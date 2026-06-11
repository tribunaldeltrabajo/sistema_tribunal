#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CALCULADORA DE AUDIENCIAS
LRT (Ley 24.557) y Despidos (Ley 20.744)
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import os
from utils.navegacion import mostrar_sidebar_navegacion
from utils.funciones_comunes import (
    safe_parse_date, days_in_month, redondear,
    numero_a_letras, formato_moneda, get_mes_nombre
)
from utils.motor_actualizacion import (
    cargar_todo, calcular_ipc_cer_3,
    calcular_bcra, calcular_art55, calcular_tasa_activa
)

mostrar_sidebar_navegacion('audiencias')

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR   = os.path.join(BASE_DIR, "data")
PATH_PISOS = os.path.join(DATA_DIR, "dataset_pisos.csv")

def mes_anio(fecha):
    return f"{get_mes_nombre(fecha.month)} {fecha.year}"

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
    DS['df_pisos'] = df_pisos
    return DS

try:
    DS = cargar_datasets()
except Exception as e:
    st.error(f"Error al cargar datasets: {e}")
    st.stop()

# Limpiar session_state viejo que no tiene 'tasa'
if 'desp_res' in st.session_state and 'tasa' in st.session_state.get('desp_res', {}):
    del st.session_state['desp_res']  # limpiar versión vieja con tasa
if 'lrt_res' in st.session_state and 'tasa' not in st.session_state.get('lrt_res', {}):
    del st.session_state['lrt_res']

def get_piso(fecha_pmi):
    df_pisos = DS['df_pisos']
    candidate = None
    for _, r in df_pisos.iterrows():
        d0, d1 = r['desde'], r['hasta']
        if pd.isna(d1) or d1 is None:
            if fecha_pmi >= d0: candidate = (float(r['piso']), r['resol'])
        else:
            if d0 <= fecha_pmi <= d1: return (float(r['piso']), r['resol'])
    return candidate if candidate else (None, "")

def det_ipc_html(ipc, fecha_origen):
    if ipc['metodo'] == 'CER+IPC':
        return f"""
        <tr><td>CER origen ({fecha_origen.strftime('%m/%Y')})</td><td class="num">{ipc['cer_origen']:.6f}</td></tr>
        <tr><td>CER nov-2016</td><td class="num">{ipc['cer_nov2016']:.6f}</td></tr>
        <tr><td>Coef. CER</td><td class="num">{ipc['coef_cer']:.6f}</td></tr>
        <tr><td>Coef. IPC (base→{ipc['ipc_ultimo']:.2f})</td><td class="num">{ipc['coef_ipc']:.6f}</td></tr>
        """
    else:
        return f"""
        <tr><td>IPC origen ({mes_anio(fecha_origen)})</td><td class="num">{ipc['ipc_origen']:.2f}</td></tr>
        <tr><td>IPC último ({mes_anio(ipc['ipc_ultimo_fecha'])})</td><td class="num">{ipc['ipc_ultimo']:.2f}</td></tr>
        <tr><td>Coeficiente</td><td class="num">{ipc['coef']:.6f} ({ipc['pct_variacion']:.2f}%)</td></tr>
        """

def renglones_color(variantes):
    colores = ['#c0392b', '#1a5276', '#7d6608', '#1e8449']
    for idx, (label, monto) in enumerate(variantes):
        color = colores[min(idx, len(colores)-1)]
        st.markdown(
            f"<div style='background:{color};padding:8px 16px;margin-bottom:4px;"
            f"display:flex;justify-content:space-between;align-items:center'>"
            f"<span style='font-weight:600;color:white;font-size:13px'>{label}</span>"
            f"<span style='font-family:monospace;font-size:16px;font-weight:800;color:white'>"
            f"{formato_moneda(monto)}</span></div>",
            unsafe_allow_html=True
        )

def bloque_art55(r55, key_bcra, capital, pmi, fcalc):
    usar_bcra = st.checkbox(
        "Método BCRA (CER + 3% compuesto)", value=False, key=key_bcra,
        help="Usa CER diario + 3% compuesto, igual a la calculadora oficial del BCRA."
    )
    if usar_bcra:
        r55 = calcular_art55(capital, pmi, fcalc,
                             DS['df_ipc'], DS['df_cer'], DS['datos_tp'],
                             usar_bcra=True, datos_cer_xls=DS['datos_cer_xls'])
    st.markdown("**Art. 55 Ley 27.802**")
    aplica = r55['aplica']
    lbl_techo = 'CER + 3% — techo (inc. b)' if usar_bcra else 'IPC + 3% — techo (inc. b)'
    lbl_piso  = '67% CER+3% — piso (inc. c)' if usar_bcra else '67% IPC+3% — piso (inc. c)'
    for label, valor, key in sorted([
        ('Tasa Pasiva BCRA (inc. a)', r55['tasa_pasiva'], 'tasa_pasiva'),
        (lbl_techo,                   r55['ipc_3'],       'techo'),
        (lbl_piso,                    r55['piso_67'],     'piso'),
    ], key=lambda x: -x[1]):
        bg = '#c0392b' if key == aplica else '#555'
        marca = " ✓" if key == aplica else ""
        st.markdown(
            f"<div style='background:{bg};padding:6px 14px;margin-bottom:3px;"
            f"display:flex;justify-content:space-between'>"
            f"<span style='color:white;font-size:11px;font-weight:600'>{label}{marca}</span>"
            f"<span style='color:white;font-family:monospace;font-weight:800'>{formato_moneda(valor)}</span>"
            f"</div>", unsafe_allow_html=True
        )
    return r55

# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────

st.markdown("# ⚖️ CALCULADORA DE AUDIENCIAS")
st.markdown("---")

tab_lrt, tab_despidos, tab_info = st.tabs(["🧮 LRT", "📋 Despidos", "ℹ️ Información"])


# ═══════════════════════════════════════════════════════════════
# TAB LRT
# ═══════════════════════════════════════════════════════════════

with tab_lrt:
    st.subheader("Indemnización LRT — Ley 24.557")

    # Inputs arriba — igual que relatoría
    c1, c2 = st.columns(2)
    with c1:
        pmi = st.date_input("Fecha PMI", value=date(2020,1,1),
            min_value=date(2002,1,1), max_value=date.today(),
            format="DD/MM/YYYY", key="lrt_pmi")
    with c2:
        fecha_calculo_lrt = st.date_input("Fecha de cálculo", value=date.today(),
            format="DD/MM/YYYY", key="lrt_fecha_calc")

    c3, c4, c5 = st.columns(3)
    with c3:
        ibm = st.number_input("IBM actualizado ($)", min_value=0.01,
            value=500000.0, step=1000.0, format="%.2f", key="lrt_ibm",
            help="IBM ya calculado por el módulo IBM (actualizado por RIPTE)")
    with c4:
        edad = st.number_input("Edad", min_value=18, max_value=100, value=45, key="lrt_edad")
    with c5:
        incapacidad = st.number_input("Incapacidad (%)", min_value=0.01,
            max_value=100.0, value=30.0, step=0.5, format="%.2f", key="lrt_inc")

    art3 = st.checkbox("Incluir 20% art. 3 Ley 26.773", value=True, key="lrt_art3")
    calcular_lrt = st.button("⚡ CALCULAR", use_container_width=True, type="primary", key="btn_lrt")

    if calcular_lrt:
        if pmi >= fecha_calculo_lrt:
            st.error("La fecha PMI debe ser anterior a la fecha de cálculo.")
        else:
            capital_formula = float(redondear(
                Decimal(str(ibm)) * 53
                * (Decimal('65') / Decimal(str(edad)))
                * (Decimal(str(incapacidad)) / 100)
            ))
            piso_monto, piso_norma = get_piso(pmi)
            if piso_monto:
                piso_prop = float(redondear(Decimal(str(piso_monto)) * Decimal(str(incapacidad)) / 100))
                piso_aplicado = capital_formula < piso_prop
                capital_base  = piso_prop if piso_aplicado else capital_formula
                piso_txt = (f"Se aplica piso {piso_norma}: {formato_moneda(piso_prop)}"
                            if piso_aplicado else f"Supera piso {piso_norma}: {formato_moneda(piso_prop)}")
            else:
                capital_base = capital_formula; piso_aplicado = False
                piso_txt = "Sin piso disponible para la fecha"

            adicional_20  = float(redondear(Decimal(str(capital_base)) * Decimal('0.20'))) if art3 else 0.0
            capital_total = float(redondear(Decimal(str(capital_base)) + Decimal(str(adicional_20))))

            res_ipc  = calcular_ipc_cer_3(capital_total, pmi, fecha_calculo_lrt, DS['df_ipc'], DS['df_cer'])
            res_tasa = calcular_tasa_activa(capital_total, pmi, fecha_calculo_lrt, DS['df_tasa'])
            res_55   = calcular_art55(capital_total, pmi, fecha_calculo_lrt,
                                      DS['df_ipc'], DS['df_cer'], DS['datos_tp'])

            st.session_state['lrt_res'] = {
                'capital_formula': capital_formula, 'capital_base': capital_base,
                'piso_aplicado': piso_aplicado, 'piso_txt': piso_txt,
                'adicional_20': adicional_20, 'capital_total': capital_total,
                'ipc': res_ipc, 'tasa': res_tasa, 'art55': res_55,
                'pmi': pmi, 'fecha_calculo': fecha_calculo_lrt,
                'ibm': ibm, 'edad': edad, 'incapacidad': incapacidad, 'art3': art3,
            }

    if 'lrt_res' in st.session_state:
        r   = st.session_state['lrt_res']
        ipc = r['ipc']; tasa = r.get('tasa', {'total': 0, 'tasa_pct': 0}); r55 = r['art55']

        label_piso = " ⚠️ piso" if r['piso_aplicado'] else ""
        st.markdown(f"**Capital fórmula:** {formato_moneda(r['capital_formula'])}")
        st.caption(r['piso_txt'])
        if r['art3']:
            st.markdown(f"**20% art. 3:** {formato_moneda(r['adicional_20'])}")
        st.markdown(
            f"<div style='margin:8px 0 12px 0'>"
            f"<span style='font-size:1.3rem;font-weight:700;color:#c0392b'>"
            f"CAPITAL BASE: {formato_moneda(r['capital_total'])}{label_piso}</span></div>",
            unsafe_allow_html=True
        )
        st.markdown("---")

        # Renglones de color
        variantes = sorted([
            ('IPC + 3% (Art. 276 LCT)', ipc['total']),
            ('Tasa Activa BNA (Art. 12 inc. b LRT conf. Art. 11 Ley 27.348)', tasa['total']),
        ], key=lambda x: -x[1])
        renglones_color(variantes)

        # Art. 55
        st.markdown("---")
        r55 = bloque_art55(r55, "lrt_bcra_55", r['capital_total'], r['pmi'], r['fecha_calculo'])
    else:
        st.info("👈 Completá los datos y presioná CALCULAR")

    # ── PDF LRT ──
    if 'lrt_res' in st.session_state:
        st.markdown("---")
        if st.button("🖨️ Generar PDF — LRT", key="pdf_lrt_btn"):
            st.session_state['mostrar_pdf_lrt'] = True

        if st.session_state.get('mostrar_pdf_lrt'):
            r = st.session_state['lrt_res']
            ipc = r['ipc']; tasa = r.get('tasa', {'total': 0, 'tasa_pct': 0}); r55 = r['art55']
            ipc_mayor = ipc['total'] >= tasa['total']
            aplica = r55['aplica']

            filas_55 = sorted([
                ('Tasa Pasiva BCRA (inc. a)', r55['tasa_pasiva'], 'tasa_pasiva'),
                ('IPC + 3% — techo (inc. b)', r55['ipc_3'],       'techo'),
                ('67% IPC+3% — piso (inc. c)', r55['piso_67'],    'piso'),
            ], key=lambda x: -x[1])
            filas_55_html = "".join(
                f"<tr style='background:{'#c0392b' if k==aplica else '#f5f5f5'};color:{'white' if k==aplica else 'black'}'>"
                f"<td>{lbl}{' ✓ APLICA' if k==aplica else ''}</td>"
                f"<td class='num' style='font-weight:700'>{formato_moneda(v)}</td></tr>"
                for lbl, v, k in filas_55
            )

            html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
@page {{size:A4;margin:1.5cm}}
@media print {{.no-print {{display:none}} body {{background:white}}}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Arial,sans-serif;font-size:10px;background:#eee;padding:12px}}
.container{{background:white;padding:18px;max-width:760px;margin:0 auto}}
h1{{font-size:15px;text-align:center;border-bottom:2px solid #000;padding-bottom:6px;margin-bottom:4px}}
h2{{font-size:10px;font-weight:700;text-transform:uppercase;margin:10px 0 4px 0;color:#333}}
.sub{{text-align:center;font-size:9px;color:#444;margin-bottom:12px}}
table{{width:100%;border-collapse:collapse;margin-bottom:10px}}
td,th{{padding:4px 7px;border:1px solid #bbb;font-size:9.5px}}
th{{background:#333;color:#fff;font-weight:600;text-align:left}}
.num{{text-align:right}}
.cap-box{{border:2px solid #000;padding:8px;text-align:center;margin:10px 0}}
.cap-box .val{{font-size:20px;font-weight:800}}
.footer{{text-align:center;font-size:8px;color:#777;margin-top:12px;border-top:1px solid #ccc;padding-top:6px}}
.btn{{background:#333;color:white;border:none;padding:7px 16px;cursor:pointer;font-size:12px;font-weight:600;margin-bottom:10px}}
</style></head><body>
<button class="btn no-print" onclick="window.print()">🖨️ IMPRIMIR / GUARDAR PDF</button>
<div class="container">
<h1>CÁLCULO INDEMNIZACIÓN — LEY 24.557</h1>
<div class="sub">Fecha de cálculo: {r['fecha_calculo'].strftime('%d/%m/%Y')}</div>
<table>
<tr><th colspan="2">DATOS DEL CASO</th></tr>
<tr><td>Fecha PMI</td><td>{r['pmi'].strftime('%d/%m/%Y')}</td></tr>
<tr><td>IBM (actualizado por RIPTE)</td><td class="num">{formato_moneda(r['ibm'])}</td></tr>
<tr><td>Edad al siniestro</td><td>{r['edad']} años</td></tr>
<tr><td>Incapacidad</td><td>{r['incapacidad']:.2f}%</td></tr>
</table>
<table>
<tr><th colspan="2">FÓRMULA — IBM × 53 × (65/edad) × (inc%/100)</th></tr>
<tr><td>Capital fórmula</td><td class="num">{formato_moneda(r['capital_formula'])}</td></tr>
<tr><td>{r['piso_txt']}</td><td class="num">{formato_moneda(r['capital_base'])}</td></tr>
{"<tr><td>20% art. 3 Ley 26.773</td><td class='num'>" + formato_moneda(r['adicional_20']) + "</td></tr>" if r['art3'] else ""}
</table>
<div class="cap-box"><div style="font-size:9px;font-weight:600;margin-bottom:3px">CAPITAL BASE TOTAL</div>
<div class="val">{formato_moneda(r['capital_total'])}</div></div>
<h2>Art. 55 Ley 27.802 — Juicios en trámite</h2>
<table>
<tr><th>Concepto</th><th class="num">Total</th></tr>
{filas_55_html}
</table>
<p style="font-size:8px;color:#555">Se exponen los tres valores. El juez puede apartarse por inconstitucionalidad.</p>
<h2>IPC + 3% simple (Art. 276 LCT)</h2>
<table>
{det_ipc_html(ipc, r['pmi'])}
<tr><td>Capital indexado</td><td class="num">{formato_moneda(ipc['capital_indexado'])}</td></tr>
<tr><td>Interés 3% simple ({ipc['dias']} días)</td><td class="num">{formato_moneda(ipc['interes_3'])}</td></tr>
</table>
<div class="cap-box">
<div style="font-size:9px;font-weight:600;margin-bottom:3px">IPC + 3% (Art. 276 LCT)</div>
<div class="val">{formato_moneda(ipc['total'])}</div>
</div>
<h2>Tasa Activa BNA (Art. 12 inc. b LRT conf. Art. 11 Ley 27.348)</h2>
<table>
<tr><td>Tasa acumulada</td><td class="num">{tasa['tasa_pct']:.2f}%</td></tr>
</table>
<div class="cap-box">
<div style="font-size:9px;font-weight:600;margin-bottom:3px">TASA ACTIVA BNA</div>
<div class="val">{formato_moneda(tasa['total'])}</div>
</div>
<div class="footer">Tribunal de Trabajo N° 2 de Quilmes — {date.today().strftime('%d/%m/%Y')}</div>
</div></body></html>"""
            st.components.v1.html(html, height=1000, scrolling=True)


# ═══════════════════════════════════════════════════════════════
# TAB DESPIDOS
# ═══════════════════════════════════════════════════════════════

with tab_despidos:
    st.subheader("Despido — Ley 20.744 (LCT)")

    # Inputs arriba
    c1, c2, c3 = st.columns(3)
    with c1:
        f_ingreso = st.date_input("Fecha de ingreso", value=date(2015,1,1),
            min_value=date(1980,1,1), max_value=date.today(),
            format="DD/MM/YYYY", key="desp_ingreso")
    with c2:
        f_despido = st.date_input("Fecha de despido", value=date(2023,6,1),
            min_value=date(1980,1,1), max_value=date.today(),
            format="DD/MM/YYYY", key="desp_despido")
    with c3:
        f_calculo_desp = st.date_input("Fecha de cálculo", value=date.today(),
            format="DD/MM/YYYY", key="desp_calculo")

    c4, c5 = st.columns(2)
    with c4:
        salario = st.number_input("Salario mensual bruto ($)", min_value=0.01,
            value=300000.0, step=1000.0, format="%.2f", key="desp_salario")
    with c5:
        pago_preaviso = st.checkbox("¿Se pagó preaviso?", value=False, key="desp_preaviso")

    calcular_desp = st.button("⚡ CALCULAR", use_container_width=True, type="primary", key="btn_desp")

    if calcular_desp:
        años_raw  = f_despido.year  - f_ingreso.year
        meses_raw = f_despido.month - f_ingreso.month
        if f_despido.day < f_ingreso.day: meses_raw -= 1
        if meses_raw < 0: años_raw -= 1; meses_raw += 12
        años = años_raw + (1 if meses_raw > 3 else 0)
        meses_resto = 0 if meses_raw > 3 else meses_raw

        sal = Decimal(str(salario))
        antig = (sal * Decimal(str(max(años,1)))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if not pago_preaviso:
            meses_preaviso = 1 if años < 5 else 2
            sustit_prev = (sal * Decimal(str(meses_preaviso))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            sac_prev    = (sustit_prev / 12).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            meses_preaviso = 0; sustit_prev = Decimal('0'); sac_prev = Decimal('0')

        dias_mes = days_in_month(f_despido)
        d_trabajados = (sal / Decimal(str(dias_mes)) * Decimal(str(f_despido.day))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if f_despido.day == dias_mes:
            integracion = sac_integ = Decimal('0'); dias_integ = 0
        else:
            dias_integ  = dias_mes - f_despido.day
            integracion = (sal / Decimal(str(dias_mes)) * Decimal(str(dias_integ))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            sac_integ   = (integracion / 12).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if f_despido.month <= 6:
            dias_sac = (f_despido - date(f_despido.year, 1, 1)).days; semestre = "1°"
        else:
            dias_sac = (f_despido - date(f_despido.year, 7, 1)).days; semestre = "2°"
        sac_prop = (sal / 365 * Decimal(str(dias_sac))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        dias_vac = 14 if años_raw < 5 else 21 if años_raw < 10 else 28 if años_raw < 20 else 35
        vacaciones = (sal / 25 * Decimal(str(dias_vac))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        sac_vac    = (vacaciones / 12).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        total_rubros = (antig + sustit_prev + sac_prev + d_trabajados +
                       integracion + sac_integ + sac_prop + vacaciones + sac_vac
                       ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        res_ipc_d = calcular_ipc_cer_3(float(total_rubros), f_despido, f_calculo_desp, DS['df_ipc'], DS['df_cer'])
        res_55_d  = calcular_art55(float(total_rubros), f_despido, f_calculo_desp,
                                   DS['df_ipc'], DS['df_cer'], DS['datos_tp'])
        txt_antig = f"({años} año{'s' if años!=1 else ''})" + (f" y {meses_resto} mes{'es' if meses_resto!=1 else ''}" if meses_resto > 0 else "")

        st.session_state['desp_res'] = {
            'f_ingreso': f_ingreso, 'f_despido': f_despido, 'f_calculo': f_calculo_desp,
            'salario': float(salario), 'años': años, 'meses_resto': meses_resto,
            'txt_antig': txt_antig, 'pago_preaviso': pago_preaviso,
            'meses_preaviso': meses_preaviso, 'dias_vac': dias_vac,
            'rubros': {
                'Antigüedad art. 245':       float(antig),
                'Sustitutiva preaviso':       float(sustit_prev),
                'SAC preaviso':               float(sac_prev),
                'Días trabajados del mes':    float(d_trabajados),
                'Integración mes de despido': float(integracion),
                'SAC integración':            float(sac_integ),
                'SAC proporcional':           float(sac_prop),
                'Vacaciones no gozadas':      float(vacaciones),
                'SAC vacaciones':             float(sac_vac),
            },
            'total_rubros': float(total_rubros),
            'ipc': res_ipc_d, 'art55': res_55_d,
        }

    if 'desp_res' in st.session_state:
        r   = st.session_state['desp_res']
        ipc = r['ipc']; r55 = r['art55']

        for concepto, monto_r in r['rubros'].items():
            if monto_r > 0:
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{concepto}**"); c2.markdown(f"**{formato_moneda(monto_r)}**")

        st.markdown(
            f"<div style='margin:10px 0 12px 0'>"
            f"<span style='font-size:1.3rem;font-weight:700;color:#c0392b'>"
            f"TOTAL: {formato_moneda(r['total_rubros'])}</span></div>",
            unsafe_allow_html=True
        )
        st.markdown("---")

        # Renglones de color
        renglones_color([('IPC + 3% (Art. 276 LCT)', ipc['total'])])

        # Art. 55
        st.markdown("---")
        r55 = bloque_art55(r55, "desp_bcra_55", r['total_rubros'], r['f_despido'], r['f_calculo'])
    else:
        st.info("👈 Completá los datos y presioná CALCULAR")

    # ── PDF Despidos ──
    if 'desp_res' in st.session_state:
        st.markdown("---")
        if st.button("🖨️ Generar PDF — Despidos", key="pdf_desp_btn"):
            st.session_state['mostrar_pdf_desp'] = True

        if st.session_state.get('mostrar_pdf_desp'):
            r   = st.session_state['desp_res']
            ipc = r['ipc']; r55 = r['art55']
            aplica_d = r55['aplica']

            rubros_html = "".join(
                f"<tr><td>{c}</td><td class='num'>{formato_moneda(m)}</td></tr>"
                for c, m in r['rubros'].items() if m > 0
            )
            filas_55_d = sorted([
                ('Tasa Pasiva BCRA (inc. a)', r55['tasa_pasiva'], 'tasa_pasiva'),
                ('IPC + 3% — techo (inc. b)', r55['ipc_3'],       'techo'),
                ('67% IPC+3% — piso (inc. c)', r55['piso_67'],    'piso'),
            ], key=lambda x: -x[1])
            filas_55_d_html = "".join(
                f"<tr style='background:{'#c0392b' if k==aplica_d else '#f5f5f5'};color:{'white' if k==aplica_d else 'black'}'>"
                f"<td>{lbl}{' ✓ APLICA' if k==aplica_d else ''}</td>"
                f"<td class='num' style='font-weight:700'>{formato_moneda(v)}</td></tr>"
                for lbl, v, k in filas_55_d
            )

            html_d = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
@page {{size:A4;margin:1.5cm}}
@media print {{.no-print {{display:none}} body {{background:white}}}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Arial,sans-serif;font-size:10px;background:#eee;padding:12px}}
.container{{background:white;padding:18px;max-width:760px;margin:0 auto}}
h1{{font-size:15px;text-align:center;border-bottom:2px solid #000;padding-bottom:6px;margin-bottom:4px}}
h2{{font-size:10px;font-weight:700;text-transform:uppercase;margin:10px 0 4px 0;color:#333}}
.sub{{text-align:center;font-size:9px;color:#444;margin-bottom:12px}}
table{{width:100%;border-collapse:collapse;margin-bottom:10px}}
td,th{{padding:4px 7px;border:1px solid #bbb;font-size:9.5px}}
th{{background:#333;color:#fff;font-weight:600;text-align:left}}
.num{{text-align:right}}
.total-box{{border:2px solid #000;padding:8px;text-align:center;margin:10px 0}}
.total-box .val{{font-size:20px;font-weight:800}}
.footer{{text-align:center;font-size:8px;color:#777;margin-top:12px;border-top:1px solid #ccc;padding-top:6px}}
.btn{{background:#333;color:white;border:none;padding:7px 16px;cursor:pointer;font-size:12px;font-weight:600;margin-bottom:10px}}
</style></head><body>
<button class="btn no-print" onclick="window.print()">🖨️ IMPRIMIR / GUARDAR PDF</button>
<div class="container">
<h1>LIQUIDACIÓN POR DESPIDO — LEY 20.744</h1>
<div class="sub">Fecha de cálculo: {r['f_calculo'].strftime('%d/%m/%Y')}</div>
<table>
<tr><th colspan="2">DATOS</th></tr>
<tr><td>Fecha de ingreso</td><td>{r['f_ingreso'].strftime('%d/%m/%Y')}</td></tr>
<tr><td>Fecha de despido</td><td>{r['f_despido'].strftime('%d/%m/%Y')}</td></tr>
<tr><td>Antigüedad</td><td>{r['txt_antig']}</td></tr>
<tr><td>Salario mensual bruto</td><td class="num">{formato_moneda(r['salario'])}</td></tr>
<tr><td>Preaviso</td><td>{"Abonado" if r['pago_preaviso'] else f"No abonado — {r['meses_preaviso']} mes/es"}</td></tr>
</table>
<table>
<tr><th>Concepto</th><th class="num">Importe</th></tr>
{rubros_html}
</table>
<div class="total-box"><div style="font-size:9px;font-weight:600;margin-bottom:3px">INDEMNIZACIÓN TOTAL</div>
<div class="val">{formato_moneda(r['total_rubros'])}</div></div>
<h2>IPC + 3% simple (desde fecha de despido)</h2>
<table>
{det_ipc_html(ipc, r['f_despido'])}
<tr><td>Capital indexado</td><td class="num">{formato_moneda(ipc['capital_indexado'])}</td></tr>
<tr><td>Interés 3% simple ({ipc['dias']} días)</td><td class="num">{formato_moneda(ipc['interes_3'])}</td></tr>
</table>
<div class="total-box"><div style="font-size:9px;font-weight:600;margin-bottom:3px">IPC + 3% (Art. 276 LCT)</div>
<div class="val">{formato_moneda(ipc['total'])}</div></div>
<h2>Art. 55 Ley 27.802 — Juicios en trámite</h2>
<table>
<tr><th>Concepto</th><th class="num">Total</th></tr>
{filas_55_d_html}
</table>
<p style="font-size:8px;color:#555">Se exponen los tres valores. El juez puede apartarse por inconstitucionalidad.</p>
<div class="total-box" style="border:3px solid #000;margin-top:12px">
<div style="font-size:9px;font-weight:600;margin-bottom:3px">{r55['label_aplica']}</div>
<div class="val">{formato_moneda(r55['valor_aplica'])}</div>
</div>
<div class="footer">Tribunal de Trabajo N° 2 de Quilmes — {date.today().strftime('%d/%m/%Y')}</div>
</div></body></html>"""
            st.components.v1.html(html_d, height=1000, scrolling=True)


# ═══════════════════════════════════════════════════════════════
# TAB INFORMACIÓN
# ═══════════════════════════════════════════════════════════════

with tab_info:
    st.markdown("""
## CALCULADORA DE AUDIENCIAS — DOCUMENTACIÓN TÉCNICA

---

## I. INDEMNIZACIÓN POR ACCIDENTE DE TRABAJO — LEY 24.557 (LRT)

### 1. Ingreso Base Mensual (IBM)

El art. 12 de la Ley 24.557 define el **Ingreso Base Mensual** como la cantidad que resulte de dividir la suma total de las remuneraciones sujetas a cotización correspondientes a los doce meses anteriores a la primera manifestación invalidante (o al tiempo de prestación de servicios si fuera menor), por el número de días corridos del período.

Conforme el art. 8° de la Ley 24.557, los importes por incapacidad laboral permanente se ajustan semestralmente según la variación del índice **RIPTE** (Remuneraciones Imponibles Promedio de los Trabajadores Estables), publicado por la Secretaría de Seguridad Social. El IBM actualizado por RIPTE se calcula en el módulo específico del sistema y se ingresa aquí como dato ya procesado.

### 2. Fórmula indemnizatoria — Art. 14 ap. 2 inc. a) Ley 24.557

Declarado el carácter definitivo de la Incapacidad Laboral Permanente Parcial (hasta el 50%), la indemnización de pago único se calcula:

```
C = IBM × 53 × (65 / edad) × (incapacidad / 100)
```

donde:
- **IBM**: Ingreso Base Mensual actualizado por RIPTE
- **53**: multiplicador legal (art. 14 ap. 2 inc. a LRT, conf. Dec. 1278/2000)
- **65**: edad de referencia legal
- **edad**: edad del damnificado a la fecha de la PMI

### 3. Pisos indemnizatorios (SRT)

La SRT establece mediante resoluciones periódicas el piso mínimo que no puede ser inferior a determinado monto por el porcentaje de ILP, en virtud de la variación del RIPTE. Para el período marzo–agosto 2026 el piso es de **$ 97.502.420** por el porcentaje de ILP (Res. SRT 15/2026). El sistema verifica automáticamente si el capital fórmula supera el piso vigente a la fecha de la PMI y aplica el mayor.

Fuente: [Superintendencia de Riesgos del Trabajo](https://www.srt.gob.ar)

### 4. Adicional art. 3 Ley 26.773

El art. 3 de la Ley 26.773 estableció un adicional de mejora del **20%** sobre la indemnización. Su aplicación es opcional en el sistema dado que su procedencia depende de las circunstancias de cada caso y de la jurisprudencia aplicable.

### 5. Actualización e intereses

#### 5.1. IPC + 3% anual simple — Art. 276 LCT (conf. art. 54 Ley 27.802)

El art. 54 de la Ley 27.802 sustituyó el art. 276 de la LCT estableciendo que los créditos laborales serán actualizados por la variación del **IPC — Nivel General** del INDEC, con más una tasa de interés pura del **3% anual** desde que cada suma sea debida hasta el efectivo pago.

El cálculo se realiza en dos pasos:

**Paso 1 — Actualización por IPC:**
```
Capital actualizado = C × (IPC_cálculo / IPC_PMI)
```
Para períodos anteriores a diciembre de 2016 (base del IPC INDEC), el sistema empalma con el **CER** (Coeficiente de Estabilización de Referencia) del BCRA: CER hasta noviembre de 2016, IPC desde diciembre de 2016 en adelante.

**Paso 2 — Interés puro 3% anual simple:**
```
Interés = Capital actualizado × 0,03 × (días / 365)
Total   = Capital actualizado + Interés
```

Fuentes: [IPC — INDEC](https://www.indec.gob.ar/indec/web/Nivel4-Tema-3-5-31) | [CER diario — BCRA](https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/diar_cer.xls)

#### 5.2. Tasa Activa BNA — Art. 12 inc. b) LRT conf. art. 11 Ley 27.348

El art. 12 inc. b) de la Ley 24.557 (conf. art. 11 Ley 27.348) establece que el IBM devengará durante ese período un interés equivalente al **promedio de la tasa activa cartera general nominal anual vencida a treinta días del Banco de la Nación Argentina**.

El sistema aplica la tasa mensual promedio en forma proporcional a los días de cada mes del período, acumulada en interés simple:

```
Total = Capital × (1 + Σ(tasa_mes_i × días_período_i / días_mes_i) / 100)
```

Fuente: datos publicados por el Banco de la Nación Argentina (cartera general, nominal anual, vencida a 30 días).

### 6. Art. 55 Ley 27.802 — Régimen transitorio para juicios en trámite

El art. 55 de la Ley 27.802 (vigente desde el 6/3/2026) dispone un régimen transitorio para todos los juicios en trámite sin sentencia firme a esa fecha, incluidos los recursos de queja pendientes.

El sistema muestra simultáneamente los **tres valores** previstos en la norma:

**Inc. a) — Tasa Pasiva BCRA:**
Calculada conforme la metodología de la [Resolución 45/26 del BCRA](https://www.bcra.gob.ar/archivos/PDFs/PublicacionesEstadisticas/resolucion-directorio-45-2026-tasa-pasiva-l-27802.pdf):

```
i = ((100 + Tm) / (100 + T0) − 1) × 100
```

donde T0 es el valor de la serie del día **anterior al inicio** del devengamiento y Tm el del día de cierre. Dataset: [diar_ind.xls — BCRA](https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/diar_ind.xls)

**Inc. b) — IPC + 3% (techo):**
Mismo cálculo que el régimen general (punto 5.1). Si la tasa pasiva supera este valor, se aplica este techo.

**Inc. c) — 67% del IPC + 3% (piso):**
```
Total_piso = Total_IPC × 0,67
```
Si la tasa pasiva es inferior a este piso, se aplica el piso.

Se exponen los tres valores para que el juez pueda **apartarse de la banda legal** por razones de inconstitucionalidad. Existe jurisprudencia en desarrollo que declara inconstitucional el art. 55 por conducir el piso mínimo a un resultado que vulnera el principio protectorio (art. 9 LCT).

**Método BCRA (checkbox opcional):** recalcula el Art. 55 usando el CER diario del BCRA con interés compuesto del 3% anual, replicando la metodología de la [calculadora oficial del BCRA](https://www.bcra.gob.ar/calculadora-intereses-creditos-laborales-judicializados/). La diferencia con el método legal (IPC + 3% simple) es inferior al 0,2% en períodos extensos. Dataset: [diar_cer.xls — BCRA](https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/diar_cer.xls)

---

## II. DESPIDO SIN CAUSA — LEY 20.744 (LCT)

### 1. Rubros liquidados

El sistema calcula los siguientes conceptos:

**Antigüedad — art. 245 LCT:**
Un salario mensual por cada año de antigüedad o fracción mayor a tres meses. La fracción superior a tres meses se computa como año completo. Antigüedad mínima computable: un año.
```
Antigüedad = salario × años
```

**Sustitutiva de preaviso — art. 232 LCT:**
Corresponde cuando el preaviso no fue otorgado. Un mes para antigüedades de hasta cinco años; dos meses para antigüedades mayores.
```
Preaviso = salario × meses_preaviso
```

**SAC sobre preaviso — art. 156 LCT:**
```
SAC preaviso = preaviso / 12
```

**Días trabajados del mes:**
```
Días trabajados = (salario / días_del_mes) × día_del_despido
```

**Integración del mes de despido — art. 233 LCT:**
Cuando el despido no opera el último día del mes, corresponde abonar los días restantes.
```
Integración = (salario / días_del_mes) × días_restantes
```

**SAC sobre integración — art. 156 LCT:**
```
SAC integración = integración / 12
```

**SAC proporcional — art. 156 LCT:**
Parte proporcional del SAC por los días trabajados en el semestre en curso.
```
SAC proporcional = (salario / 365) × días_trabajados_en_semestre
```

**Vacaciones no gozadas — art. 156 LCT:**
Según antigüedad: 14 días (hasta 5 años), 21 días (5 a 10 años), 28 días (10 a 20 años), 35 días (más de 20 años).
```
Vacaciones = (salario / 25) × días_vacaciones
SAC vacaciones = vacaciones / 12
```

### 2. Multas e indemnizaciones agravadas

El sistema **no calcula** multas ni agravamientos indemnizatorios (arts. 8, 9 y 15 Ley 24.013; art. 2 Ley 25.323; art. 80 LCT; art. 132 bis LCT, entre otros). Su procedencia depende de las circunstancias fácticas de cada caso y deben ser adicionados por el operador judicial.

### 3. Actualización e intereses

Se aplican los mismos métodos descriptos en el punto I.5, tomando como fecha de origen la del **despido**:

- **IPC + 3% anual simple** (Art. 276 LCT conf. art. 54 Ley 27.802)
- **Art. 55 Ley 27.802** con sus tres valores simultáneos (tasa pasiva, techo y piso)

---

*Sistema desarrollado para el Tribunal de Trabajo N° 2 de Quilmes.*
""")