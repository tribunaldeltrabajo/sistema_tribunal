#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CALCULADORA RELATORÍA
LRT (Ley 24.557) — Sentencia, Liquidación y Honorarios
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import os
from utils.navegacion import mostrar_sidebar_navegacion
from utils.funciones_comunes import (
    safe_parse_date, redondear, formato_moneda,
    numero_a_letras, get_mes_nombre
)
from utils.motor_actualizacion import cargar_todo, calcular_ipc_cer_3, calcular_cer_simple, calcular_art55, calcular_tasa_activa as _calc_tasa

def mes_anio(fecha):
    """Devuelve 'Mes AAAA' en español."""
    return f"{get_mes_nombre(fecha.month)} {fecha.year}"

mostrar_sidebar_navegacion('relatoria')

# ─────────────────────────────────────────────
# RUTAS
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

PATH_TASA  = os.path.join(DATA_DIR, "dataset_tasa.csv")
PATH_PISOS = os.path.join(DATA_DIR, "dataset_pisos.csv")
PATH_JUS   = os.path.join(DATA_DIR, "Dataset_JUS.csv")
TASA_JUSTICIA    = 0.022
SOBRETASA_CAJA   = 0.05
FACTOR_HONORARIO = 1.31
TOPE_NETO        = 0.25 / FACTOR_HONORARIO

# ─────────────────────────────────────────────
# CARGA DE DATASETS
# ─────────────────────────────────────────────

@st.cache_data
def cargar_datasets():
    DS = cargar_todo()

    df_pisos = pd.read_csv(PATH_PISOS)
    df_pisos.columns = df_pisos.columns.str.strip().str.lower()
    df_pisos['desde'] = df_pisos['fecha_inicio'].apply(safe_parse_date)
    df_pisos['hasta'] = df_pisos['fecha_fin'].apply(safe_parse_date)
    df_pisos['piso']  = pd.to_numeric(df_pisos['monto_minimo'], errors='coerce')
    df_pisos['resol'] = df_pisos['norma'].astype(str)
    df_pisos = df_pisos.dropna(subset=['desde','piso']).sort_values('desde').reset_index(drop=True)

    df_jus = pd.read_csv(PATH_JUS)
    df_jus.columns = df_jus.columns.str.strip()
    df_jus['FECHA ENTRADA EN VIGENCIA'] = pd.to_datetime(df_jus['FECHA ENTRADA EN VIGENCIA'], dayfirst=True)
    df_jus['FECHA DE FINALIZACION'] = pd.to_datetime(df_jus['FECHA DE FINALIZACION'], format='%d/%m/%Y', dayfirst=True, errors='coerce')
    df_jus['VALOR IUS'] = df_jus['VALOR IUS'].astype(str).str.replace('$','').str.replace('.','').str.replace(',','.').str.strip()
    df_jus['VALOR IUS'] = pd.to_numeric(df_jus['VALOR IUS'], errors='coerce')

    DS['df_pisos'] = df_pisos
    DS['df_jus']   = df_jus
    return DS


# ─────────────────────────────────────────────
# MOTOR IPC + 3%
# ─────────────────────────────────────────────

def actualizar_ipc_cer(monto, fecha_origen, fecha_calculo):
    return calcular_ipc_cer_3(monto, fecha_origen, fecha_calculo, DS['df_ipc'], DS['df_cer'])

def actualizar_tasa_activa(monto, fecha_origen, fecha_calculo):
    return _calc_tasa(monto, fecha_origen, fecha_calculo, DS['df_tasa'])

def get_piso(df_pisos, fecha_pmi):
    candidate = None
    for _, r in df_pisos.iterrows():
        d0, d1 = r['desde'], r['hasta']
        if pd.isna(d1) or d1 is None:
            if fecha_pmi >= d0:
                candidate = (float(r['piso']), r['resol'])
        else:
            if d0 <= fecha_pmi <= d1:
                return (float(r['piso']), r['resol'])
    return candidate if candidate else (None, "")


def agregar_tasas(subtotal):
    tj   = float(redondear(Decimal(str(subtotal)) * Decimal(str(TASA_JUSTICIA))))
    caja = float(redondear(Decimal(str(tj)) * Decimal(str(SOBRETASA_CAJA))))
    total = float(redondear(Decimal(str(subtotal)) + Decimal(str(tj)) + Decimal(str(caja))))
    return tj, caja, total


def get_valor_jus(df_jus, fecha):
    fecha_ts = pd.Timestamp(fecha)
    reg = df_jus[
        (df_jus['FECHA ENTRADA EN VIGENCIA'] <= fecha_ts) &
        ((df_jus['FECHA DE FINALIZACION'] >= fecha_ts) | df_jus['FECHA DE FINALIZACION'].isna())
    ]
    if reg.empty:
        reg = df_jus.iloc[:1]
    row = reg.iloc[0]
    return float(row['VALOR IUS']), str(row['ACUERDO'])


# ─────────────────────────────────────────────
# CÁLCULO LRT
# ─────────────────────────────────────────────

def calcular_lrt(pmi, f_calc, ibm, edad, incapacidad, art3):
    capital_formula = float(redondear(
        Decimal(str(ibm)) * 53
        * (Decimal('65') / Decimal(str(edad)))
        * (Decimal(str(incapacidad)) / 100)
    ))
    piso_monto, piso_norma = get_piso(DS['df_pisos'], pmi)
    if piso_monto:
        piso_prop = float(redondear(Decimal(str(piso_monto)) * Decimal(str(incapacidad)) / 100))
        piso_aplicado = capital_formula < piso_prop
        capital_base = piso_prop if piso_aplicado else capital_formula
        piso_txt = (
            f"Se aplica piso mínimo determinado por la {piso_norma}, que multiplicado por el "
            f"porcentaje de incapacidad ({incapacidad:.1f}%) alcanza la suma de {formato_moneda(piso_prop)}."
            if piso_aplicado else
            f"Dicho monto supera el piso mínimo determinado por la {piso_norma}, que multiplicado "
            f"por el porcentaje de incapacidad ({incapacidad:.1f}%) alcanza la suma de {formato_moneda(piso_prop)}."
        )
    else:
        capital_base  = capital_formula
        piso_aplicado = False
        piso_txt      = "Sin piso disponible para la fecha."

    adicional_20  = float(redondear(Decimal(str(capital_base)) * Decimal('0.20'))) if art3 else 0.0
    capital_total = float(redondear(Decimal(str(capital_base)) + Decimal(str(adicional_20))))

    from utils.motor_actualizacion import calcular_tasa_pasiva
    res_ipc  = actualizar_ipc_cer(capital_total, pmi, f_calc)
    res_cer  = calcular_cer_simple(capital_total, pmi, f_calc, DS['datos_cer_xls'])
    res_tasa = actualizar_tasa_activa(capital_total, pmi, f_calc)
    res_tp   = calcular_tasa_pasiva(capital_total, pmi, f_calc, DS['datos_tp'])

    return {
        'capital_formula': capital_formula,
        'capital_base':    capital_base,
        'piso_aplicado':   piso_aplicado,
        'piso_txt':        piso_txt,
        'adicional_20':    adicional_20,
        'capital_total':   capital_total,
        'ipc':             res_ipc,
        'cer':             res_cer,
        'tasa':            res_tasa,
        'tp':              res_tp,
        'pmi':             pmi,
        'fecha_calculo':   f_calc,
        'ibm':             ibm,
        'edad':            edad,
        'incapacidad':     incapacidad,
        'art3':            art3,
    }


# ─────────────────────────────────────────────
# GENERADORES DE TEXTO
# ─────────────────────────────────────────────

def texto_liquidacion(r, caratula, variante):
    ipc  = r['ipc']
    tasa = r['tasa']
    f_pmi     = r['pmi'].strftime('%d/%m/%Y')
    f_calculo = r['fecha_calculo'].strftime('%d/%m/%Y')

    if ipc['metodo'] == 'CER+IPC':
        linea_act = (
            f"2. Capital Actualizado mediante CER/IPC "
            f"(CER {ipc['ipc_origen_fecha'].strftime('%m/%Y')}: {ipc['cer_origen']:.6f} / "
            f"CER Nov-2016: {ipc['cer_nov2016']:.6f} — Coef. CER: {ipc['coef_cer']:.4f} — "
            f"IPC base 100 / {ipc['ipc_ultimo_fecha'].strftime('%m/%Y')}: {ipc['ipc_ultimo']:.2f} — "
            f"Coef. total: {ipc['coef']:.4f} — {ipc['pct_variacion']:.2f}%) "
            f"{formato_moneda(ipc['capital_indexado'])}"
        )
    else:
        linea_act = (
            f"2. Capital Actualizado mediante IPC "
            f"({ipc['ipc_ultimo_fecha'].strftime('%m/%Y')}: {ipc['ipc_ultimo']:.2f} / "
            f"{ipc['ipc_origen_fecha'].strftime('%m/%Y')}: {ipc['ipc_origen']:.2f} — "
            f"Coef. {ipc['coef']:.4f} — {ipc['pct_variacion']:.2f}%) "
            f"{formato_moneda(ipc['capital_indexado'])}"
        )

    if variante == 'ipc':
        subtotal = ipc['total']
        lineas = [
            f"1. Capital Histórico {formato_moneda(r['capital_total'])}",
            linea_act,
            f"3. Interés puro del 3% anual desde {f_pmi} hasta {f_calculo} {formato_moneda(ipc['interes_3'])}",
        ]

    elif variante == 'tasa':
        subtotal = tasa['total']
        lineas = [
            f"1. Capital Histórico {formato_moneda(r['capital_total'])}",
            f"2. Intereses Tasa Activa BNA desde {f_pmi} hasta {f_calculo} "
            f"(tasa acumulada: {tasa['tasa_pct']:.2f}%) {formato_moneda(tasa['total'] - r['capital_total'])}",
        ]

    elif variante == 'cer':
        cer = r['cer']
        subtotal = cer['total']
        lineas = [
            f"1. Capital Histórico {formato_moneda(r['capital_total'])}",
            f"2. Capital Actualizado mediante CER "
            f"({cer['cer_calculo_fecha'].strftime('%d/%m/%Y')}: {cer['cer_calculo']:.6f} / "
            f"{cer['cer_origen_fecha'].strftime('%d/%m/%Y')}: {cer['cer_origen']:.6f} — "
            f"Coef. {cer['coef']:.6f} — {cer['pct_variacion']:.2f}%) {formato_moneda(cer['capital_indexado'])}",
            f"3. Interés puro del 3% anual desde {f_pmi} hasta {f_calculo} {formato_moneda(cer['interes_3'])}",
        ]

    elif variante == 'tp':
        tp = r['tp']
        subtotal = tp['total']
        lineas = [
            f"1. Capital Histórico {formato_moneda(r['capital_total'])}",
            f"2. Intereses Tasa Pasiva BCRA desde {f_pmi} hasta {f_calculo} "            f"(T\u2080: {tp['T0']:.6f} / T\u2098: {tp['Tm']:.6f} — tasa período: {tp['tasa_pct']:.2f}%) "            f"{formato_moneda(tp['total'] - r['capital_total'])}",
        ]

    else:  # art55
        subtotal = ipc.get('art55_piso', 0.0)
        lineas = [
            f"1. Capital Histórico {formato_moneda(r['capital_total'])}",
            linea_act,
            f"3. Interés puro del 3% anual desde {f_pmi} hasta {f_calculo} {formato_moneda(ipc['interes_3'])}",
            f"SUBTOTAL CER + 3% {formato_moneda(ipc['total'])}",
            f"4. Art. 55 Ley 27802 (67% de IPC+3%) {formato_moneda(subtotal)}",
        ]

    tj, caja, total_final = agregar_tasas(subtotal)
    cuerpo = "\n".join(lineas)

    texto = (
        f"Quilmes, en la fecha en que se suscribe con firma digital (Ac. SCBA. 3975/20).\n"
        f"LIQUIDACION que practica la Actuaria en el presente expediente caratulado: {caratula}\n\n"
        f"{cuerpo}\n"
        f"SUBTOTAL {formato_moneda(subtotal)}\n\n"
        f"*Tasa de Justicia (2,2%) {formato_moneda(tj)} *\n"
        f"Sobretasa Contribución Caja de Abogados (5% de Tasa) {formato_moneda(caja)}\n"
        f"TOTAL {formato_moneda(total_final)}\n"
        f"Importa la presente liquidación la suma de {numero_a_letras(total_final)}-\n"
        f"De la liquidación practicada, traslado a las partes por el plazo de cinco (5) días, "
        f"bajo apercibimiento de tenerla por consentida (art 59 de la Ley 15.057 - RC 1840/24 SCBA) "
        f"Notifíquese.-"
    )
    return texto, total_final


def texto_sentencia(r):
    ipc  = r['ipc']
    tasa = r['tasa']

    art3_txt = (
        f"20% Art. 3 Ley 26.773: {formato_moneda(r['adicional_20'])}"
        if r['art3'] else
        "20% Art. 3 Ley 26.773: no corresponde"
    )

    bloque_formula = (
        f"Fórmula:\n"
        f"Valor de IBM ({formato_moneda(r['ibm'])}) x 53 x 65/edad({r['edad']}) x Incapacidad ({r['incapacidad']:.1f}%)\n"
        f"Capital calculado: {formato_moneda(r['capital_formula'])}\n"
        f"{r['piso_txt']}\n"
        f"{art3_txt}\n"
        f"Total: {formato_moneda(r['capital_total'])}\n"
        f"SON {numero_a_letras(r['capital_total'])}"
    )

    mes_pmi  = get_mes_nombre(r['pmi'].month).lower()
    anio_pmi = r['pmi'].year
    pct_tasa = tasa['tasa_pct']
    pct_ipc  = ipc['pct_variacion']
    f_pmi    = r['pmi'].strftime('%d/%m/%Y')

    if ipc['total'] > tasa['total']:
        bloque_comparativo = (
            f"La confrontación entre la tasa activa del Banco de la Nación Argentina prevista en el "
            f"artículo 12 de la LRT y la variación del IPC correspondiente al período comprendido "
            f"entre {mes_pmi} de {anio_pmi} y la fecha evidencia, en el caso, la insuficiencia "
            f"del mecanismo legal para preservar el contenido económico de la prestación. En efecto, "
            f"mientras la tasa activa acumuló aproximadamente un {pct_tasa:.2f}%, el IPC registrado "
            f"por el INDEC para idéntico período alcanzó el {pct_ipc:.2f}%. El resultado concreto en "
            f"el expediente es el que se expone en los guarismos obrantes en autos. "
            f"Histórico al {f_pmi}: {formato_moneda(r['capital_total'])}; "
            f"Tasa Act. BNA: {formato_moneda(tasa['total'])}; "
            f"IPC+3%: {formato_moneda(ipc['total'])}."
        )
    else:
        bloque_comparativo = (
            f"La confrontación entre la tasa activa del Banco de la Nación Argentina prevista en el "
            f"artículo 12 de la LRT y la variación del IPC correspondiente al período comprendido "
            f"entre {mes_pmi} de {anio_pmi} y la fecha no evidencia insuficiencia del mecanismo "
            f"legal para preservar el contenido económico de la prestación. En efecto, la tasa activa "
            f"acumuló aproximadamente un {pct_tasa:.2f}%, en tanto el IPC registrado por el INDEC "
            f"para idéntico período alcanzó el {pct_ipc:.2f}%, siendo en el caso el mecanismo legal "
            f"constitucionalmente aceptable. El resultado concreto en el expediente es el que se "
            f"expone en los guarismos obrantes en autos. "
            f"Histórico al {f_pmi}: {formato_moneda(r['capital_total'])}; "
            f"Tasa Act. BNA: {formato_moneda(tasa['total'])}; "
            f"IPC+3%: {formato_moneda(ipc['total'])}."
        )

    return bloque_formula + "\n\n" + bloque_comparativo


# ─────────────────────────────────────────────
# HONORARIOS
# ─────────────────────────────────────────────

def calcular_honorarios(monto_juicio, n_auxiliares, valor_jus):
    """
    Total con aportes e IVA (x1.31) nunca supera 25% del juicio.
    Tope neto = 25% / 1.31 = 19.08%.
    Actor nunca baja de 12% neto. Si aplica piso, auxiliares se prorratean.
    Mínimos: 7 JUS actor, 3.5 JUS auxiliar.
    """
    TOPE_NETO = 0.25 / FACTOR_HONORARIO  # ~19.08%
    tabla_aux = {0: 0.00, 1: 0.05, 2: 0.04, 3: 0.035, 4: 0.030, 5: 0.025}

    n       = min(n_auxiliares, 5)
    pct_aux = tabla_aux[n]

    # Actor toma el resto hasta el tope neto
    pct_actor = TOPE_NETO - pct_aux * n

    if pct_actor < 0.12:
        # Actor en piso — auxiliares se prorratean para no superar tope
        pct_actor = 0.12
        if n > 0:
            pct_aux = (TOPE_NETO - 0.12) / n

    # Mínimos en JUS
    minimo_actor = 7   * valor_jus
    minimo_aux   = 3.5 * valor_jus

    actor_minimo_aplicado = (monto_juicio * pct_actor) < minimo_actor
    aux_minimo_aplicado   = n > 0 and (monto_juicio * pct_aux) < minimo_aux

    hon_actor_neto = max(monto_juicio * pct_actor, minimo_actor)
    hon_aux_neto   = max(monto_juicio * pct_aux,   minimo_aux) if n > 0 else 0.0

    pct_actor_real = hon_actor_neto / monto_juicio * 100
    pct_aux_real   = hon_aux_neto   / monto_juicio * 100 if n > 0 else 0.0

    hon_dem_neto = hon_actor_neto * 0.70
    pct_dem_real = hon_dem_neto / monto_juicio * 100

    # IVA y aportes por separado
    IVA      = Decimal('0.21')
    APORTES  = Decimal('0.10')

    def desglose(neto):
        n_dec    = Decimal(str(neto))
        aportes  = float(redondear(n_dec * APORTES))
        iva      = float(redondear(n_dec * IVA))
        total    = float(redondear(n_dec + Decimal(str(aportes)) + Decimal(str(iva))))
        return aportes, iva, total

    actor_ap, actor_iva, actor_total = desglose(hon_actor_neto)
    dem_ap,   dem_iva,   dem_total   = desglose(hon_dem_neto)
    aux_ap,   aux_iva,   aux_total   = desglose(hon_aux_neto) if n > 0 else (0.0, 0.0, 0.0)

    actor_jus = round(hon_actor_neto / valor_jus, 2) if valor_jus > 0 else 0
    dem_jus   = round(hon_dem_neto   / valor_jus, 2) if valor_jus > 0 else 0
    aux_jus   = round(hon_aux_neto   / valor_jus, 2) if valor_jus > 0 else 0

    total_sin_dem  = hon_actor_neto + hon_aux_neto * n
    pct_total_real = total_sin_dem / monto_juicio * 100

    return {
        'actor_neto':   hon_actor_neto, 'actor_total':  actor_total,
        'actor_pct':    pct_actor_real, 'actor_jus':    actor_jus,
        'actor_ap':     actor_ap,       'actor_iva':    actor_iva,
        'dem_neto':     hon_dem_neto,   'dem_total':    dem_total,
        'dem_pct':      pct_dem_real,   'dem_jus':      dem_jus,
        'dem_ap':       dem_ap,         'dem_iva':      dem_iva,
        'aux_neto':     hon_aux_neto,   'aux_total':    aux_total,
        'aux_pct':      pct_aux_real,   'aux_jus':      aux_jus,
        'aux_ap':       aux_ap,         'aux_iva':      aux_iva,
        'n_aux':        n,
        'total_sin_dem': total_sin_dem,
        'pct_total':    pct_total_real,
        'valor_jus':          valor_jus,
        'actor_min':          actor_minimo_aplicado,
        'aux_min':            aux_minimo_aplicado,
    }


# ─────────────────────────────────────────────
# CARGA INICIAL
# ─────────────────────────────────────────────

try:
    DS = cargar_datasets()
except Exception as e:
    st.error(f"Error al cargar datasets: {e}")
    st.stop()


# Limpiar cache de honorarios si viene de versión anterior
if 'hon_res' in st.session_state and ('actor_min' not in st.session_state.get('hon_res', {}) or 'dem_jus' not in st.session_state.get('hon_res', {})):
    del st.session_state['hon_res']
    if 'hon_acuerdo' in st.session_state: del st.session_state['hon_acuerdo']
    if 'hon_monto_j' in st.session_state: del st.session_state['hon_monto_j']

# ═══════════════════════════════════════════════════════════════
# ENCABEZADO
# ═══════════════════════════════════════════════════════════════

st.markdown("# ⚖️ CALCULADORA RELATORÍA — LRT")
st.markdown("---")

# ─────────────────────────────────────────────
# INPUTS ÚNICOS
# ─────────────────────────────────────────────

caratula_input = st.text_input(
    "Carátula del expediente",
    key="rel_caratula",
    placeholder="Apellido c/ Empresa S.A. s/ Accidente de Trabajo"
)

c1, c2 = st.columns(2)
with c1:
    pmi_input = st.date_input("Fecha PMI", value=date(2020, 1, 1),
        min_value=date(2002,1,1), max_value=date.today(),
        format="DD/MM/YYYY", key="rel_pmi")
with c2:
    fcalc_input = st.date_input("Fecha de cálculo", value=date.today(),
        format="DD/MM/YYYY", key="rel_fcalc")

c3, c4, c5 = st.columns(3)
with c3:
    ibm_input = st.number_input("IBM actualizado ($)", min_value=0.01,
        value=500000.0, step=1000.0, format="%.2f", key="rel_ibm")
with c4:
    edad_input = st.number_input("Edad", min_value=18, max_value=100,
        value=45, step=1, key="rel_edad")
with c5:
    inc_input = st.number_input("Incapacidad (%)", min_value=0.01,
        max_value=100.0, value=30.0, step=0.5, format="%.2f", key="rel_inc")

art3_input = st.checkbox("Incluir 20% art. 3 Ley 26.773", value=True, key="rel_art3")

calcular = st.button("⚡ CALCULAR", type="primary", use_container_width=True, key="btn_rel")

if calcular:
    if pmi_input >= fcalc_input:
        st.error("La fecha PMI debe ser anterior a la fecha de cálculo.")
    else:
        res = calcular_lrt(pmi_input, fcalc_input, ibm_input, edad_input, inc_input, art3_input)
        st.session_state['rel_res'] = res
        st.session_state['rel_caratula_val'] = caratula_input

# ─────────────────────────────────────────────
# RESUMEN DE RESULTADOS
# ─────────────────────────────────────────────

if 'rel_res' in st.session_state:
    r = st.session_state['rel_res']
    ipc  = r['ipc']
    tasa = r['tasa']
    art55 = ipc.get('art55_piso', 0.0)

    cer_total = r.get('cer', {}).get('total', 0.0)
    tp_total  = r.get('tp',  {}).get('total', 0.0)

    # Ordenados de mayor a menor (sin CER)
    principales = sorted([
        ('IPC + 3% (Art. 276 LCT conf. Art. 54 LML)',          ipc['total'],   '#4a9e9e'),
        ('Tasa Activa BNA (Art. 12 inc. b LRT conf. Art. 11 Ley 27.348)',   tasa['total'],  '#c8956a'),
        ('Art. 55 inc. c LML — 67% de IPC + 3%', art55,          '#c8956a'),
        ('Tasa Pasiva BCRA (Art. 55 inc. a LML conf. Res. 45/26 BCRA)',  tp_total,       '#9c82ae'),
    ], key=lambda x: -x[1])

    _colores_pos = ['#4a9e9e', '#6a9e7a', '#c8956a', '#9c82ae']
    st.markdown("---")
    for _i, (_lbl, _val, _c) in enumerate(principales):
        _col = _colores_pos[_i] if _i < len(_colores_pos) else '#9c82ae'
        st.markdown(
            f"<div style='background:{_col};padding:8px 16px;margin-bottom:4px;"
            f"display:flex;justify-content:space-between;align-items:center'>"
            f"<span style='font-weight:600;color:white;font-size:13px'>{_lbl}</span>"
            f"<span style='font-family:monospace;font-size:16px;font-weight:800;color:white'>{formato_moneda(_val)}</span>"
            f"</div>",
            unsafe_allow_html=True
        )
    # CER siempre último como referencia
    if cer_total:
        st.markdown(
            f"<div style='background:#7b5ea8;padding:8px 16px;margin-bottom:4px;"
            f"display:flex;justify-content:space-between;align-items:center'>"
            f"<span style='font-weight:600;color:white;font-size:13px'>CER + 3% (referencia)</span>"
            f"<span style='font-family:monospace;font-size:16px;font-weight:800;color:white'>{formato_moneda(cer_total)}</span>"
            f"</div>",
            unsafe_allow_html=True
        )
    st.markdown("<div style='margin-bottom:16px'></div>", unsafe_allow_html=True)

    # ─────────────────────────────────────────────
    # PESTAÑAS
    # ─────────────────────────────────────────────

    tab_sent, tab_liq, tab_hon = st.tabs(["📄 Sentencia", "📋 Liquidación", "💵 Honorarios"])

    with tab_sent:
        txt_sent = texto_sentencia(r)
        st.text_area("", txt_sent, height=max(400, txt_sent.count("\n") * 28 + 100), key="ta_sent")

    with tab_liq:
        caratula = st.session_state.get('rel_caratula_val', '')
        tp_tot = r.get('tp', {}).get('total', 0.0)
        variantes_liq = sorted([
            ('ipc',   ipc['total']),
            ('tasa',  tasa['total']),
            ('art55', art55),
            ('tp',    tp_tot),
        ], key=lambda x: -x[1])

        labels = {'ipc': 'IPC + 3% (Art. 276 LCT conf. Art. 54 LML)', 'tasa': 'Tasa Activa BNA (Art. 12 inc. b LRT conf. Art. 11 Ley 27.348)', 'art55': 'Art. 55 Ley 27802 (67%)', 'tp': 'Tasa Pasiva BCRA (Art. 55 inc. a LML conf. Res. 45/26 BCRA)'}
        subtotales = {'ipc': ipc['total'], 'tasa': tasa['total'], 'art55': art55, 'tp': tp_tot}
        for idx, (variante, _) in enumerate(variantes_liq):
            texto_var, total_final = texto_liquidacion(r, caratula, variante)
            subtotal = subtotales[variante]
            titulo = f"**{labels[variante]} — {formato_moneda(subtotal)}**" if idx == 0 else f"{labels[variante]} — {formato_moneda(subtotal)}"
            st.markdown(titulo)
            st.text_area("", texto_var, height=max(400, texto_var.count("\n") * 28 + 100), key=f"ta_liq_{variante}")

    with tab_hon:
        st.subheader("Regulación de Honorarios — Ley 24.432")
        # Monto viene del cálculo principal — el más favorable
        monto_juicio_hon = max(ipc['total'], tasa['total'])

        c1, c2 = st.columns(2)
        with c1:
            fecha_sent_hon = st.date_input("Fecha de sentencia",
                value=date.today(), format="DD/MM/YYYY", key="hon_fecha")
        with c2:
            n_aux = st.number_input("Cantidad de auxiliares",
                min_value=0, max_value=5, value=1, step=1, key="hon_naux")

        st.caption(f"Monto del juicio (más favorable): {formato_moneda(monto_juicio_hon)}")

        if st.button("⚡ CALCULAR HONORARIOS", type="primary", key="btn_hon"):
            valor_jus, acuerdo_jus = get_valor_jus(DS['df_jus'], fecha_sent_hon)
            h = calcular_honorarios(monto_juicio_hon, int(n_aux), valor_jus)
            st.session_state['hon_res']    = h
            st.session_state['hon_acuerdo'] = acuerdo_jus
            st.session_state['hon_monto_j'] = monto_juicio_hon

        if 'hon_res' in st.session_state and 'hon_acuerdo' in st.session_state and 'hon_monto_j' in st.session_state:
            h       = st.session_state['hon_res']
            acuerdo = st.session_state['hon_acuerdo']
            monto_j = st.session_state['hon_monto_j']

            st.caption(f"Monto del juicio: {formato_moneda(monto_j)} — JUS vigente: {formato_moneda(h['valor_jus'])} ({acuerdo})")
            st.markdown("---")

            def fila_honorario(label, pct, neto, jus, ap, iva, total, minimo=False):
                jus_val = f"{jus:.2f}" if jus is not None and jus == jus else "—"
                min_txt = " ⚠️ *mínimo aplicado (JUS)*" if minimo else ""
                st.markdown(f"**{label}:** {pct:.2f}% — {formato_moneda(neto)} — {jus_val} JUS{min_txt}")
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;+ Aportes (10%): {formato_moneda(ap)}", unsafe_allow_html=True)
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;+ IVA (21%): {formato_moneda(iva)}", unsafe_allow_html=True)
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**= Total con aportes e IVA: {formato_moneda(total)}**", unsafe_allow_html=True)
                st.markdown("")

            fila_honorario("Representación Actora",    h['actor_pct'], h['actor_neto'], h['actor_jus'], h['actor_ap'], h['actor_iva'], h['actor_total'], h.get('actor_min', False))
            fila_honorario("Representación Demandada", h['dem_pct'],   h['dem_neto'],   h['dem_jus'],   h['dem_ap'],   h['dem_iva'],   h['dem_total'])
            for i in range(1, h['n_aux'] + 1):
                fila_honorario(f"Auxiliar {i}", h['aux_pct'], h['aux_neto'], h['aux_jus'], h['aux_ap'], h['aux_iva'], h['aux_total'], h.get('aux_min', False))

            st.markdown("---")
            total_con_factor = float(redondear(Decimal(str(h['total_sin_dem'])) * Decimal(str(FACTOR_HONORARIO))))
            pct_con_factor = total_con_factor / monto_j * 100
            st.markdown(f"**Total regulado (sin demandada):**")
            st.markdown(f"Neto: {formato_moneda(h['total_sin_dem'])} — {h['pct_total']:.2f}%")
            st.markdown(f"**Con aportes e IVA: {formato_moneda(total_con_factor)} — {pct_con_factor:.2f}%**")