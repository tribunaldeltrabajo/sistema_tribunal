#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CALCULADORA DE HONORARIOS
Regulación de Honorarios — Ley 24.432
Extraído de calculadora_relatoria.py como módulo independiente.
"""

import streamlit as st
import pandas as pd
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import os
from utils.navegacion import mostrar_sidebar_navegacion
from utils.funciones_comunes import redondear, formato_moneda

mostrar_sidebar_navegacion('honorarios')

# ─────────────────────────────────────────────
# RUTAS Y CONSTANTES
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
PATH_JUS = os.path.join(DATA_DIR, "Dataset_JUS.csv")

FACTOR_HONORARIO = 1.31
TOPE_NETO        = 0.25 / FACTOR_HONORARIO

# ─────────────────────────────────────────────
# CARGA DE DATASETS
# ─────────────────────────────────────────────

@st.cache_data
def cargar_datasets():
    df_jus = pd.read_csv(PATH_JUS)
    df_jus.columns = df_jus.columns.str.strip()
    df_jus['FECHA ENTRADA EN VIGENCIA'] = pd.to_datetime(df_jus['FECHA ENTRADA EN VIGENCIA'], dayfirst=True)
    df_jus['FECHA DE FINALIZACION'] = pd.to_datetime(df_jus['FECHA DE FINALIZACION'], format='%d/%m/%Y', dayfirst=True, errors='coerce')
    df_jus['VALOR IUS'] = df_jus['VALOR IUS'].astype(str).str.replace('$','').str.replace('.','').str.replace(',','.').str.strip()
    df_jus['VALOR IUS'] = pd.to_numeric(df_jus['VALOR IUS'], errors='coerce')
    return df_jus

try:
    df_jus = cargar_datasets()
except Exception as e:
    st.error(f"Error al cargar datasets: {e}")
    st.stop()


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
# CÁLCULO DE HONORARIOS
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
# UI
# ─────────────────────────────────────────────

st.markdown("# 💵 CALCULADORA DE HONORARIOS")
st.markdown("---")
st.subheader("Regulación de Honorarios — Ley 24.432")

c1, c2, c3 = st.columns(3)
with c1:
    monto_juicio_hon = st.number_input("Monto del juicio ($)", min_value=0.01,
        value=1000000.0, step=1000.0, format="%.2f", key="hon_monto")
with c2:
    fecha_sent_hon = st.date_input("Fecha de sentencia",
        value=date.today(), format="DD/MM/YYYY", key="hon_fecha")
with c3:
    n_aux = st.number_input("Cantidad de auxiliares",
        min_value=0, max_value=5, value=1, step=1, key="hon_naux")

if st.button("⚡ CALCULAR HONORARIOS", type="primary", use_container_width=True, key="btn_hon"):
    valor_jus, acuerdo_jus = get_valor_jus(df_jus, fecha_sent_hon)
    h = calcular_honorarios(monto_juicio_hon, int(n_aux), valor_jus)
    st.session_state['hon_res']     = h
    st.session_state['hon_acuerdo'] = acuerdo_jus
    st.session_state['hon_monto_j'] = monto_juicio_hon

if 'hon_res' in st.session_state and 'hon_acuerdo' in st.session_state and 'hon_monto_j' in st.session_state:
    h       = st.session_state['hon_res']
    acuerdo = st.session_state['hon_acuerdo']
    monto_j = st.session_state['hon_monto_j']

    st.markdown("---")
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
else:
    st.info("👈 Completá los datos y presioná CALCULAR HONORARIOS")
