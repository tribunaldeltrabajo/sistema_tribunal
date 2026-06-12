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
    calcular_art55, calcular_bcra, calcular_tasa_activa
)

mostrar_sidebar_navegacion('actualizacion')

def mes_anio(fecha):
    return f"{get_mes_nombre(fecha.month)} {fecha.year}"

@st.cache_data
def _cargar():
    return cargar_todo()

try:
    DS = _cargar()
except Exception as e:
    st.error(f"Error al cargar datasets: {e}")
    st.stop()

ipc_ult  = DS['df_ipc'].iloc[-1]
tp_fechas = sorted(DS['datos_tp'].keys())

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

if st.button("⚡ CALCULAR", type="primary", use_container_width=True, key="btn_act"):
    if fecha_ini >= fecha_fin:
        st.error("La fecha inicial debe ser anterior a la fecha final.")
    else:
        r_ipc = calcular_ipc_cer_3(monto, fecha_ini, fecha_fin, DS['df_ipc'], DS['df_cer'])
        r_cer = calcular_cer_simple(monto, fecha_ini, fecha_fin, DS['datos_cer_xls'])
        r55   = calcular_art55(monto, fecha_ini, fecha_fin, DS['df_ipc'], DS['df_cer'], DS['datos_tp'])
        r_ta  = calcular_tasa_activa(monto, fecha_ini, fecha_fin, DS['df_tasa'])

        st.session_state['act_res'] = r_ipc
        st.session_state['act_cer'] = r_cer
        st.session_state['act_55']  = r55
        st.session_state['act_ta']  = r_ta

if 'act_res' in st.session_state:
    r    = st.session_state['act_res']
    r55  = st.session_state['act_55']
    r_ta = st.session_state['act_ta']
    label_metodo = "IPC + 3% simple (art. 276 LCT)"

    st.markdown("---")

    # ── Bloque 1: IPC + 3% ──
    st.markdown(f"**{label_metodo}**")
    st.markdown(
        f"<div style='background:#b8952a;padding:8px 16px;margin-bottom:8px;"
        f"display:flex;justify-content:space-between;align-items:center'>"
        f"<span style='color:white;font-weight:600'>Total actualizado</span>"
        f"<span style='color:white;font-family:monospace;font-size:16px;font-weight:800'>"
        f"{formato_moneda(r['total'])}</span></div>",
        unsafe_allow_html=True
    )
    with st.expander("Detalle"):
        if r['metodo'] == 'CER+IPC':
            st.write(f"**Método:** CER + IPC (empalme)")
            st.write(f"**CER origen ({fecha_ini.strftime('%m/%Y')}):** {r['cer_origen']:.6f}")
            st.write(f"**CER nov-2016:** {r['cer_nov2016']:.6f}")
            st.write(f"**Coef. CER:** {r['coef_cer']:.6f}")
            st.write(f"**Coef. IPC:** {r['coef_ipc']:.6f}")
        else:
            st.write(f"**IPC origen ({mes_anio(fecha_ini)}):** {r['ipc_origen']:.2f}")
            st.write(f"**IPC último ({mes_anio(r['ipc_ultimo_fecha'])}):** {r['ipc_ultimo']:.2f}")
        st.write(f"**Coef. total:** {r['coef']:.6f} ({r['pct_variacion']:.2f}%)")
        st.write(f"**Capital indexado:** {formato_moneda(r['capital_indexado'])}")
        st.write(f"**Interés 3% simple ({r['dias']} días):** {formato_moneda(r['interes_3'])}")

    # ── Bloque 2: Tasa Activa BNA ──
    st.markdown("---")
    st.markdown("**Tasa Activa BNA**")
    st.markdown(
        f"<div style='background:#7b9e87;padding:8px 16px;margin-bottom:8px;"
        f"display:flex;justify-content:space-between;align-items:center'>"
        f"<span style='color:white;font-weight:600'>Total Tasa Activa BNA</span>"
        f"<span style='color:white;font-family:monospace;font-size:16px;font-weight:800'>"
        f"{formato_moneda(r_ta['total'])}</span></div>",
        unsafe_allow_html=True
    )
    with st.expander("Detalle Tasa Activa"):
        st.write(f"**Tasa acumulada:** {r_ta['tasa_pct']:.2f}%")

    st.markdown("---")

    # ── Bloque 3: Art. 55 ──
    usar_bcra_55 = st.checkbox(
        "Método BCRA (CER + 3% compuesto)",
        value=False, key="act_bcra_55",
        help="La calculadora oficial del BCRA usa el CER diario con interés compuesto. "
             "Activa esta opción para ver el Art. 55 calculado con ese método."
    )
    if usar_bcra_55:
        r55_bcra = calcular_art55(monto, fecha_ini, fecha_fin, DS['df_ipc'], DS['df_cer'], DS['datos_tp'],
                                  usar_bcra=True, datos_cer_xls=DS['datos_cer_xls'])
        r55_show = r55_bcra
    else:
        r55_show = r55
    st.markdown("**Art. 55 Ley 27.802 — Juicios en trámite**")

    colores = {'tasa_pasiva': '#7b9e87', 'techo': '#7d6608', 'piso': '#7d6608'}
    aplica  = r55_show['aplica']

    filas_55 = [
        ('Tasa Pasiva BCRA (Art. 55 inc. a LML conf. Res. 45/26 BCRA)',     r55_show['tasa_pasiva'], 'tasa_pasiva'),
        ('IPC + 3% — techo (Art. 55 inc. b LML)',     r55_show['ipc_3'],       'techo'),
        ('Art. 55 inc. c LML — 67% de IPC + 3%', r55_show['piso_67'],  'piso'),
    ]
    filas_55_sorted = sorted(filas_55, key=lambda x: -x[1])

    for label, valor, key in filas_55_sorted:
        es_aplica = (key == aplica)
        bg = '#b8952a' if es_aplica else ('#2c3e50' if key == 'tasa_pasiva' else '#555')
        marca = " ✓ APLICA" if es_aplica else ""
        st.markdown(
            f"<div style='background:{bg};padding:7px 16px;margin-bottom:3px;"
            f"display:flex;justify-content:space-between;align-items:center'>"
            f"<span style='color:white;font-size:12px;font-weight:600'>{label}{marca}</span>"
            f"<span style='color:white;font-family:monospace;font-size:15px;font-weight:800'>"
            f"{formato_moneda(valor)}</span></div>",
            unsafe_allow_html=True
        )

    st.caption("Se muestran los tres valores. El juez puede apartarse de la banda si declara inconstitucionalidad.")

    with st.expander("Detalle Tasa Pasiva"):
        tp = r55_show['detalle_tp']
        st.write(f"**T₀ ({tp['T0_fecha'].strftime('%d/%m/%Y')}):** {tp['T0']:.6f}")
        st.write(f"**Tₘ ({tp['Tm_fecha'].strftime('%d/%m/%Y')}):** {tp['Tm']:.6f}")
        st.write(f"**Tasa período:** {tp['tasa_pct']:.4f}%")

    # ── Bloque 4: CER + 3% (referencia) ──
    r_cer = st.session_state.get('act_cer', {})
    if r_cer:
        st.markdown("---")
        st.markdown("**CER diario + 3% simple** *(referencia)*")
        st.markdown(
            f"<div style='background:#6c3483;padding:7px 16px;margin-bottom:8px;"
            f"display:flex;justify-content:space-between;align-items:center'>"
            f"<span style='color:white;font-size:12px;font-weight:600'>Total CER + 3%</span>"
            f"<span style='color:white;font-family:monospace;font-size:15px;font-weight:800'>"
            f"{formato_moneda(r_cer['total'])}</span></div>",
            unsafe_allow_html=True
        )
        with st.expander("Detalle CER"):
            st.write(f"**CER origen ({fecha_ini.strftime('%d/%m/%Y')}):** {r_cer['cer_origen']:.6f}")
            st.write(f"**CER cálculo ({r_cer['cer_calculo_fecha'].strftime('%d/%m/%Y')}):** {r_cer['cer_calculo']:.6f}")
            st.write(f"**Coeficiente:** {r_cer['coef']:.6f} ({r_cer['pct_variacion']:.2f}%)")
            st.write(f"**Capital indexado:** {formato_moneda(r_cer['capital_indexado'])}")
            st.write(f"**Interés 3% simple ({r_cer['dias']} días):** {formato_moneda(r_cer['interes_3'])}")

    # ── PDF ──
    st.markdown("---")
    if st.button("🖨️ Generar PDF", key="act_pdf_btn"):
        st.session_state['act_pdf'] = True

    if st.session_state.get('act_pdf'):
        f_ini_str = fecha_ini.strftime('%d/%m/%Y')
        f_fin_str = fecha_fin.strftime('%d/%m/%Y')

        if r['metodo'] == 'CER+IPC':
                det_html = f"""
                <tr><td>CER origen ({fecha_ini.strftime('%m/%Y')})</td><td class="num">{r['cer_origen']:.6f}</td></tr>
                <tr><td>CER nov-2016</td><td class="num">{r['cer_nov2016']:.6f}</td></tr>
                <tr><td>Coef. CER</td><td class="num">{r['coef_cer']:.6f}</td></tr>
                <tr><td>IPC base 100 → {mes_anio(r['ipc_ultimo_fecha'])}: {r['ipc_ultimo']:.2f}</td><td class="num">Coef. IPC: {r['coef_ipc']:.6f}</td></tr>
                <tr><td>Capital indexado</td><td class="num">{formato_moneda(r['capital_indexado'])}</td></tr>
                <tr><td>Interés 3% simple ({r['dias']} días)</td><td class="num">{formato_moneda(r['interes_3'])}</td></tr>
                """
        else:
            det_html = f"""
            <tr><td>IPC origen ({mes_anio(fecha_ini)})</td><td class="num">{r['ipc_origen']:.2f}</td></tr>
            <tr><td>IPC último ({mes_anio(r['ipc_ultimo_fecha'])})</td><td class="num">{r['ipc_ultimo']:.2f}</td></tr>
            <tr><td>Coeficiente</td><td class="num">{r['coef']:.6f} ({r['pct_variacion']:.2f}%)</td></tr>
            <tr><td>Capital indexado</td><td class="num">{formato_moneda(r['capital_indexado'])}</td></tr>
            <tr><td>Interés 3% simple ({r['dias']} días)</td><td class="num">{formato_moneda(r['interes_3'])}</td></tr>
            """
        titulo_met = "IPC + 3% SIMPLE (Art. 276 LCT)"

        tp = r55_show['detalle_tp']
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
.aplica {{background:#b8952a;color:white;font-weight:700}}
.footer {{text-align:center;font-size:8px;color:#888;margin-top:14px;border-top:1px solid #ddd;padding-top:6px}}
.btn {{background:#333;color:white;border:none;padding:7px 16px;cursor:pointer;font-size:12px;font-weight:600;margin-bottom:10px}}
</style></head><body>
<button class="btn no-print" onclick="window.print()">🖨️ IMPRIMIR / GUARDAR PDF</button>
<div class="container">
<h1>ACTUALIZACIÓN E INTERESES</h1>

<table>
<tr><th colspan="2">DATOS</th></tr>
<tr><td>Monto histórico</td><td class="num"><strong>{formato_moneda(monto)}</strong></td></tr>
<tr><td>Período</td><td>{f_ini_str} al {f_fin_str}</td></tr>
</table>

<h2>{titulo_met}</h2>
<table>
<tr><th colspan="2">Detalle</th></tr>
{det_html}
<tr><th>TOTAL</th><th class="num">{formato_moneda(r['total'])}</th></tr>
</table>

<h2>Art. 55 Ley 27.802 — Juicios en trámite</h2>
<table>
<tr><th>Concepto</th><th class="num">Total</th></tr>
{"".join(
    f'<tr class="{"aplica" if key==aplica else ""}"><td>{label}{" ✓ APLICA" if key==aplica else ""}</td><td class="num">{formato_moneda(valor)}</td></tr>'
    for label, valor, key in filas_55_sorted
)}
</table>
<p style="font-size:8.5px;color:#555;margin-bottom:8px">
Se exponen los tres valores. El juez puede apartarse de la banda legal por razones de inconstitucionalidad.
</p>

<table>
<tr><th colspan="2">Tasa Pasiva BCRA — Detalle (Res. 45/26)</th></tr>
<tr><td>T₀ ({tp['T0_fecha'].strftime('%d/%m/%Y')})</td><td class="num">{tp['T0']:.6f}</td></tr>
<tr><td>Tₘ ({tp['Tm_fecha'].strftime('%d/%m/%Y')})</td><td class="num">{tp['Tm']:.6f}</td></tr>
<tr><td>Tasa período</td><td class="num">{tp['tasa_pct']:.4f}%</td></tr>
</table>

<table>
<tr><th colspan="2">Tasa Activa BNA (referencia)</th></tr>
<tr><td>Tasa acumulada</td><td class="num">{r_ta['tasa_pct']:.2f}%</td></tr>
<tr><td><strong>Total</strong></td><td class="num"><strong>{formato_moneda(r_ta['total'])}</strong></td></tr>
</table>

<div class="footer">Tribunal de Trabajo N° 2 de Quilmes — {date.today().strftime('%d/%m/%Y')}</div>
</div></body></html>"""

        st.components.v1.html(html, height=900, scrolling=True)