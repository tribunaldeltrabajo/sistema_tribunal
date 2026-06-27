#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CALCULADORA DE ACTUALIZACIÓN E INTERESES
"""

import streamlit as st
from datetime import date, timedelta
from decimal import Decimal
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.navegacion import mostrar_sidebar_navegacion
from utils.funciones_comunes import redondear, formato_moneda, numero_a_letras, get_mes_nombre
from utils.motor_actualizacion import (
    cargar_todo, calcular_ipc_cer_3, calcular_cer_simple,
    calcular_art55, calcular_bcra, calcular_tasa_activa, calcular_tasa_pasiva,
    calcular_con_capitalizacion, calcular_ripte_6
)

mostrar_sidebar_navegacion('actualizacion')

TASA_JUSTICIA  = 0.022
SOBRETASA_CAJA = 0.05

def mes_anio(fecha):
    return f"{get_mes_nombre(fecha.month)} {fecha.year}"

def agregar_tasas(subtotal):
    tj   = float(redondear(Decimal(str(subtotal)) * Decimal(str(TASA_JUSTICIA))))
    caja = float(redondear(Decimal(str(tj)) * Decimal(str(SOBRETASA_CAJA))))
    total = float(redondear(Decimal(str(subtotal)) + Decimal(str(tj)) + Decimal(str(caja))))
    return tj, caja, total

def texto_liq_generico(cap_historico, f_origen, f_calc, lineas_cuerpo, subtotal):
    """Formato exacto de liquidación — idéntico al de relatoría."""
    tj, caja, total_final = agregar_tasas(subtotal)
    cuerpo = "\n".join(lineas_cuerpo)
    return (
        f"Quilmes, en la fecha en que se suscribe con firma digital (Ac. SCBA. 3975/20).\n"
        f"LIQUIDACION que practica la Actuaria en el presente expediente.\n\n"
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

@st.cache_data
def _cargar():
    return cargar_todo()

try:
    DS = _cargar()
except Exception as e:
    st.error(f"Error al cargar datasets: {e}")
    st.stop()

st.markdown("# 📈 ACTUALIZACIÓN E INTERESES")
st.markdown("---")

# ── Inputs ──
c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    monto = st.number_input("Monto histórico ($)", min_value=0.01,
        value=1000000.0, step=1000.0, format="%.2f", key="act_monto")
with c2:
    fecha_ini = st.date_input("Fecha inicial", value=date(2020, 1, 1),
        min_value=date(1993, 6, 3), max_value=date.today(),
        format="DD/MM/YYYY", key="act_ini")
with c3:
    fecha_fin = st.date_input("Fecha final", value=date.today(),
        min_value=date(1993, 6, 4), max_value=date.today() + timedelta(days=365),
        format="DD/MM/YYYY", key="act_fin")

c4, c5 = st.columns([1, 2])
with c4:
    capitaliza = st.checkbox("Capitaliza intereses — opcional (Art. 770 inc. b CCyC)", value=False, key="act_capitaliza")
with c5:
    fecha_demanda = st.date_input("Fecha de interposición de demanda", value=date(2022, 1, 1),
        min_value=date(1993, 6, 4), max_value=date.today(),
        format="DD/MM/YYYY", key="act_fecha_demanda", disabled=not capitaliza)

if st.button("⚡ CALCULAR", type="primary", use_container_width=True, key="btn_act"):
    if fecha_ini >= fecha_fin:
        st.error("La fecha inicial debe ser anterior a la fecha final.")
    elif capitaliza and not (fecha_ini < fecha_demanda < fecha_fin):
        st.error("La fecha de interposición de demanda debe estar entre la fecha inicial y la fecha final.")
    else:
        r_ipc   = calcular_ipc_cer_3(monto, fecha_ini, fecha_fin, DS['df_ipc'], DS['df_cer'])
        r_cer   = calcular_cer_simple(monto, fecha_ini, fecha_fin, DS['datos_cer_xls'])
        r55     = calcular_art55(monto, fecha_ini, fecha_fin, DS['df_ipc'], DS['df_cer'], DS['datos_tp'])
        r_ripte = calcular_ripte_6(monto, fecha_ini, fecha_fin, DS['df_ripte'])

        if capitaliza:
            r_ta = calcular_con_capitalizacion(monto, fecha_ini, fecha_demanda, fecha_fin, DS['df_tasa'], tipo='activa')
            r_tp = calcular_con_capitalizacion(monto, fecha_ini, fecha_demanda, fecha_fin, DS['datos_tp'], tipo='pasiva')
        else:
            r_ta = calcular_tasa_activa(monto, fecha_ini, fecha_fin, DS['df_tasa'])
            r_tp = calcular_tasa_pasiva(monto, fecha_ini, fecha_fin, DS['datos_tp'])

        st.session_state['act_res']    = r_ipc
        st.session_state['act_cer']    = r_cer
        st.session_state['act_55']     = r55
        st.session_state['act_ripte']  = r_ripte
        st.session_state['act_ta']     = r_ta
        st.session_state['act_tp']     = r_tp
        st.session_state['act_capitaliza_usado']    = capitaliza
        st.session_state['act_fecha_demanda_usada'] = fecha_demanda if capitaliza else None
        st.session_state['act_monto_calc']  = monto
        st.session_state['act_f_ini_calc']  = fecha_ini
        st.session_state['act_f_fin_calc']  = fecha_fin

if 'act_res' in st.session_state and 'act_ripte' not in st.session_state:
    del st.session_state['act_res']

if 'act_res' not in st.session_state:
    st.info("👈 Completá los datos y presioná CALCULAR")
    st.stop()

r       = st.session_state['act_res']
r55     = st.session_state['act_55']
r_ripte = st.session_state['act_ripte']
r_ta    = st.session_state['act_ta']
r_tp    = st.session_state['act_tp']
r_cer   = st.session_state.get('act_cer', {})
cap_usado       = st.session_state.get('act_capitaliza_usado', False)
f_demanda_usada = st.session_state.get('act_fecha_demanda_usada')
monto_c   = st.session_state['act_monto_calc']
f_ini_c   = st.session_state['act_f_ini_calc']
f_fin_c   = st.session_state['act_f_fin_calc']
f_ini_str = f_ini_c.strftime('%d/%m/%Y')
f_fin_str = f_fin_c.strftime('%d/%m/%Y')

st.markdown("---")

# ═══════════════════════════════════════════════════════════════
# BLOQUE 1 — IPC + 3%
# ═══════════════════════════════════════════════════════════════
st.markdown("**IPC + 3% simple (Art. 276 LCT conf. Art. 54 LML)**")
st.markdown(
    f"<div style='background:#b8952a;padding:8px 16px;margin-bottom:8px;"
    f"display:flex;justify-content:space-between;align-items:center;border-radius:4px'>"
    f"<span style='color:white;font-weight:600'>Total actualizado</span>"
    f"<span style='color:white;font-family:monospace;font-size:16px;font-weight:800'>"
    f"{formato_moneda(r['total'])}</span></div>",
    unsafe_allow_html=True
)

if r['metodo'] == 'CER+IPC':
    linea_act_ipc = (
        f"2. Capital Actualizado mediante CER/IPC "
        f"(CER {f_ini_c.strftime('%m/%Y')}: {r['cer_origen']:.6f} / "
        f"CER Nov-2016: {r['cer_nov2016']:.6f} — Coef. CER: {r['coef_cer']:.4f} — "
        f"IPC base 100 / {r['ipc_ultimo_fecha'].strftime('%m/%Y')}: {r['ipc_ultimo']:.2f} — "
        f"Coef. total: {r['coef']:.4f} — {r['pct_variacion']:.2f}%) "
        f"{formato_moneda(r['capital_indexado'])}"
    )
else:
    linea_act_ipc = (
        f"2. Capital Actualizado mediante IPC "
        f"({r['ipc_ultimo_fecha'].strftime('%m/%Y')}: {r['ipc_ultimo']:.2f} / "
        f"{f_ini_c.strftime('%m/%Y')}: {r['ipc_origen']:.2f} — "
        f"Coef. {r['coef']:.4f} — {r['pct_variacion']:.2f}%) "
        f"{formato_moneda(r['capital_indexado'])}"
    )

with st.expander("Detalle"):
    if r['metodo'] == 'CER+IPC':
        st.write(f"**Método:** CER + IPC (empalme)")
        st.write(f"**CER origen ({f_ini_c.strftime('%m/%Y')}):** {r['cer_origen']:.6f}")
        st.write(f"**CER nov-2016:** {r['cer_nov2016']:.6f}")
        st.write(f"**Coef. CER:** {r['coef_cer']:.6f}")
        st.write(f"**Coef. IPC:** {r['coef_ipc']:.6f}")
    else:
        st.write(f"**IPC origen ({mes_anio(f_ini_c)}):** {r['ipc_origen']:.2f}")
        st.write(f"**IPC último ({mes_anio(r['ipc_ultimo_fecha'])}):** {r['ipc_ultimo']:.2f}")
    st.write(f"**Coef. total:** {r['coef']:.6f} ({r['pct_variacion']:.2f}%)")
    st.write(f"**Capital indexado:** {formato_moneda(r['capital_indexado'])}")
    st.write(f"**Interés 3% simple ({r['dias']} días):** {formato_moneda(r['interes_3'])}")

with st.expander("Liquidación"):
    lineas_ipc = [
        f"1. Capital Histórico {formato_moneda(monto_c)}",
        linea_act_ipc,
        f"3. Interés puro del 3% anual desde {f_ini_str} hasta {f_fin_str} {formato_moneda(r['interes_3'])}",
    ]
    txt_ipc = texto_liq_generico(monto_c, f_ini_c, f_fin_c, lineas_ipc, r['total'])
    st.text_area("", txt_ipc, height=max(300, txt_ipc.count('\n') * 28 + 100), key="ta_liq_ipc")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════
# BLOQUE 2 — ART. 55 inc. c) — 67% de IPC+3% (piso)
# ═══════════════════════════════════════════════════════════════
usar_bcra_55 = st.checkbox(
    "Método BCRA (CER + 3% compuesto)",
    value=False, key="act_bcra_55",
    help="La calculadora oficial del BCRA usa el CER diario con interés compuesto."
)
if usar_bcra_55:
    r55_show = calcular_art55(monto_c, f_ini_c, f_fin_c, DS['df_ipc'], DS['df_cer'], DS['datos_tp'],
                              usar_bcra=True, datos_cer_xls=DS['datos_cer_xls'])
else:
    r55_show = r55

st.markdown("**Art. 55 inc. c) LML — 67% de IPC + 3% (piso)**")
st.markdown(
    f"<div style='background:#9d6b18;padding:8px 16px;margin-bottom:8px;"
    f"display:flex;justify-content:space-between;align-items:center;border-radius:4px'>"
    f"<span style='color:white;font-weight:600'>Total Art. 55 inc. c)</span>"
    f"<span style='color:white;font-family:monospace;font-size:16px;font-weight:800'>"
    f"{formato_moneda(r55_show['piso_67'])}</span></div>",
    unsafe_allow_html=True
)
st.caption("Se calcula también el techo (inc. b) e la tasa pasiva (inc. a) — el juez puede apartarse de la banda por inconstitucionalidad.")

with st.expander("Detalle"):
    st.write(f"**IPC + 3% — techo (inc. b):** {formato_moneda(r55_show['ipc_3'])}")
    st.write(f"**67% de IPC + 3% — piso (inc. c):** {formato_moneda(r55_show['piso_67'])}")
    st.write(f"**Tasa Pasiva BCRA (inc. a):** {formato_moneda(r55_show['tasa_pasiva'])}")
    st.write(f"**Valor que aplica según la banda:** {r55_show['label_aplica']}")

with st.expander("Liquidación"):
    lineas_55 = [
        f"1. Capital Histórico {formato_moneda(monto_c)}",
        linea_act_ipc,
        f"3. Interés puro del 3% anual desde {f_ini_str} hasta {f_fin_str} {formato_moneda(r['interes_3'])}",
        f"SUBTOTAL IPC + 3% {formato_moneda(r['total'])}",
        f"4. Art. 55 inc. c) LML — 67% de IPC + 3% {formato_moneda(r55_show['piso_67'])}",
    ]
    txt_55 = texto_liq_generico(monto_c, f_ini_c, f_fin_c, lineas_55, r55_show['piso_67'])
    st.text_area("", txt_55, height=max(300, txt_55.count('\n') * 28 + 100), key="ta_liq_55")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════
# BLOQUE 3 — TASA PASIVA BCRA (con capitalización opcional)
# ═══════════════════════════════════════════════════════════════
if cap_usado:
    st.markdown("**Tasa Pasiva BCRA — con capitalización de intereses (Art. 770 inc. b CCyC)**")
else:
    st.markdown("**Tasa Pasiva BCRA**")
st.markdown(
    f"<div style='background:#9a9eaa;padding:8px 16px;margin-bottom:8px;"
    f"display:flex;justify-content:space-between;align-items:center;border-radius:4px'>"
    f"<span style='color:white;font-weight:600'>Total Tasa Pasiva BCRA</span>"
    f"<span style='color:white;font-family:monospace;font-size:16px;font-weight:800'>"
    f"{formato_moneda(r_tp['total'])}</span></div>",
    unsafe_allow_html=True
)

with st.expander("Detalle"):
    if cap_usado:
        st.write(f"**Capital histórico:** {formato_moneda(r_tp['capital_historico'])}")
        st.write(f"**Tramo 1** — desde {f_ini_str} hasta interposición de demanda "
                 f"({f_demanda_usada.strftime('%d/%m/%Y')}): tasa acumulada {r_tp['tramo1']['tasa_pct']:.4f}%")
        st.write(f"**Capital capitalizado al {f_demanda_usada.strftime('%d/%m/%Y')}:** "
                 f"{formato_moneda(r_tp['capital_capitalizado'])} "
                 f"(interés tramo 1: {formato_moneda(r_tp['interes_tramo1'])})")
        st.write(f"**Tramo 2** — desde {f_demanda_usada.strftime('%d/%m/%Y')} hasta "
                 f"{f_fin_str}: tasa acumulada {r_tp['tramo2']['tasa_pct']:.4f}%")
        st.write(f"**Total final:** {formato_moneda(r_tp['total'])}")
    else:
        st.write(f"**T₀ ({r_tp['T0_fecha'].strftime('%d/%m/%Y')}):** {r_tp['T0']:.6f}")
        st.write(f"**Tₘ ({r_tp['Tm_fecha'].strftime('%d/%m/%Y')}):** {r_tp['Tm']:.6f}")
        st.write(f"**Tasa período:** {r_tp['tasa_pct']:.4f}%")

with st.expander("Liquidación"):
    if cap_usado:
        f_dem = f_demanda_usada.strftime('%d/%m/%Y')
        lineas_tp = [
            f"1. Capital Histórico {formato_moneda(monto_c)}",
            f"2. Intereses Tasa Pasiva BCRA desde {f_ini_str} hasta interposición de demanda ({f_dem}) "
            f"(tasa período: {r_tp['tramo1']['tasa_pct']:.4f}%) {formato_moneda(r_tp['interes_tramo1'])}",
            f"3. Capital Capitalizado al {f_dem} (Art. 770 inc. b CCyC) {formato_moneda(r_tp['capital_capitalizado'])}",
            f"4. Intereses Tasa Pasiva BCRA desde {f_dem} hasta {f_fin_str} "
            f"(tasa período: {r_tp['tramo2']['tasa_pct']:.4f}%) {formato_moneda(r_tp['total'] - r_tp['capital_capitalizado'])}",
        ]
    else:
        lineas_tp = [
            f"1. Capital Histórico {formato_moneda(monto_c)}",
            f"2. Intereses Tasa Pasiva BCRA desde {f_ini_str} hasta {f_fin_str} "
            f"(T₀: {r_tp['T0']:.6f} / Tₘ: {r_tp['Tm']:.6f} — tasa período: {r_tp['tasa_pct']:.4f}%) "
            f"{formato_moneda(r_tp['total'] - monto_c)}",
        ]
    txt_tp = texto_liq_generico(monto_c, f_ini_c, f_fin_c, lineas_tp, r_tp['total'])
    st.text_area("", txt_tp, height=max(300, txt_tp.count('\n') * 28 + 100), key="ta_liq_tp")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════
# BLOQUE 4 — TASA ACTIVA BNA (con capitalización opcional)
# ═══════════════════════════════════════════════════════════════
if cap_usado:
    st.markdown("**Tasa Activa BNA — con capitalización de intereses (Art. 770 inc. b CCyC)**")
else:
    st.markdown("**Tasa Activa BNA (Art. 12 inc. b LRT conf. Art. 11 Ley 27.348)**")
st.markdown(
    f"<div style='background:#7b9e87;padding:8px 16px;margin-bottom:8px;"
    f"display:flex;justify-content:space-between;align-items:center;border-radius:4px'>"
    f"<span style='color:white;font-weight:600'>Total Tasa Activa BNA</span>"
    f"<span style='color:white;font-family:monospace;font-size:16px;font-weight:800'>"
    f"{formato_moneda(r_ta['total'])}</span></div>",
    unsafe_allow_html=True
)

with st.expander("Detalle"):
    if cap_usado:
        st.write(f"**Capital histórico:** {formato_moneda(r_ta['capital_historico'])}")
        st.write(f"**Tramo 1** — desde {f_ini_str} hasta interposición de demanda "
                 f"({f_demanda_usada.strftime('%d/%m/%Y')}): tasa acumulada {r_ta['tramo1']['tasa_pct']:.2f}%")
        st.write(f"**Capital capitalizado al {f_demanda_usada.strftime('%d/%m/%Y')}:** "
                 f"{formato_moneda(r_ta['capital_capitalizado'])} "
                 f"(interés tramo 1: {formato_moneda(r_ta['interes_tramo1'])})")
        st.write(f"**Tramo 2** — desde {f_demanda_usada.strftime('%d/%m/%Y')} hasta "
                 f"{f_fin_str}: tasa acumulada {r_ta['tramo2']['tasa_pct']:.2f}%")
        st.write(f"**Total final:** {formato_moneda(r_ta['total'])}")
    else:
        st.write(f"**Tasa acumulada:** {r_ta['tasa_pct']:.2f}%")

with st.expander("Liquidación"):
    if cap_usado:
        f_dem = f_demanda_usada.strftime('%d/%m/%Y')
        lineas_ta = [
            f"1. Capital Histórico {formato_moneda(monto_c)}",
            f"2. Intereses Tasa Activa BNA desde {f_ini_str} hasta interposición de demanda ({f_dem}) "
            f"(tasa acumulada: {r_ta['tramo1']['tasa_pct']:.2f}%) {formato_moneda(r_ta['interes_tramo1'])}",
            f"3. Capital Capitalizado al {f_dem} (Art. 770 inc. b CCyC) {formato_moneda(r_ta['capital_capitalizado'])}",
            f"4. Intereses Tasa Activa BNA desde {f_dem} hasta {f_fin_str} "
            f"(tasa acumulada: {r_ta['tramo2']['tasa_pct']:.2f}%) {formato_moneda(r_ta['total'] - r_ta['capital_capitalizado'])}",
        ]
    else:
        lineas_ta = [
            f"1. Capital Histórico {formato_moneda(monto_c)}",
            f"2. Intereses Tasa Activa BNA desde {f_ini_str} hasta {f_fin_str} "
            f"(tasa acumulada: {r_ta['tasa_pct']:.2f}%) {formato_moneda(r_ta['total'] - monto_c)}",
        ]
    txt_ta = texto_liq_generico(monto_c, f_ini_c, f_fin_c, lineas_ta, r_ta['total'])
    st.text_area("", txt_ta, height=max(300, txt_ta.count('\n') * 28 + 100), key="ta_liq_ta")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════
# BLOQUE 5 — RIPTE + 6% (Barrios)
# ═══════════════════════════════════════════════════════════════
st.markdown("**RIPTE + 6% (Barrios)**")
st.markdown(
    f"<div style='background:#5b7a9e;padding:8px 16px;margin-bottom:8px;"
    f"display:flex;justify-content:space-between;align-items:center;border-radius:4px'>"
    f"<span style='color:white;font-weight:600'>Total RIPTE + 6%</span>"
    f"<span style='color:white;font-family:monospace;font-size:16px;font-weight:800'>"
    f"{formato_moneda(r_ripte['total'])}</span></div>",
    unsafe_allow_html=True
)

with st.expander("Detalle"):
    st.write(f"**RIPTE origen ({mes_anio(f_ini_c)}):** {r_ripte['ripte_origen']:.2f}")
    st.write(f"**RIPTE último ({mes_anio(r_ripte['ripte_calculo_fecha'])}):** {r_ripte['ripte_calculo']:.2f}")
    st.write(f"**Coeficiente:** {r_ripte['coef']:.6f} ({r_ripte['pct_variacion']:.2f}%)")
    st.write(f"**Capital indexado:** {formato_moneda(r_ripte['capital_indexado'])}")
    st.write(f"**Interés 6% simple ({r_ripte['dias']} días):** {formato_moneda(r_ripte['interes_6'])}")

with st.expander("Liquidación"):
    linea_act_ripte = (
        f"2. Capital Actualizado mediante RIPTE "
        f"({r_ripte['ripte_calculo_fecha'].strftime('%m/%Y')}: {r_ripte['ripte_calculo']:.2f} / "
        f"{f_ini_c.strftime('%m/%Y')}: {r_ripte['ripte_origen']:.2f} — "
        f"Coef. {r_ripte['coef']:.4f} — {r_ripte['pct_variacion']:.2f}%) "
        f"{formato_moneda(r_ripte['capital_indexado'])}"
    )
    lineas_ripte = [
        f"1. Capital Histórico {formato_moneda(monto_c)}",
        linea_act_ripte,
        f"3. Interés puro del 6% anual desde {f_ini_str} hasta {f_fin_str} {formato_moneda(r_ripte['interes_6'])}",
    ]
    txt_ripte = texto_liq_generico(monto_c, f_ini_c, f_fin_c, lineas_ripte, r_ripte['total'])
    st.text_area("", txt_ripte, height=max(300, txt_ripte.count('\n') * 28 + 100), key="ta_liq_ripte")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════
# BLOQUE 6 — CER + 3% (referencia)
# ═══════════════════════════════════════════════════════════════
if r_cer:
    st.markdown("**CER diario + 3% simple** *(referencia)*")
    st.markdown(
        f"<div style='background:#6c3483;padding:7px 16px;margin-bottom:8px;"
        f"display:flex;justify-content:space-between;align-items:center;border-radius:4px'>"
        f"<span style='color:white;font-size:12px;font-weight:600'>Total CER + 3%</span>"
        f"<span style='color:white;font-family:monospace;font-size:15px;font-weight:800'>"
        f"{formato_moneda(r_cer['total'])}</span></div>",
        unsafe_allow_html=True
    )

    with st.expander("Detalle"):
        st.write(f"**CER origen ({f_ini_str}):** {r_cer['cer_origen']:.6f}")
        st.write(f"**CER cálculo ({r_cer['cer_calculo_fecha'].strftime('%d/%m/%Y')}):** {r_cer['cer_calculo']:.6f}")
        st.write(f"**Coeficiente:** {r_cer['coef']:.6f} ({r_cer['pct_variacion']:.2f}%)")
        st.write(f"**Capital indexado:** {formato_moneda(r_cer['capital_indexado'])}")
        st.write(f"**Interés 3% simple ({r_cer['dias']} días):** {formato_moneda(r_cer['interes_3'])}")

    with st.expander("Liquidación"):
        linea_act_cer = (
            f"2. Capital Actualizado mediante CER "
            f"({r_cer['cer_calculo_fecha'].strftime('%d/%m/%Y')}: {r_cer['cer_calculo']:.6f} / "
            f"{r_cer['cer_origen_fecha'].strftime('%d/%m/%Y')}: {r_cer['cer_origen']:.6f} — "
            f"Coef. {r_cer['coef']:.6f} — {r_cer['pct_variacion']:.2f}%) {formato_moneda(r_cer['capital_indexado'])}"
        )
        lineas_cer = [
            f"1. Capital Histórico {formato_moneda(monto_c)}",
            linea_act_cer,
            f"3. Interés puro del 3% anual desde {f_ini_str} hasta {f_fin_str} {formato_moneda(r_cer['interes_3'])}",
        ]
        txt_cer = texto_liq_generico(monto_c, f_ini_c, f_fin_c, lineas_cer, r_cer['total'])
        st.text_area("", txt_cer, height=max(300, txt_cer.count('\n') * 28 + 100), key="ta_liq_cer")

# ═══════════════════════════════════════════════════════════════
# PDF
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
if st.button("🖨️ Generar PDF", key="act_pdf_btn"):
    st.session_state['act_pdf'] = True

if st.session_state.get('act_pdf'):
    if r['metodo'] == 'CER+IPC':
        det_html_ipc = f"""
        <tr><td>CER origen ({f_ini_c.strftime('%m/%Y')})</td><td class="num">{r['cer_origen']:.6f}</td></tr>
        <tr><td>CER nov-2016</td><td class="num">{r['cer_nov2016']:.6f}</td></tr>
        <tr><td>Coef. CER</td><td class="num">{r['coef_cer']:.6f}</td></tr>
        <tr><td>IPC base 100 → {mes_anio(r['ipc_ultimo_fecha'])}: {r['ipc_ultimo']:.2f}</td><td class="num">Coef. IPC: {r['coef_ipc']:.6f}</td></tr>
        <tr><td>Capital indexado</td><td class="num">{formato_moneda(r['capital_indexado'])}</td></tr>
        <tr><td>Interés 3% simple ({r['dias']} días)</td><td class="num">{formato_moneda(r['interes_3'])}</td></tr>
        """
    else:
        det_html_ipc = f"""
        <tr><td>IPC origen ({mes_anio(f_ini_c)})</td><td class="num">{r['ipc_origen']:.2f}</td></tr>
        <tr><td>IPC último ({mes_anio(r['ipc_ultimo_fecha'])})</td><td class="num">{r['ipc_ultimo']:.2f}</td></tr>
        <tr><td>Coeficiente</td><td class="num">{r['coef']:.6f} ({r['pct_variacion']:.2f}%)</td></tr>
        <tr><td>Capital indexado</td><td class="num">{formato_moneda(r['capital_indexado'])}</td></tr>
        <tr><td>Interés 3% simple ({r['dias']} días)</td><td class="num">{formato_moneda(r['interes_3'])}</td></tr>
        """

    if cap_usado:
        det_html_tp = f"""
        <tr><td>Capital histórico</td><td class="num">{formato_moneda(r_tp['capital_historico'])}</td></tr>
        <tr><td>Tramo 1 (hasta demanda {f_demanda_usada.strftime('%d/%m/%Y')})</td><td class="num">tasa {r_tp['tramo1']['tasa_pct']:.4f}%</td></tr>
        <tr><td>Capital capitalizado</td><td class="num">{formato_moneda(r_tp['capital_capitalizado'])}</td></tr>
        <tr><td>Tramo 2 (desde demanda hasta cálculo)</td><td class="num">tasa {r_tp['tramo2']['tasa_pct']:.4f}%</td></tr>
        """
        det_html_ta = f"""
        <tr><td>Capital histórico</td><td class="num">{formato_moneda(r_ta['capital_historico'])}</td></tr>
        <tr><td>Tramo 1 (hasta demanda {f_demanda_usada.strftime('%d/%m/%Y')})</td><td class="num">tasa {r_ta['tramo1']['tasa_pct']:.2f}%</td></tr>
        <tr><td>Capital capitalizado</td><td class="num">{formato_moneda(r_ta['capital_capitalizado'])}</td></tr>
        <tr><td>Tramo 2 (desde demanda hasta cálculo)</td><td class="num">tasa {r_ta['tramo2']['tasa_pct']:.2f}%</td></tr>
        """
    else:
        det_html_tp = f"""
        <tr><td>T₀ ({r_tp['T0_fecha'].strftime('%d/%m/%Y')})</td><td class="num">{r_tp['T0']:.6f}</td></tr>
        <tr><td>Tₘ ({r_tp['Tm_fecha'].strftime('%d/%m/%Y')})</td><td class="num">{r_tp['Tm']:.6f}</td></tr>
        <tr><td>Tasa período</td><td class="num">{r_tp['tasa_pct']:.4f}%</td></tr>
        """
        det_html_ta = f"""
        <tr><td>Tasa acumulada</td><td class="num">{r_ta['tasa_pct']:.2f}%</td></tr>
        """

    det_html_ripte = f"""
    <tr><td>RIPTE origen ({mes_anio(f_ini_c)})</td><td class="num">{r_ripte['ripte_origen']:.2f}</td></tr>
    <tr><td>RIPTE último ({mes_anio(r_ripte['ripte_calculo_fecha'])})</td><td class="num">{r_ripte['ripte_calculo']:.2f}</td></tr>
    <tr><td>Coeficiente</td><td class="num">{r_ripte['coef']:.6f} ({r_ripte['pct_variacion']:.2f}%)</td></tr>
    <tr><td>Capital indexado</td><td class="num">{formato_moneda(r_ripte['capital_indexado'])}</td></tr>
    <tr><td>Interés 6% simple ({r_ripte['dias']} días)</td><td class="num">{formato_moneda(r_ripte['interes_6'])}</td></tr>
    """

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
@page {{size:A4;margin:1.5cm}}
@media print {{.no-print {{display:none}} body {{background:white}}}}
* {{box-sizing:border-box;margin:0;padding:0}}
body {{font-family:Arial,sans-serif;font-size:10px;background:#eee;padding:12px}}
.container {{background:white;padding:18px;max-width:760px;margin:0 auto}}
h1 {{font-size:15px;text-align:center;border-bottom:2px solid #000;padding-bottom:6px;margin-bottom:12px}}
h2 {{font-size:11px;font-weight:700;margin:10px 0 4px 0;text-transform:uppercase;color:#333}}
table {{width:100%;border-collapse:collapse;margin-bottom:10px}}
td,th {{padding:4px 7px;border:1px solid #ccc;font-size:9.5px}}
th {{background:#333;color:#fff;font-weight:600;text-align:left}}
.num {{text-align:right}}
.footer {{text-align:center;font-size:8px;color:#888;margin-top:14px;border-top:1px solid #ddd;padding-top:6px}}
.btn {{background:#333;color:white;border:none;padding:7px 16px;cursor:pointer;font-size:12px;font-weight:600;margin-bottom:10px}}
</style></head><body>
<button class="btn no-print" onclick="window.print()">🖨️ IMPRIMIR / GUARDAR PDF</button>
<div class="container">
<h1>ACTUALIZACIÓN E INTERESES</h1>

<table>
<tr><th colspan="2">DATOS</th></tr>
<tr><td>Monto histórico</td><td class="num"><strong>{formato_moneda(monto_c)}</strong></td></tr>
<tr><td>Período</td><td>{f_ini_str} al {f_fin_str}</td></tr>
{f"<tr><td>Capitaliza desde demanda</td><td>{f_demanda_usada.strftime('%d/%m/%Y')} (Art. 770 inc. b CCyC)</td></tr>" if cap_usado else ""}
</table>

<h2>1. IPC + 3% SIMPLE (Art. 276 LCT)</h2>
<table>
<tr><th colspan="2">Detalle</th></tr>
{det_html_ipc}
<tr><th>TOTAL</th><th class="num">{formato_moneda(r['total'])}</th></tr>
</table>

<h2>2. Art. 55 inc. c) LML — 67% de IPC + 3% (piso)</h2>
<table>
<tr><td>IPC + 3% — techo (inc. b)</td><td class="num">{formato_moneda(r55_show['ipc_3'])}</td></tr>
<tr><td>67% de IPC + 3% — piso (inc. c)</td><td class="num">{formato_moneda(r55_show['piso_67'])}</td></tr>
<tr><td>Tasa Pasiva BCRA (inc. a)</td><td class="num">{formato_moneda(r55_show['tasa_pasiva'])}</td></tr>
<tr><th>TOTAL (inc. c — piso)</th><th class="num">{formato_moneda(r55_show['piso_67'])}</th></tr>
</table>
<p style="font-size:8.5px;color:#555;margin-bottom:8px">
Se exponen los tres valores. El juez puede apartarse de la banda legal por razones de inconstitucionalidad.
</p>

<h2>3. Tasa Pasiva BCRA{" — con capitalización Art. 770 inc. b CCyC" if cap_usado else " (Res. 45/26)"}</h2>
<table>
{det_html_tp}
<tr><th>TOTAL</th><th class="num">{formato_moneda(r_tp['total'])}</th></tr>
</table>

<h2>4. Tasa Activa BNA{" — con capitalización Art. 770 inc. b CCyC" if cap_usado else " (Art. 12 inc. b LRT)"}</h2>
<table>
{det_html_ta}
<tr><th>TOTAL</th><th class="num">{formato_moneda(r_ta['total'])}</th></tr>
</table>

<h2>5. RIPTE + 6% (Barrios)</h2>
<table>
{det_html_ripte}
<tr><th>TOTAL</th><th class="num">{formato_moneda(r_ripte['total'])}</th></tr>
</table>

{f'''<h2>6. CER + 3% simple (referencia)</h2>
<table>
<tr><td>CER origen ({f_ini_str})</td><td class="num">{r_cer["cer_origen"]:.6f}</td></tr>
<tr><td>CER cálculo ({r_cer["cer_calculo_fecha"].strftime("%d/%m/%Y")})</td><td class="num">{r_cer["cer_calculo"]:.6f}</td></tr>
<tr><td>Coeficiente</td><td class="num">{r_cer["coef"]:.6f} ({r_cer["pct_variacion"]:.2f}%)</td></tr>
<tr><td>Capital indexado</td><td class="num">{formato_moneda(r_cer["capital_indexado"])}</td></tr>
<tr><td>Interés 3% simple ({r_cer["dias"]} días)</td><td class="num">{formato_moneda(r_cer["interes_3"])}</td></tr>
<tr><th>TOTAL</th><th class="num">{formato_moneda(r_cer["total"])}</th></tr>
</table>''' if r_cer else ''}

<div class="footer">Tribunal de Trabajo N° 2 de Quilmes — {date.today().strftime('%d/%m/%Y')}</div>
</div></body></html>"""

    st.components.v1.html(html, height=1400, scrolling=True)
