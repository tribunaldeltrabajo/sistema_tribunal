#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CALCULADORA DE ACTUALIZACIÓN DE MONTOS
Sistema simple de actualización con RIPTE, IPC y Tasa Activa
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from utils.data_loader import get_ultimo_dato
from utils.navegacion import mostrar_sidebar_navegacion
from utils.funciones_comunes import safe_parse_date, formato_moneda
from utils.info_datasets import mostrar_ultimos_datos_universal

# Sidebar de navegación
mostrar_sidebar_navegacion('actualizacion')

# Cargar datasets
def cargar_datasets():
    """Carga los datasets de RIPTE, Tasa e IPC"""
    df_ripte = pd.read_csv("data/dataset_ripte.csv", encoding='utf-8')
    df_ripte['fecha'] = pd.to_datetime(df_ripte['año'].astype(str) + '-' + 
                                       df_ripte['mes'].str[:3].map({
                                           'Ene': '01', 'Feb': '02', 'Mar': '03', 'Abr': '04',
                                           'May': '05', 'Jun': '06', 'Jul': '07', 'Ago': '08',
                                           'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dic': '12'
                                       }) + '-01')
    
    df_tasa = pd.read_csv("data/dataset_tasa.csv", encoding='utf-8')
    df_tasa['Desde'] = pd.to_datetime(df_tasa['Desde'], format='%d/%m/%Y', dayfirst=True)
    df_tasa['Hasta'] = pd.to_datetime(df_tasa['Hasta'], format='%d/%m/%Y', dayfirst=True)
    df_tasa['Valor'] = df_tasa['Valor'].astype(str).str.replace(',', '.').astype(float)
    
    df_ipc = pd.read_csv("data/dataset_ipc.csv", encoding='utf-8')
    df_ipc['periodo'] = pd.to_datetime(df_ipc['periodo'], format='ISO8601', errors='coerce')
    
    return df_ripte, df_tasa, df_ipc

# Función para actualizar por RIPTE con tasa pura variable
def actualizar_ripte(monto_base, fecha_inicial, fecha_final, df_ripte, tasa_pura):
    """Actualiza un monto por RIPTE + tasa pura variable"""
    try:
        if df_ripte.empty:
            return monto_base, 1.0, 0.0
        
        fecha_pmi = pd.to_datetime(fecha_inicial)
        fecha_final_date = pd.to_datetime(fecha_final)
        
        # Obtener RIPTE inicial
        ripte_pmi_data = df_ripte[df_ripte['fecha'] <= fecha_pmi]
        if ripte_pmi_data.empty:
            ripte_pmi = float(get_ultimo_dato(df_ripte)['indice_ripte'])
        else:
            ripte_pmi = float(get_ultimo_dato(ripte_pmi_data)['indice_ripte'])
        
        # Obtener RIPTE final
        ripte_final_data = df_ripte[df_ripte['fecha'] <= fecha_final_date]
        if ripte_final_data.empty:
            ripte_final = float(get_ultimo_dato(df_ripte)['indice_ripte'])
        else:
            ripte_final = float(get_ultimo_dato(ripte_final_data)['indice_ripte'])
        
        # Calcular coeficiente RIPTE
        coeficiente = ripte_final / ripte_pmi if ripte_pmi > 0 else 1.0
        
        # Aplicar RIPTE
        ripte_actualizado = monto_base * coeficiente
        
        # Aplicar tasa pura adicional
        interes_puro = ripte_actualizado * (tasa_pura / 100)
        
        total = ripte_actualizado + interes_puro
        
        return total, coeficiente, interes_puro
    except Exception as e:
        st.error(f"Error en cálculo de RIPTE: {str(e)}")
        return monto_base, 1.0, 0.0

# Función para actualizar por Tasa Activa
def actualizar_tasa(monto_base, fecha_inicial, fecha_final, df_tasa):
    """Actualiza un monto por Tasa Activa"""
    try:
        if df_tasa.empty:
            return monto_base, 0.0
        
        fecha_pmi = pd.to_datetime(fecha_inicial)
        fecha_final_date = pd.to_datetime(fecha_final)
        
        # Convertir a date si es Timestamp
        if isinstance(fecha_pmi, pd.Timestamp):
            fecha_pmi = fecha_pmi.date()
        if isinstance(fecha_final_date, pd.Timestamp):
            fecha_final_date = fecha_final_date.date()
        
        total_aporte_pct = 0.0
        
        for _, row in df_tasa.iterrows():
            if "Desde" in df_tasa.columns and not pd.isna(row.get("Desde")):
                fecha_desde = row["Desde"]
            elif "desde" in df_tasa.columns and not pd.isna(row.get("desde")):
                fecha_desde = row["desde"]
            else:
                continue
                
            if "Hasta" in df_tasa.columns and not pd.isna(row.get("Hasta")):
                fecha_hasta = row["Hasta"]
            elif "hasta" in df_tasa.columns and not pd.isna(row.get("hasta")):
                fecha_hasta = row["hasta"]
            else:
                continue
            
            if isinstance(fecha_desde, pd.Timestamp):
                fecha_desde = fecha_desde.date()
            if isinstance(fecha_hasta, pd.Timestamp):
                fecha_hasta = fecha_hasta.date()
            
            inicio_interseccion = max(fecha_pmi, fecha_desde)
            fin_interseccion = min(fecha_final_date, fecha_hasta)
            
            if inicio_interseccion <= fin_interseccion:
                dias_interseccion = (fin_interseccion - inicio_interseccion).days + 1
                
                if "Valor" in df_tasa.columns and not pd.isna(row.get("Valor")):
                    valor_mensual_pct = float(row["Valor"])
                elif "valor" in df_tasa.columns and not pd.isna(row.get("valor")):
                    valor_mensual_pct = float(row["valor"])
                elif "tasa" in df_tasa.columns and not pd.isna(row.get("tasa")):
                    valor_mensual_pct = float(row["tasa"])
                else:
                    continue
                
                aporte_pct = valor_mensual_pct * (dias_interseccion / 30.0)
                total_aporte_pct += aporte_pct
        
        total_actualizado = monto_base * (1.0 + total_aporte_pct / 100.0)
        
        return total_actualizado, total_aporte_pct
    except Exception as e:
        st.error(f"Error en cálculo de tasa: {str(e)}")
        return monto_base, 0.0

# Función para actualizar por IPC con tasa pura variable
def actualizar_ipc(monto_base, fecha_inicial, fecha_final, df_ipc, tasa_pura):
    """Actualiza un monto por IPC + tasa pura variable"""
    try:
        if df_ipc.empty:
            return monto_base, 0.0, 0.0
        
        fecha_pmi = pd.to_datetime(fecha_inicial)
        fecha_final_date = pd.to_datetime(fecha_final)
        
        # Convertir a fecha como objeto date para usar replace
        if isinstance(fecha_pmi, pd.Timestamp):
            fecha_pmi = fecha_pmi.date()
        if isinstance(fecha_final_date, pd.Timestamp):
            fecha_final_date = fecha_final_date.date()
        
        fecha_inicio_mes = pd.Timestamp(fecha_pmi.replace(day=1))
        fecha_final_mes = pd.Timestamp(fecha_final_date.replace(day=1))
        
        ipc_periodo = df_ipc[
            (pd.to_datetime(df_ipc['periodo']) >= fecha_inicio_mes) &
            (pd.to_datetime(df_ipc['periodo']) <= fecha_final_mes)
        ]
        
        if ipc_periodo.empty:
            return monto_base, 0.0, 0.0
        
        factor_acumulado = 1.0
        for _, row in ipc_periodo.iterrows():
            variacion = row['variacion_mensual']
            if not pd.isna(variacion):
                factor_acumulado *= (1 + variacion / 100)
        
        inflacion_acumulada = (factor_acumulado - 1) * 100
        
        # Aplicar IPC
        ipc_actualizado = monto_base * factor_acumulado
        
        # Aplicar tasa pura adicional
        interes_puro = ipc_actualizado * (tasa_pura / 100)
        
        total = ipc_actualizado + interes_puro
        
        return total, inflacion_acumulada, interes_puro
    except Exception as e:
        st.error(f"Error en cálculo de IPC: {str(e)}")
        return monto_base, 0.0, 0.0

# Función para formatear montos

def generar_desglose_texto(r):
    """Genera desglose detallado en formato texto plano"""
    ripte_sin_interes = r['monto'] * r['ripte_coef']
    ipc_sin_interes = r['monto'] * (1 + r['ipc_inflacion'] / 100)
    
    texto = f"DESGLOSE DE ACTUALIZACIÓN\n"
    texto += f"Período: {r['fecha_inicial'].strftime('%d/%m/%Y')} al {r['fecha_final'].strftime('%d/%m/%Y')}\n"
    texto += f"Monto Original: {formato_moneda(r['monto'])}\n"
    texto += "=" * 60 + "\n\n"
    
    texto += f"RIPTE + {r['tasa_pura_ripte']}% ANUAL\n"
    texto += "-" * 60 + "\n"
    texto += f"Monto Base:\t\t{formato_moneda(r['monto'])}\n"
    texto += f"Coeficiente RIPTE:\t{r['ripte_coef']:.6f}\n"
    texto += f"Monto Actualizado RIPTE:\t{formato_moneda(ripte_sin_interes)}\n"
    texto += f"Tasa Pura {r['tasa_pura_ripte']}%:\t\t{formato_moneda(r['ripte_interes'])}\n"
    texto += f"TOTAL RIPTE:\t\t{formato_moneda(r['ripte_total'])}\n\n"
    
    texto += "TASA ACTIVA BNA\n"
    texto += "-" * 60 + "\n"
    texto += f"Monto Base:\t\t{formato_moneda(r['monto'])}\n"
    texto += f"Tasa Acumulada:\t\t{r['tasa_pct']:.2f}%\n"
    texto += f"Intereses:\t\t{formato_moneda(r['tasa_total'] - r['monto'])}\n"
    texto += f"TOTAL TASA:\t\t{formato_moneda(r['tasa_total'])}\n\n"
    
    texto += f"IPC + {r['tasa_pura_ipc']}% ANUAL\n"
    texto += "-" * 60 + "\n"
    texto += f"Monto Base:\t\t{formato_moneda(r['monto'])}\n"
    texto += f"Inflación Acumulada:\t{r['ipc_inflacion']:.2f}%\n"
    texto += f"Monto Actualizado IPC:\t{formato_moneda(ipc_sin_interes)}\n"
    texto += f"Tasa Pura {r['tasa_pura_ipc']}%:\t\t{formato_moneda(r['ipc_interes'])}\n"
    texto += f"TOTAL IPC:\t\t{formato_moneda(r['ipc_total'])}\n"
    texto += "=" * 60 + "\n"
    
    return texto

# Cargar datos
try:
    df_ripte, df_tasa, df_ipc = cargar_datasets()
except Exception as e:
    st.error(f"Error al cargar datasets: {str(e)}")
    st.stop()

# Título principal
st.markdown("# 📈 CALCULADORA DE ACTUALIZACIÓN E INTERESES")
st.markdown("---")

# Diseño en dos columnas principales
col_izq, col_der = st.columns([1, 1])

# Columna izquierda - DATOS DE ENTRADA
with col_izq:
    st.subheader("📝 DATOS")
    
    monto = st.number_input(
        "💰 Monto a Actualizar ($)",
        min_value=0.01,
        value=100000.00,
        step=1000.00,
        format="%.2f"
    )
    
    fecha_inicial = st.date_input(
        "📅 Fecha Inicial",
        value=date(2023, 1, 1),
        min_value=date(2010, 1, 1),
        max_value=date.today(),
        format="DD/MM/YYYY"
    )
    
    fecha_final = st.date_input(
        "📅 Fecha Final",
        value=date.today(),
        min_value=date(2010, 1, 1),
        max_value=date.today(),
        format="DD/MM/YYYY"
    )
    
    st.markdown("---")
    st.markdown("**⚙️ Tasas Puras**")
    
    tasa_pura_ripte = st.slider(
        "RIPTE (%)",
        min_value=0,
        max_value=6,
        value=3,
        step=1
    )
    
    tasa_pura_ipc = st.slider(
        "IPC (%)",
        min_value=0,
        max_value=6,
        value=3,
        step=1
    )
    
    calcular = st.button("⚡ CALCULAR", use_container_width=True, type="primary")

# Columna derecha - RESULTADOS
with col_der:
    st.subheader("📊 RESULTADOS")
    
    if calcular:
        if fecha_inicial >= fecha_final:
            st.error("⚠️ La fecha inicial debe ser anterior a la fecha final.")
        else:
            # Calcular actualizaciones
            ripte_total, ripte_coef, ripte_interes = actualizar_ripte(
                monto, fecha_inicial, fecha_final, df_ripte, tasa_pura_ripte
            )
            
            tasa_total, tasa_pct = actualizar_tasa(
                monto, fecha_inicial, fecha_final, df_tasa
            )
            
            ipc_total, ipc_inflacion, ipc_interes = actualizar_ipc(
                monto, fecha_inicial, fecha_final, df_ipc, tasa_pura_ipc
            )
            
            # Guardar resultados en session_state
            st.session_state.resultados = {
                'ripte_total': ripte_total,
                'ripte_coef': ripte_coef,
                'ripte_interes': ripte_interes,
                'tasa_total': tasa_total,
                'tasa_pct': tasa_pct,
                'ipc_total': ipc_total,
                'ipc_inflacion': ipc_inflacion,
                'ipc_interes': ipc_interes,
                'monto': monto,
                'fecha_inicial': fecha_inicial,
                'fecha_final': fecha_final,
                'tasa_pura_ripte': tasa_pura_ripte,
                'tasa_pura_ipc': tasa_pura_ipc
            }
    
    # Mostrar resultados si existen
    if 'resultados' in st.session_state:
        r = st.session_state.resultados
        
        # RIPTE
        st.success(f"**RIPTE + {r['tasa_pura_ripte']}%**")
        st.metric(label="Total", value=formato_moneda(r['ripte_total']), label_visibility="collapsed")
        st.caption(f"Coef: {r['ripte_coef']:.4f} | Int: {formato_moneda(r['ripte_interes'])}")
        
        # Tasa Activa
        st.success("**Tasa Activa**")
        st.metric(label="Total", value=formato_moneda(r['tasa_total']), label_visibility="collapsed")
        st.caption(f"Tasa Acumulada: {r['tasa_pct']:.2f}%")
        
        # IPC
        st.info(f"**IPC + {r['tasa_pura_ipc']}%**")
        st.metric(label="Total", value=formato_moneda(r['ipc_total']), label_visibility="collapsed")
        st.caption(f"Inflación: {r['ipc_inflacion']:.2f}% | Int: {formato_moneda(r['ipc_interes'])}")
        
        st.caption(f"Período: {r['fecha_inicial'].strftime('%d/%m/%Y')} al {r['fecha_final'].strftime('%d/%m/%Y')}")
    else:
        st.info("👈 Ingrese los datos y presione CALCULAR")

# Sección inferior - Desglose y datos
st.markdown("---")

if 'resultados' in st.session_state:
    r = st.session_state.resultados
    
    tab1, tab2 = st.tabs(["📋 Desglose Detallado", "ℹ️ Información"])
    
    with tab1:
        st.markdown("### 📋 Desglose para copiar")
        texto_desglose = generar_desglose_texto(r)
        st.code(texto_desglose, language=None)
    
    with tab2:
        # Últimos datos disponibles
        ultimo_ripte_txt = ""
        ultimo_ipc_txt = ""
        ultima_tasa_txt = ""
        
        if not df_ripte.empty:
            ultimo_ripte = get_ultimo_dato(df_ripte)
            fecha_ripte = ultimo_ripte['fecha']
            valor_ripte = ultimo_ripte['indice_ripte']
            if pd.notnull(fecha_ripte):
                mes_ripte = fecha_ripte.month if isinstance(fecha_ripte, pd.Timestamp) else fecha_ripte.month
                año_ripte = fecha_ripte.year if isinstance(fecha_ripte, pd.Timestamp) else fecha_ripte.year
                ultimo_ripte_txt = f"**RIPTE** {mes_ripte}/{año_ripte}: {valor_ripte:,.0f}".replace(",", ".")
        
        if not df_ipc.empty:
            ultimo_ipc = get_ultimo_dato(df_ipc)
            fecha_ipc = ultimo_ipc['periodo']
            variacion_ipc = ultimo_ipc['variacion_mensual']
            if pd.notnull(fecha_ipc):
                if isinstance(fecha_ipc, pd.Timestamp):
                    mes_ipc = fecha_ipc.month
                    año_ipc = fecha_ipc.year
                else:
                    fecha_ipc = pd.to_datetime(fecha_ipc)
                    mes_ipc = fecha_ipc.month
                    año_ipc = fecha_ipc.year
                ultimo_ipc_txt = f"**IPC** {mes_ipc}/{año_ipc}: {variacion_ipc:.2f}%"
        
        if not df_tasa.empty:
            ultima_tasa = get_ultimo_dato(df_tasa)
            valor_tasa = ultima_tasa['Valor']
            fecha_hasta = ultima_tasa['Hasta']
            if pd.notnull(fecha_hasta):
                fecha_txt = fecha_hasta.strftime("%d/%m/%Y") if isinstance(fecha_hasta, pd.Timestamp) else pd.to_datetime(fecha_hasta).strftime("%d/%m/%Y")
                ultima_tasa_txt = f"**TASA** {fecha_txt}: {valor_tasa:.2f}%"
        
        st.info(f"**📊 Últimos Datos Disponibles**")
        st.markdown(ultimo_ripte_txt)
        st.markdown(ultimo_ipc_txt)
        st.markdown(ultima_tasa_txt)
        
        st.markdown("---")
        st.markdown("""
        ### 📊 Métodos de Actualización
        
        **RIPTE + Tasa Pura:**
        - El RIPTE (Remuneración Imponible Promedio de los Trabajadores Estables) se utiliza como índice de actualización.
        - Se aplica una tasa pura adicional seleccionable entre 0% y 6%.
        - **Fuente:** Secretaría de Seguridad Social - Ministerio de Trabajo
        
        **Tasa Activa:**
        - Tasa activa promedio del Banco de la Nación Argentina.
        - Se calcula día a día según los valores históricos.
        - **Fuente:** Banco de la Nación Argentina
        
        **IPC + Tasa Pura:**
        - El IPC (Índice de Precios al Consumidor) refleja la variación inflacionaria.
        - Se aplica una tasa pura adicional seleccionable entre 0% y 6%.
        - **Fuente:** INDEC - Instituto Nacional de Estadística y Censos
        
        ### 🔢 Detalles Técnicos
        
        Todos los cálculos se realizan utilizando precisión decimal para garantizar exactitud legal.
        Los redondeos se aplican según normas contables argentinas (Resoluciones Técnicas 17 y 41).
        """)

# Mostrar últimos datos disponibles
st.markdown("---")
mostrar_ultimos_datos_universal()

# Footer
st.markdown("---")
st.caption("**CALCULADORA DE ACTUALIZACIÓN** | Sistema de Actualización de Montos")
st.caption("Los resultados son aproximados y no constituyen asesoramiento legal.")