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

# Cargar datos
df_jus = cargar_dataset_jus()

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
    
    # Columnas principales: Entrada | Resultado
    col_entrada, col_resultado = st.columns([1, 1])
    
    with col_entrada:
        st.markdown("**💰 Datos del Juicio**")
        monto_juicio = st.number_input(
            "Monto ($)",
            min_value=0.01,
            value=1000000.00,
            step=10000.00,
            format="%.2f",
            key="monto_juicio"
        )
        
        fecha_sent = st.date_input(
            "Fecha",
            value=date.today(),
            min_value=date(2017, 1, 1),
            max_value=date.today(),
            format="DD/MM/YYYY",
            key="fecha_sent"
        )
    
    # Conversión a JUS
    res_base = convertir_a_jus(monto_juicio, fecha_sent, df_jus)
    
    if res_base:
        limite_25 = monto_juicio * 0.25
        
        with col_resultado:
            st.markdown(f"**📊 Límite 25%:** {formato_moneda(limite_25)}")
            st.caption(f"{(limite_25/res_base['valor_jus']):.2f} JUS | {res_base['acuerdo']}")
        
        # Inicializar estados con keys únicos por ID
        if 'abog_data' not in st.session_state:
            st.session_state.abog_data = [{'id': 1, 'pesos': 0.0, 'iva': False}]
            st.session_state.abog_counter = 1
        if 'aux_data' not in st.session_state:
            st.session_state.aux_data = [{'id': 1, 'pesos': 0.0}]
            st.session_state.aux_counter = 1
        
        # Calcular totales individuales (Caja siempre incluida)
        total_abog = sum([a['pesos'] for a in st.session_state.abog_data])
        total_iva = sum([a['pesos'] * 0.21 for a in st.session_state.abog_data if a.get('iva', False)])
        total_caja = sum([a['pesos'] * 0.10 for a in st.session_state.abog_data])  # Caja siempre
        total_aux = sum([a['pesos'] for a in st.session_state.aux_data])
        
        total_usado = total_abog + total_iva + total_caja + total_aux
        pct_usado = (total_usado / monto_juicio) * 100
        
        # Mostrar porcentaje usado
        with col_resultado:
            color = "red" if pct_usado > 25 else ("orange" if pct_usado > 20 else "green")
            emoji = "🔴" if pct_usado > 25 else ("🟡" if pct_usado > 20 else "🟢")
            st.markdown(f"<h1 style='text-align: center; color: {color};'>{emoji} {pct_usado:.2f}%</h1>", unsafe_allow_html=True)
            st.progress(min(pct_usado / 25.0, 1.0))
        
        st.markdown("")
        
        st.markdown("---")
        
        # ============================================
        # ABOGADOS Y AUXILIARES EN 2 COLUMNAS
        # ============================================
        col_abogados, col_auxiliares = st.columns([1, 1], gap="large")
        
        # COLUMNA IZQUIERDA: ABOGADOS
        with col_abogados:
            st.markdown('<div style="background-color: #4CAF50; color: white; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 10px;"><b>👨‍⚖️ Abogados</b></div>', unsafe_allow_html=True)
            
            for i, abog in enumerate(st.session_state.abog_data):
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    otros = sum([a['pesos'] for j, a in enumerate(st.session_state.abog_data) if j != i])
                    otros_iva = sum([a['pesos'] * 0.21 for j, a in enumerate(st.session_state.abog_data) if j != i and a.get('iva', False)])
                    otros_caja = sum([a['pesos'] * 0.10 for j, a in enumerate(st.session_state.abog_data) if j != i])
                    disp = limite_25 - total_aux - otros - otros_iva - otros_caja
                    
                    monto_base_abog = abog['pesos']
                    iva_abog = monto_base_abog * 0.21 if abog.get('iva', False) else 0
                    caja_abog = monto_base_abog * 0.10
                    monto_total_abog = monto_base_abog + iva_abog + caja_abog
                    
                    disp_ajustado = disp + monto_total_abog
                    
                    max_pct = (disp_ajustado / (monto_juicio * (1.21 if abog.get('iva', False) else 1) * 1.10)) * 100 if monto_juicio > 0 else 0
                    
                    pct = st.number_input(
                        "% del monto",
                        min_value=0.00,
                        max_value=max(0.00, max_pct),
                        value=round((abog['pesos'] / monto_juicio * 100) if monto_juicio > 0 else 0.0, 2),
                        step=0.01,
                        format="%.2f",
                        key=f"abog_pct_{abog['id']}_{i}"
                    )
                    
                    nuevo_pesos = round((pct / 100) * monto_juicio, 2)
                    if abs(nuevo_pesos - abog['pesos']) > 0.001:
                        st.session_state.abog_data[i]['pesos'] = nuevo_pesos
                        st.rerun()
                
                with col2:
                    max_pesos_permitido = disp_ajustado / ((1.21 if abog.get('iva', False) else 1) * 1.10)
                    
                    pesos = st.number_input(
                        "$ Monto",
                        min_value=0.00,
                        max_value=max(0.00, max_pesos_permitido),
                        value=round(abog['pesos'], 2),
                        step=100.00,
                        format="%.2f",
                        key=f"abog_pesos_{abog['id']}_{i}"
                    )
                    
                    if abs(pesos - abog['pesos']) > 0.001:
                        st.session_state.abog_data[i]['pesos'] = round(pesos, 2)
                        st.rerun()
                
                col_j, col_iv, col_del = st.columns([2, 1, 0.5])
                
                with col_j:
                    jus_abog = abog['pesos'] / res_base['valor_jus']
                    alerta_jus = " ⚠️ No supera mínimo" if jus_abog < 7 else ""
                    st.caption(f"{jus_abog:.2f} JUS{alerta_jus}")
                
                with col_iv:
                    iva = st.checkbox("IVA", key=f"abog_iva_{abog['id']}_{i}", value=abog.get('iva', False))
                    if iva != abog.get('iva', False):
                        st.session_state.abog_data[i]['iva'] = iva
                        st.rerun()
                
                with col_del:
                    if len(st.session_state.abog_data) > 1:
                        if st.button("🗑️", key=f"del_abog_{abog['id']}_{i}"):
                            st.session_state.abog_data.pop(i)
                            st.rerun()
                
                detalles = [f"Caja: {formato_moneda(round(abog['pesos'] * 0.10, 2))}"]
                if abog.get('iva', False):
                    detalles.append(f"IVA: {formato_moneda(round(abog['pesos'] * 0.21, 2))}")
                st.caption(" | ".join(detalles))
                st.markdown("")
            
            if pct_usado >= 25.0:
                st.button("➕ Abogado", key="add_abog", disabled=True)
                st.caption("⚠️ Límite alcanzado")
            else:
                if st.button("➕ Abogado", key="add_abog"):
                    st.session_state.abog_counter += 1
                    st.session_state.abog_data.append({'id': st.session_state.abog_counter, 'pesos': 0.0, 'iva': False})
                    st.rerun()
            
            total_abog_individual = sum([a['pesos'] for a in st.session_state.abog_data])
            total_iva_individual = sum([a['pesos'] * 0.21 for a in st.session_state.abog_data if a.get('iva', False)])
            total_caja_individual = sum([a['pesos'] * 0.10 for a in st.session_state.abog_data])
            
            st.caption(f"**Total:** {formato_moneda(round(total_abog_individual, 2))} + Caja {formato_moneda(round(total_caja_individual, 2))} + IVA {formato_moneda(round(total_iva_individual, 2))}")
        
        # COLUMNA DERECHA: AUXILIARES
        with col_auxiliares:
            st.markdown('<div style="background-color: #2196F3; color: white; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 10px;"><b>🔬 Auxiliares</b></div>', unsafe_allow_html=True)
            
            for i, aux in enumerate(st.session_state.aux_data):
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    otros = sum([a['pesos'] for j, a in enumerate(st.session_state.aux_data) if j != i])
                    total_abog_con_extras = sum([
                        a['pesos'] + 
                        (a['pesos'] * 0.21 if a.get('iva', False) else 0) + 
                        (a['pesos'] * 0.10)
                        for a in st.session_state.abog_data
                    ])
                    disp = limite_25 - total_abog_con_extras - otros
                    
                    max_pct = (disp / monto_juicio) * 100 if monto_juicio > 0 else 0
                    
                    pct = st.number_input(
                        "% del monto",
                        min_value=0.00,
                        max_value=max(0.00, max_pct),
                        value=round((aux['pesos'] / monto_juicio * 100) if monto_juicio > 0 else 0.0, 2),
                        step=0.01,
                        format="%.2f",
                        key=f"aux_pct_{aux['id']}_{i}"
                    )
                    
                    nuevo_pesos = round((pct / 100) * monto_juicio, 2)
                    if abs(nuevo_pesos - aux['pesos']) > 0.001:
                        st.session_state.aux_data[i]['pesos'] = nuevo_pesos
                        st.rerun()
                
                with col2:
                    pesos = st.number_input(
                        "$ Monto",
                        min_value=0.00,
                        max_value=max(0.00, disp),
                        value=round(aux['pesos'], 2),
                        step=100.00,
                        format="%.2f",
                        key=f"aux_pesos_{aux['id']}_{i}"
                    )
                    
                    if abs(pesos - aux['pesos']) > 0.001:
                        st.session_state.aux_data[i]['pesos'] = round(pesos, 2)
                        st.rerun()
                
                col_nom, col_del = st.columns([3, 0.5])
                
                with col_nom:
                    st.caption(f"Auxiliar {i+1}")
                
                with col_del:
                    if len(st.session_state.aux_data) > 1:
                        if st.button("🗑️", key=f"del_aux_{aux['id']}_{i}"):
                            st.session_state.aux_data.pop(i)
                            st.rerun()
                
                st.markdown("")
            
            if pct_usado >= 25.0:
                st.button("➕ Auxiliar", key="add_aux", disabled=True)
            else:
                if st.button("➕ Auxiliar", key="add_aux"):
                    if len(st.session_state.aux_data) < 5:
                        st.session_state.aux_counter += 1
                        st.session_state.aux_data.append({'id': st.session_state.aux_counter, 'pesos': 0.0})
                        st.rerun()
            
            st.caption(f"**Total:** {formato_moneda(round(total_aux, 2))}")
        
        st.markdown("")
        
        # Detalle de cálculos regulados
        with st.expander("📋 Detalle de Cálculos Regulados"):
            st.markdown(f"""
            **Datos Base:**
            - Monto del Juicio: {formato_moneda(monto_juicio)}
            - Monto en JUS: {res_base['jus']:.2f} JUS
            - Valor JUS: {formato_moneda(res_base['valor_jus'])} ({res_base['acuerdo']})
            - Límite 25%: {formato_moneda(limite_25)} ({(limite_25/res_base['valor_jus']):.2f} JUS)
            
            ---
            
            **Abogados:**
            """)
            
            for i, abog in enumerate(st.session_state.abog_data):
                jus_abog = abog['pesos'] / res_base['valor_jus']
                pct_abog = (abog['pesos'] / monto_juicio) * 100
                iva_abog = abog['pesos'] * 0.21 if abog.get('iva', False) else 0
                caja_abog = abog['pesos'] * 0.10
                total_abog_individ = abog['pesos'] + iva_abog + caja_abog
                
                st.markdown(f"""
                **Abogado {i+1}:**
                - Honorarios: {formato_moneda(abog['pesos'])} ({pct_abog:.2f}% | {jus_abog:.2f} JUS)
                - Caja (10%): {formato_moneda(caja_abog)}
                {f"- IVA (21%): {formato_moneda(iva_abog)}" if abog.get('iva', False) else ""}
                - **Subtotal: {formato_moneda(total_abog_individ)} ({(total_abog_individ/monto_juicio*100):.2f}%)**
                """)
            
            total_abog_individual = sum([a['pesos'] for a in st.session_state.abog_data])
            total_iva_individual = sum([a['pesos'] * 0.21 for a in st.session_state.abog_data if a.get('iva', False)])
            total_caja_individual = sum([a['pesos'] * 0.10 for a in st.session_state.abog_data])
            
            st.markdown(f"""
            **Total Abogados:**
            - Honorarios: {formato_moneda(total_abog_individual)}
            - Caja: {formato_moneda(total_caja_individual)}
            - IVA: {formato_moneda(total_iva_individual)}
            - **Total: {formato_moneda(total_abog_individual + total_caja_individual + total_iva_individual)} ({((total_abog_individual + total_caja_individual + total_iva_individual)/monto_juicio*100):.2f}%)**
            
            ---
            
            **Auxiliares:**
            """)
            
            for i, aux in enumerate(st.session_state.aux_data):
                jus_aux = aux['pesos'] / res_base['valor_jus']
                pct_aux = (aux['pesos'] / monto_juicio) * 100
                
                st.markdown(f"""
                **Auxiliar {i+1}:** {formato_moneda(aux['pesos'])} ({pct_aux:.2f}% | {jus_aux:.2f} JUS)
                """)
            
            st.markdown(f"""
            **Total Auxiliares:** {formato_moneda(total_aux)} ({(total_aux/monto_juicio*100):.2f}%)
            
            ---
            
            **RESUMEN FINAL:**
            - Total Abogados: {formato_moneda(total_abog_individual + total_caja_individual + total_iva_individual)} ({((total_abog_individual + total_caja_individual + total_iva_individual)/monto_juicio*100):.2f}%)
            - Total Auxiliares: {formato_moneda(total_aux)} ({(total_aux/monto_juicio*100):.2f}%)
            - **TOTAL GENERAL: {formato_moneda(total_usado)} ({pct_usado:.2f}%)**
            - **REMANENTE: {formato_moneda(limite_25 - total_usado)} ({(25.0 - pct_usado):.2f}%)**
            """)

# Mostrar últimos datos disponibles
st.markdown("---")
mostrar_ultimos_datos_universal()

# Footer
st.markdown("---")
st.caption("**CALCULADORA DE HONORARIOS PROFESIONALES** | Sistema de Regulación Legal")
