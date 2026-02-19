#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CALCULADORA DE HONORARIOS PROFESIONALES
Sistema de conversión a JUS y regulación según Ley 24432
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
from utils.data_loader import get_ultimo_dato
from utils.navegacion import mostrar_sidebar_navegacion
from utils.info_datasets import mostrar_ultimos_datos_universal
from utils.funciones_comunes import formato_moneda

# Sidebar de navegación
mostrar_sidebar_navegacion('honorarios')

# Cargar dataset de JUS
def cargar_dataset_jus():
    """Carga el dataset de valores JUS"""
    df = pd.read_csv("data/Dataset_JUS.csv", encoding='utf-8')
    df.columns = df.columns.str.strip()
    df['FECHA ENTRADA EN VIGENCIA'] = pd.to_datetime(df['FECHA ENTRADA EN VIGENCIA'], dayfirst=True)
    df['FECHA DE FINALIZACION'] = pd.to_datetime(df['FECHA DE FINALIZACION'], dayfirst=True, errors='coerce')
    df['VALOR IUS'] = df['VALOR IUS'].str.replace('$', '').str.replace('.', '').str.replace(',', '.').str.strip()
    df['VALOR IUS'] = pd.to_numeric(df['VALOR IUS'])
    return df

# Función para convertir pesos a JUS
def convertir_a_jus(monto_pesos, fecha_conversion, df_jus):
    """Convierte un monto en pesos a JUS según la fecha"""
    try:
        fecha_conv = pd.to_datetime(fecha_conversion)
        
        registro = df_jus[
            (df_jus['FECHA ENTRADA EN VIGENCIA'] <= fecha_conv) &
            ((df_jus['FECHA DE FINALIZACION'] >= fecha_conv) | 
             (df_jus['FECHA DE FINALIZACION'].isna()))
        ]
        
        if registro.empty:
            registro = df_jus.iloc[-1:]
        
        valor_jus = float(get_ultimo_dato(registro)['VALOR IUS'])
        acuerdo = get_ultimo_dato(registro)['ACUERDO']
        fecha_desde = get_ultimo_dato(registro)['FECHA ENTRADA EN VIGENCIA']
        fecha_hasta = get_ultimo_dato(registro)['FECHA DE FINALIZACION']
        
        jus_exacto = float(monto_pesos) / valor_jus
        jus_redondeado = round(jus_exacto, 2)
        
        return {
            'jus': jus_redondeado,
            'jus_exacto': jus_exacto,
            'valor_jus': valor_jus,
            'acuerdo': acuerdo,
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta if pd.notna(fecha_hasta) else "Actualidad"
        }
    except Exception as e:
        st.error(f"Error en conversión a JUS: {str(e)}")
        return None

# Cargar RIPTE
def cargar_minimo_ripte():
    try:
        df = pd.read_csv("data/dataset_ripte.csv", encoding='utf-8')
        df.columns = df.columns.str.strip()
        df['monto_en_pesos'] = df['monto_en_pesos'].astype(str).str.replace('.', '').str.replace(',', '.').str.strip()
        df['monto_en_pesos'] = pd.to_numeric(df['monto_en_pesos'], errors='coerce')
        ultimo = df.iloc[0]
        minimo = float(ultimo['monto_en_pesos']) / 2
        mes = str(ultimo.get('mes', '')).strip()
        anio = str(int(ultimo['año'])) if 'año' in df.columns else ''
        return minimo, f"{mes} {anio}"
    except Exception as e:
        return None, ""

# Cargar datos
df_jus = cargar_dataset_jus()
ripte_minimo, ripte_periodo = cargar_minimo_ripte()

# Título principal
st.title("💵 CALCULADORA DE HONORARIOS PROFESIONALES")
st.markdown("---")

# Tabs
tab1, tab2 = st.tabs(["📊 CONVERSIÓN A JUS", "📋 REGULACIÓN LEY 24432"])

# ============================================
# TAB 1: CONVERSIÓN A JUS
# ============================================
with tab1:
    st.header("💰 Conversión de Pesos a JUS")
    st.markdown("---")
    
    col_izq, col_der = st.columns([1, 1])
    
    with col_izq:
        st.markdown("### 📝 Datos de Entrada")
        
        monto_pesos = st.number_input(
            "💵 Monto en Pesos ($)",
            min_value=0.01,
            value=100000.00,
            step=1000.00,
            format="%.2f",
            key="monto_jus"
        )
        
        fecha_conversion = st.date_input(
            "📅 Fecha de Conversión",
            value=date.today(),
            min_value=date(2017, 1, 1),
            max_value=date.today(),
            format="DD/MM/YYYY",
            key="fecha_jus"
        )
        
        calcular_jus = st.button("⚡ CONVERTIR A JUS", use_container_width=True, type="primary")
    
    with col_der:
        st.markdown("### 📊 Resultado")
        
        if calcular_jus:
            resultado = convertir_a_jus(monto_pesos, fecha_conversion, df_jus)
            
            if resultado:
                st.success("✅ Conversión Exitosa")
                
                fecha_hoy = pd.to_datetime(date.today())
                registro_actual = df_jus[
                    (df_jus['FECHA ENTRADA EN VIGENCIA'] <= fecha_hoy) &
                    ((df_jus['FECHA DE FINALIZACION'] >= fecha_hoy) | 
                     (df_jus['FECHA DE FINALIZACION'].isna()))
                ]
                
                if registro_actual.empty:
                    valor_jus_actual = float(get_ultimo_dato(df_jus)['VALOR IUS'])
                else:
                    valor_jus_actual = float(get_ultimo_dato(registro_actual)['VALOR IUS'])
                
                monto_actualizado = resultado['jus_exacto'] * valor_jus_actual
                
                col_jus_res1, col_jus_res2 = st.columns(2)
                
                with col_jus_res1:
                    st.metric(
                        label="Valor en JUS",
                        value=f"{resultado['jus']:,.2f} JUS".replace(",", "X").replace(".", ",").replace("X", ".")
                    )
                
                with col_jus_res2:
                    st.metric(
                        label="Monto Actualizado",
                        value=formato_moneda(monto_actualizado)
                    )
                
                st.info(f"**{resultado['acuerdo']}**")
                
                fecha_hasta_str = resultado['fecha_hasta'].strftime('%d/%m/%Y') if isinstance(resultado['fecha_hasta'], (datetime, pd.Timestamp)) else resultado['fecha_hasta']
                
                st.markdown(f"""
                **Valor JUS aplicado:** {formato_moneda(resultado['valor_jus'])}  
                **Vigencia:** {resultado['fecha_desde'].strftime('%d/%m/%Y')} hasta {fecha_hasta_str}
                """)
                
                with st.expander("📋 Detalle del Cálculo"):
                    st.markdown(f"""
                    - **Monto en Pesos:** {formato_moneda(monto_pesos)}
                    - **Valor del JUS:** {formato_moneda(resultado['valor_jus'])}
                    - **Resultado:** {formato_moneda(monto_pesos)} ÷ {formato_moneda(resultado['valor_jus'])} = **{resultado['jus']:,.2f} JUS**
                    
                    **Actualización:**
                    - **Valor JUS actual:** {formato_moneda(valor_jus_actual)}
                    - **Monto actualizado:** {resultado['jus']:,.2f} JUS × {formato_moneda(valor_jus_actual)} = **{formato_moneda(monto_actualizado)}**
                    """)
        else:
            st.info("👈 Ingrese los datos y presione CONVERTIR A JUS")

# ============================================
# TAB 2: REGULACIÓN LEY 24432
# ============================================
with tab2:
    st.header("📋 Regulación Ley 24432")

    # --- Datos base ---
    col_entrada, col_fecha = st.columns([1, 1])
    with col_entrada:
        monto_juicio = st.number_input(
            "💰 Monto del Juicio ($)",
            min_value=0.01,
            value=1000000.00,
            step=10000.00,
            format="%.2f",
            key="monto_juicio"
        )
    with col_fecha:
        fecha_sent = st.date_input(
            "📅 Fecha",
            value=date.today(),
            min_value=date(2017, 1, 1),
            max_value=date.today(),
            format="DD/MM/YYYY",
            key="fecha_sent"
        )

    res_base = convertir_a_jus(monto_juicio, fecha_sent, df_jus)

    if res_base:
        valor_jus = res_base['valor_jus']
        limite_25 = monto_juicio * 0.25

        # ── FILAS ──
        CONCEPTOS = [
            {'key': 'actora',    'label': '👨‍⚖️ Rep. Letrada Actora'},
            {'key': 'auxiliar_1', 'label': '🔬 Auxiliar 1'},
            {'key': 'auxiliar_2', 'label': '🔬 Auxiliar 2'},
            {'key': 'auxiliar_3', 'label': '🔬 Auxiliar 3'},
            {'key': 'auxiliar_4', 'label': '🔬 Auxiliar 4'},
        ]

        # ── HEADER ──
        st.markdown("---")
        h0, h1, h2, h3, h4, h5, h6 = st.columns([2.5, 3.0, 1.2, 1.2, 1.0, 1.0, 1.4])
        h0.markdown("**Concepto**")
        h1.markdown("**% del juicio**")
        h2.markdown("**$ Honorarios**")
        h3.markdown("**JUS**")
        h4.markdown("**IVA**")
        h5.markdown("**Aportes**")
        h6.markdown("**Total fila**")

        st.markdown("")

        # ── FILAS CON SLIDER ──
        for c in CONCEPTOS:
            key = c['key']
            col0, col1, col2, col3, col4, col5, col6 = st.columns([2.5, 3.0, 1.2, 1.2, 1.0, 1.0, 1.4])

            with col0:
                st.markdown(f"<div style='padding-top:28px'>{c['label']}</div>", unsafe_allow_html=True)

            with col1:
                pct = st.slider(
                    "pct", min_value=0.0, max_value=25.0,
                    value=0.0, step=0.05, format="%.2f%%",
                    key=f"pct_{key}", label_visibility="collapsed"
                )

            iva = st.session_state.get(f"iva_{key}", False)
            aportes = st.session_state.get(f"ap_{key}", 10)
            pesos = round((pct / 100) * monto_juicio, 2)
            jus = round(pesos / valor_jus, 2) if valor_jus > 0 else 0.0
            iva_monto = pesos * 0.21 if iva else 0.0
            ap_monto = pesos * (aportes / 100)
            total_fila = pesos + iva_monto + ap_monto

            with col2:
                st.markdown(f"<div style='padding-top:28px; font-weight:bold'>{formato_moneda(pesos)}</div>", unsafe_allow_html=True)

            with col3:
                st.markdown(f"<div style='padding-top:28px'>{jus:.2f}</div>", unsafe_allow_html=True)

            with col4:
                iva = st.checkbox("21%", value=iva, key=f"iva_{key}")

            with col5:
                aportes = st.selectbox("ap", options=[5, 10],
                    index=0 if aportes == 5 else 1,
                    format_func=lambda x: f"{x}%",
                    key=f"ap_{key}", label_visibility="collapsed")

            with col6:
                st.markdown(f"<div style='padding-top:28px; font-weight:bold'>{formato_moneda(total_fila)}</div>", unsafe_allow_html=True)

        # ── FILA DEMANDADA (70% de actora, sin slider) ──
        st.markdown("")
        pct_actora = st.session_state.get("pct_actora", 0.0)
        pesos_actora = round((pct_actora / 100) * monto_juicio, 2)
        pesos_dem = round(pesos_actora * 0.70, 2)
        pct_dem = round((pesos_dem / monto_juicio * 100) if monto_juicio > 0 else 0.0, 2)
        jus_dem = round(pesos_dem / valor_jus, 2) if valor_jus > 0 else 0.0
        iva_dem = st.session_state.get("iva_demandada", False)
        ap_dem = st.session_state.get("ap_demandada", 10)

        d0, d1, d2, d3, d4, d5, d6 = st.columns([2.5, 3.0, 1.2, 1.2, 1.0, 1.0, 1.4])
        iva_dem_monto = pesos_dem * 0.21 if iva_dem else 0.0
        ap_dem_monto = pesos_dem * (ap_dem / 100)
        total_dem = pesos_dem + iva_dem_monto + ap_dem_monto
        with d0:
            st.markdown("<div style='padding-top:8px; font-weight:bold; color:#E65100'>👨‍⚖️ Rep. Letrada Demandada<br><small style='color:#888'>70% actora · automático</small></div>", unsafe_allow_html=True)
        with d1:
            st.markdown(f"<div style='padding-top:8px; color:#888'>{pct_dem:.2f}%</div>", unsafe_allow_html=True)
        with d2:
            st.markdown(f"<div style='padding-top:8px; font-weight:bold; color:#E65100'>{formato_moneda(pesos_dem)}</div>", unsafe_allow_html=True)
        with d3:
            st.markdown(f"<div style='padding-top:8px; color:#E65100'>{jus_dem:.2f}</div>", unsafe_allow_html=True)
        with d4:
            iva_dem = st.checkbox("21%", value=iva_dem, key="iva_demandada")
        with d5:
            ap_dem = st.selectbox("ap", options=[5, 10],
                index=0 if ap_dem == 5 else 1,
                format_func=lambda x: f"{x}%",
                key="ap_demandada", label_visibility="collapsed")
        with d6:
            st.markdown(f"<div style='padding-top:8px; font-weight:bold; color:#E65100'>{formato_moneda(total_dem)}</div>", unsafe_allow_html=True)

        # ── TOTALES ──
        st.markdown("---")

        total_pesos = 0.0
        total_jus = 0.0
        for c in CONCEPTOS:
            key = c['key']
            pct_f = st.session_state.get(f"pct_{key}", 0.0)
            iva_f = st.session_state.get(f"iva_{key}", False)
            ap_f = st.session_state.get(f"ap_{key}", 10)
            p = round((pct_f / 100) * monto_juicio, 2)
            factor = 1.0 + (0.21 if iva_f else 0.0) + (ap_f / 100)
            total_pesos += p * factor
            total_jus += round(p / valor_jus, 2) if valor_jus > 0 else 0.0

        # Demandada no suma al 25% pero sí se muestra
        pct_usado = (total_pesos / monto_juicio * 100) if monto_juicio > 0 else 0.0
        disponible = limite_25 - total_pesos
        barra_pct = min(pct_usado / 25.0 * 100, 100)
        color = "red" if pct_usado > 25 else ("orange" if pct_usado > 20 else "green")
        barra_color = "red" if pct_usado > 25 else ("orange" if pct_usado > 20 else "#4CAF50")
        emoji = "🔴" if pct_usado > 25 else ("🟡" if pct_usado > 20 else "🟢")
        color_disp = "#cc0000" if disponible < 0 else "#4CAF50"
        jus_limite = limite_25 / valor_jus if valor_jus > 0 else 0.0

        st.markdown(f"""
        <div style="background:#1e1e1e; border:1px solid #444; border-radius:8px;
                    padding:10px 20px; margin:8px 0 12px 0;
                    display:flex; align-items:center; gap:0;">
          <div style="flex:1; text-align:center;">
            <div style="font-size:22px; font-weight:bold; color:{color};">{emoji} {pct_usado:.2f}%</div>
            <div style="font-size:11px; color:#888;">del 25% usado</div>
          </div>
          <div style="width:1px; background:#444; height:40px;"></div>
          <div style="flex:1; text-align:center;">
            <div style="font-size:22px; font-weight:bold; color:{color_disp};">{formato_moneda(disponible)}</div>
            <div style="font-size:11px; color:#888;">disponible</div>
          </div>
          <div style="width:1px; background:#444; height:40px;"></div>
          <div style="flex:1; text-align:center;">
            <div style="font-size:16px; font-weight:bold; color:#aaa;">{formato_moneda(limite_25)}</div>
            <div style="font-size:11px; color:#888;">límite 25% | {jus_limite:.2f} JUS | {res_base['acuerdo']}</div>
          </div>
          <div style="flex:2; padding-left:20px;">
            <div style="background:#333; border-radius:4px; height:10px;">
              <div style="background:{barra_color}; height:10px; border-radius:4px; width:{barra_pct:.1f}%;"></div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

# Mostrar últimos datos disponibles
st.markdown("---")
mostrar_ultimos_datos_universal()

# Footer
st.markdown("---")
st.caption("**CALCULADORA DE HONORARIOS PROFESIONALES** | Sistema de Regulación Legal")
