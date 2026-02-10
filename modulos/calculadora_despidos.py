#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CALCULADORA DE DESPIDOS
Sistema de cálculo de indemnizaciones por despido con actualizaciones
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import base64
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from utils.data_loader import get_ultimo_dato
from utils.navegacion import mostrar_sidebar_navegacion
from utils.info_datasets import mostrar_ultimos_datos_universal
from utils.funciones_comunes import safe_parse_date, days_in_month, formato_moneda

# Sidebar de navegación
mostrar_sidebar_navegacion('despidos')

# Título de la app
st.markdown("# 📊 CALCULADORA DE DESPIDOS")
st.markdown("### Indemnizaciones Laborales - Ley 20.744")
st.markdown("---")

# Cargar datasets
def cargar_datasets():
    """Carga los datasets de RIPTE, Tasa e IPC"""
    # RIPTE
    df_ripte = pd.read_csv("data/dataset_ripte.csv", encoding='utf-8')
    df_ripte['fecha'] = pd.to_datetime(
        df_ripte['año'].astype(str)
        + '-'
        + df_ripte['mes'].str[:3].map({
            'Ene': '01', 'Feb': '02', 'Mar': '03', 'Abr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Ago': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dic': '12'
        })
        + '-01'
    )

    # Tasa Activa
    df_tasa = pd.read_csv("data/dataset_tasa.csv", encoding='utf-8')
    df_tasa['Desde'] = pd.to_datetime(df_tasa['Desde'], format='%d/%m/%Y', dayfirst=True)
    df_tasa['Hasta'] = pd.to_datetime(df_tasa['Hasta'], format='%d/%m/%Y', dayfirst=True)

    df_tasa['Valor'] = (
        df_tasa['Valor']
        .astype(str)
        .str.replace(',', '.', regex=False)
        .astype(float)
    )

    # IPC
    df_ipc = pd.read_csv("data/dataset_ipc.csv", encoding='utf-8')
    df_ipc['periodo'] = pd.to_datetime(
        df_ipc['periodo'],
        dayfirst=True,
        format='mixed',
        errors='coerce'
    )

    return df_ripte, df_tasa, df_ipc


# Función para calcular antigüedad
def calcular_antiguedad(fecha_ingreso, fecha_despido):
    """Calcula años y meses de antigüedad"""
    años = fecha_despido.year - fecha_ingreso.year
    meses = fecha_despido.month - fecha_ingreso.month
    dias = fecha_despido.day - fecha_ingreso.day
    
    if dias < 0:
        meses -= 1
    
    if meses < 0:
        años -= 1
        meses += 12
    
    # Si los meses son mayor a 3, se considera un año completo adicional
    if meses > 3:
        años += 1
        meses = 0
    
    return años, meses

# Función para calcular días de vacaciones según antigüedad
def calcular_dias_vacaciones(años_antiguedad):
    """Calcula días de vacaciones según LCT 20744"""
    if años_antiguedad < 5:
        return 14
    elif años_antiguedad < 10:
        return 21
    elif años_antiguedad < 20:
        return 28
    else:
        return 35

# Función para actualizar por RIPTE
def actualizar_ripte(monto_base, fecha_inicial, fecha_final, df_ripte):
    """Actualiza un monto por RIPTE + 3% - adaptado para CSV invertido"""
    try:
        if df_ripte.empty:
            return monto_base
        
        fecha_pmi = pd.to_datetime(fecha_inicial)
        fecha_final_date = pd.to_datetime(fecha_final)
        
        # Obtener RIPTE inicial (CSV invertido: más reciente primero)
        ripte_pmi_data = df_ripte[df_ripte['fecha'] <= fecha_pmi]
        if ripte_pmi_data.empty:
            ripte_pmi = float(df_ripte.iloc[-1]['indice_ripte'])  # Más antiguo
        else:
            ripte_pmi = float(ripte_pmi_data.iloc[0]['indice_ripte'])  # Más reciente <= fecha_pmi
        
        # Obtener RIPTE final (CSV invertido: más reciente primero)
        ripte_final_data = df_ripte[df_ripte['fecha'] <= fecha_final_date]
        if ripte_final_data.empty:
            ripte_final = float(df_ripte.iloc[-1]['indice_ripte'])  # Más antiguo
        else:
            ripte_final = float(ripte_final_data.iloc[0]['indice_ripte'])  # Más reciente <= fecha_final
        
        # Calcular coeficiente RIPTE
        coeficiente = ripte_final / ripte_pmi if ripte_pmi > 0 else 1.0
        
        # Aplicar RIPTE
        ripte_actualizado = monto_base * coeficiente
        
        # Calcular días para interés 3%
        dias = (fecha_final_date - fecha_pmi).days
        factor_dias = dias / 365.0
        
        # Aplicar 3% proporcional
        interes_puro = ripte_actualizado * 0.03 * factor_dias
        
        total_ripte_3 = ripte_actualizado + interes_puro
        
        return total_ripte_3
    except Exception as e:
        st.error(f"Error en cálculo de RIPTE: {str(e)}")
        return monto_base

# Función para actualizar por Tasa Activa
def actualizar_tasa(monto_base, fecha_inicial, fecha_final, df_tasa):
    """Actualiza un monto por Tasa Activa"""
    try:
        if df_tasa.empty:
            return monto_base
        
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
        
        return total_actualizado
    except Exception as e:
        st.error(f"Error en cálculo de tasa: {str(e)}")
        return monto_base

# Función para calcular IPC acumulado
def calcular_ipc_acumulado(fecha_inicial, fecha_final, df_ipc):
    """Calcula el IPC acumulado entre dos fechas"""
    try:
        if df_ipc.empty:
            return 0.0
        
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
            return 0.0
        
        factor_acumulado = 1.0
        for _, row in ipc_periodo.iterrows():
            variacion = row['variacion_mensual']
            if not pd.isna(variacion):
                factor_acumulado *= (1 + variacion / 100)
        
        inflacion_acumulada = (factor_acumulado - 1) * 100
        return inflacion_acumulada
    except Exception as e:
        st.error(f"Error en cálculo de IPC: {str(e)}")
        return 0.0

# Función para formatear montos

# Función para generar PDF
def generar_pdf(datos_calculo, datos_actualizacion):
    """Genera un PDF con los resultados"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, 
                           topMargin=2*cm, bottomMargin=2*cm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#2E86AB'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    elements.append(Paragraph("LIQUIDACIÓN DE INDEMNIZACIÓN POR DESPIDO", title_style))
    
    # Expediente y carátula si están disponibles
    if datos_calculo.get('nro_expediente') or datos_calculo.get('caratula'):
        expediente_style = ParagraphStyle(
            'Expediente',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#666666'),
            spaceAfter=10,
            alignment=TA_CENTER
        )
        
        if datos_calculo.get('nro_expediente'):
            elements.append(Paragraph(f"<b>Expediente Nro:</b> {datos_calculo['nro_expediente']}", expediente_style))
        
        if datos_calculo.get('caratula'):
            elements.append(Paragraph(f"<b>Carátula:</b> {datos_calculo['caratula']}", expediente_style))
    
    elements.append(Spacer(1, 0.5*cm))
    
    # Datos del trabajador
    data_trabajador = [
        ['Fecha de Ingreso:', datos_calculo['fecha_ingreso']],
        ['Fecha de Despido:', datos_calculo['fecha_despido']],
        ['Antigüedad:', f"{datos_calculo['años']} años"],
        ['Salario Mensual Bruto:', formato_moneda(datos_calculo['salario'])],
        ['Preaviso:', datos_calculo['preaviso']],
    ]
    
    t1 = Table(data_trabajador, colWidths=[6*cm, 8*cm])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F5E8')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    
    elements.append(t1)
    elements.append(Spacer(1, 0.7*cm))
    
    # Conceptos
    elements.append(Paragraph("DETALLE DE CONCEPTOS", styles['Heading2']))
    elements.append(Spacer(1, 0.3*cm))
    
    data_conceptos = [
        ['Concepto', 'Importe'],
        ['Antigüedad Art. 245', formato_moneda(datos_calculo['antiguedad_245'])],
    ]
    
    if datos_calculo.get('sustitutiva_preaviso', 0) > 0:
        data_conceptos.append(['Sustitutiva de Preaviso', formato_moneda(datos_calculo['sustitutiva_preaviso'])])
        data_conceptos.append(['SAC Preaviso', formato_moneda(datos_calculo['sac_preaviso'])])
    
    data_conceptos.extend([
        ['Días trabajados del Mes', formato_moneda(datos_calculo['dias_trabajados'])],
        ['Integración mes de Despido', formato_moneda(datos_calculo['integracion_mes'])],
        ['SAC Integración mes', formato_moneda(datos_calculo['sac_integracion'])],
        ['SAC Proporcional', formato_moneda(datos_calculo['sac_proporcional'])],
        ['Vacaciones no Gozadas', formato_moneda(datos_calculo['vacaciones'])],
        ['SAC Vacaciones', formato_moneda(datos_calculo['sac_vacaciones'])],
    ])
    
    # Agregar otros conceptos si existe
    if datos_calculo.get('otros_conceptos', 0) > 0:
        data_conceptos.append(['Otros Conceptos', formato_moneda(datos_calculo['otros_conceptos'])])
    
    t2 = Table(data_conceptos, colWidths=[10*cm, 4*cm])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    
    elements.append(t2)
    elements.append(Spacer(1, 0.5*cm))
    
    # Total - usar total_final si existe, sino usar total
    total_a_mostrar = datos_calculo.get('total_final', datos_calculo['total'])
    data_total = [
        ['INDEMNIZACIÓN TOTAL', formato_moneda(total_a_mostrar)]
    ]
    
    t3 = Table(data_total, colWidths=[10*cm, 4*cm])
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F18F01')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    
    elements.append(t3)
    elements.append(Spacer(1, 0.7*cm))
    
    # Actualizaciones
    elements.append(Paragraph("ACTUALIZACIONES", styles['Heading2']))
    elements.append(Spacer(1, 0.3*cm))
    
    data_act = [
        ['Método', 'Monto Actualizado'],
        ['Actualización RIPTE + 3%', formato_moneda(datos_actualizacion['ripte'])],
        ['Actualización Tasa Activa', formato_moneda(datos_actualizacion['tasa'])],
    ]
    
    t4 = Table(data_act, colWidths=[10*cm, 4*cm])
    t4.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#28a745')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    
    elements.append(t4)
    elements.append(Spacer(1, 0.5*cm))
    
    # Nota
    nota_style = ParagraphStyle(
        'Note',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    elements.append(Paragraph("Nota: Los resultados indicados son aproximados.", nota_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# Cargar datasets
df_ripte, df_tasa, df_ipc = cargar_datasets()

# Formulario de entrada y resultados en dos columnas
col_inputs, col_results = st.columns([1, 1])

with col_inputs:
    st.subheader("📋 Datos del Trabajador")
    
    fecha_ingreso = st.date_input(
        "Fecha de Ingreso",
        value=date(2020, 11, 5),
        min_value=date(1990, 1, 1),
        max_value=date.today(),
        format="DD/MM/YYYY",
        key="fecha_ingreso_input"
    )

    fecha_despido = st.date_input(
        "Fecha de Despido",
        value=date(2025, 11, 16),
        min_value=fecha_ingreso,
        max_value=date.today(),
        format="DD/MM/YYYY",
        key="fecha_despido_input"
    )

    fecha_liquidacion = st.date_input(
        "Fecha de Liquidación",
        value=date.today(),
        min_value=fecha_despido,
        max_value=date.today() + timedelta(days=365),
        format="DD/MM/YYYY",
        key="fecha_liquidacion_input"
    )

    salario = st.number_input(
        "Salario Mensual Bruto ($)",
        min_value=0.0,
        value=150000.0,
        step=1000.0,
        format="%.2f",
        key="salario_input"
    )

    se_pago_preaviso = st.checkbox("¿Se pagó preaviso?", value=False, key="preaviso_checkbox")
    
    calcular_btn = st.button("⚡ CALCULAR INDEMNIZACIÓN", use_container_width=True, type="primary", key="calcular_button")

with col_results:
    if calcular_btn:
        
        # Calcular antigüedad
        años, meses = calcular_antiguedad(fecha_ingreso, fecha_despido)
        
        # Calcular conceptos con Decimal para precisión
        # 1. Antigüedad Art. 245
        antiguedad_245 = Decimal(str(salario)) * Decimal(str(años))
        
        # 2. Sustitutiva de preaviso
        if not se_pago_preaviso:
            if años < 5:
                sustitutiva_preaviso = Decimal(str(salario)) * Decimal('1')
            else:
                sustitutiva_preaviso = Decimal(str(salario)) * Decimal('2')
            sac_preaviso = sustitutiva_preaviso / Decimal('12')
        else:
            sustitutiva_preaviso = Decimal('0')
            sac_preaviso = Decimal('0')
        
        # 3. Días trabajados del mes
        dias_mes = days_in_month(fecha_despido)
        dias_trabajados_mes = fecha_despido.day
        dias_trabajados = (Decimal(str(salario)) / Decimal(str(dias_mes))) * Decimal(str(dias_trabajados_mes))
        
        # 4. Integración mes de despido
        if fecha_despido.day == dias_mes:
            integracion_mes = Decimal('0')
            sac_integracion = Decimal('0')
        else:
            dias_integracion = dias_mes - dias_trabajados_mes
            integracion_mes = (Decimal(str(salario)) / Decimal(str(dias_mes))) * Decimal(str(dias_integracion))
            sac_integracion = integracion_mes / Decimal('12')
        
        # 5. SAC Proporcional
        if fecha_despido.month <= 6:
            dias_desde_sac = (fecha_despido - date(fecha_despido.year, 1, 1)).days
        else:
            dias_desde_sac = (fecha_despido - date(fecha_despido.year, 7, 1)).days
        
        sac_proporcional = (Decimal(str(salario)) / Decimal('365')) * Decimal(str(dias_desde_sac))
        
        # 6. Vacaciones no gozadas
        dias_vacaciones = calcular_dias_vacaciones(años)
        valor_dia_vacaciones = Decimal(str(salario)) / Decimal('25')
        vacaciones = valor_dia_vacaciones * Decimal(str(dias_vacaciones))
        sac_vacaciones = vacaciones / Decimal('12')
        
        # Total - redondear cada concepto a 2 decimales
        antiguedad_245 = antiguedad_245.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        sustitutiva_preaviso = sustitutiva_preaviso.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        sac_preaviso = sac_preaviso.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        dias_trabajados = dias_trabajados.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        integracion_mes = integracion_mes.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        sac_integracion = sac_integracion.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        sac_proporcional = sac_proporcional.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        vacaciones = vacaciones.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        sac_vacaciones = sac_vacaciones.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        total = (antiguedad_245 + sustitutiva_preaviso + sac_preaviso + 
                 dias_trabajados + integracion_mes + sac_integracion + 
                 sac_proporcional + vacaciones + sac_vacaciones)
        
        # Guardar datos en session_state
        st.session_state.datos_calculo = {
            'fecha_ingreso': fecha_ingreso.strftime("%d/%m/%Y"),
            'fecha_despido': fecha_despido.strftime("%d/%m/%Y"),
            'fecha_liquidacion': fecha_liquidacion.strftime("%d/%m/%Y"),
            'años': años,
            'meses': meses,
            'salario': float(salario),
            'preaviso': 'Se pagó' if se_pago_preaviso else 'Sin preaviso',
            'antiguedad_245': float(antiguedad_245),
            'sustitutiva_preaviso': float(sustitutiva_preaviso),
            'sac_preaviso': float(sac_preaviso),
            'dias_trabajados': float(dias_trabajados),
            'integracion_mes': float(integracion_mes),
            'sac_integracion': float(sac_integracion),
            'sac_proporcional': float(sac_proporcional),
            'vacaciones': float(vacaciones),
            'sac_vacaciones': float(sac_vacaciones),
            'total': float(total),
            # Datos adicionales para detalles
            'dias_trabajados_mes': dias_trabajados_mes,
            'dias_integracion': dias_mes - dias_trabajados_mes if fecha_despido.day != dias_mes else 0,
            'dias_desde_sac': dias_desde_sac,
            'semestre_sac': '1er' if fecha_despido.month <= 6 else '2do',
            'dias_vacaciones': dias_vacaciones,
            'salarios_preaviso': 1 if años < 5 else 2
        }
        
        # Calcular actualizaciones
        total_float = st.session_state.datos_calculo['total']
        
        actualizado_ripte = actualizar_ripte(total_float, fecha_despido, fecha_liquidacion, df_ripte)
        actualizado_tasa = actualizar_tasa(total_float, fecha_despido, fecha_liquidacion, df_tasa)
        ipc_acumulado = calcular_ipc_acumulado(fecha_despido, fecha_liquidacion, df_ipc)
        
        st.session_state.datos_actualizacion = {
            'ripte': actualizado_ripte,
            'tasa': actualizado_tasa,
            'ipc': ipc_acumulado
        }
        
        # Guardar rubros para el PDF
        st.session_state.datos_rubros = {
            'Antigüedad Art. 245': float(antiguedad_245),
            'Sustitutiva de Preaviso': float(sustitutiva_preaviso),
            'SAC Preaviso': float(sac_preaviso),
            'Días trabajados del Mes': float(dias_trabajados),
            'Integración mes de Despido': float(integracion_mes),
            'SAC Integración': float(sac_integracion),
            'SAC Proporcional': float(sac_proporcional),
            'Vacaciones no Gozadas': float(vacaciones),
            'SAC Vacaciones': float(sac_vacaciones),
            'total': float(total),
            'antiguedad_años': años
        }

# Mostrar resultados si existen
if 'datos_calculo' in st.session_state:
    with col_results:
        st.subheader("💰 Liquidación")
        
        datos = st.session_state.datos_calculo
        
        # Texto para antigüedad
        if datos['meses'] > 0:
            texto_antiguedad = f"({datos['años']} años y {datos['meses']} meses)"
        else:
            texto_antiguedad = f"({datos['años']} años)"
        
        # Construir tabla de conceptos de forma compacta
        conceptos_data = []
        
        conceptos_data.append(["**Antigüedad Art. 245** " + texto_antiguedad, formato_moneda(datos['antiguedad_245'])])
        
        if datos['sustitutiva_preaviso'] > 0:
            salarios_txt = f"({datos['salarios_preaviso']} salario{'s' if datos['salarios_preaviso'] > 1 else ''})"
            conceptos_data.append(["**Sustitutiva de Preaviso** " + salarios_txt, formato_moneda(datos['sustitutiva_preaviso'])])
            conceptos_data.append(["**SAC Preaviso**", formato_moneda(datos['sac_preaviso'])])
        
        conceptos_data.append([f"**Días trabajados del Mes** ({datos['dias_trabajados_mes']} días)", formato_moneda(datos['dias_trabajados'])])
        
        if datos['integracion_mes'] > 0:
            conceptos_data.append([f"**Integración mes de Despido** ({datos['dias_integracion']} días)", formato_moneda(datos['integracion_mes'])])
            conceptos_data.append(["**SAC Integración**", formato_moneda(datos['sac_integracion'])])
        
        conceptos_data.append([f"**SAC Proporcional** ({datos['dias_desde_sac']} días del {datos['semestre_sac']} sem.)", formato_moneda(datos['sac_proporcional'])])
        conceptos_data.append([f"**Vacaciones no Gozadas** ({datos['dias_vacaciones']} días)", formato_moneda(datos['vacaciones'])])
        conceptos_data.append(["**SAC Vacaciones**", formato_moneda(datos['sac_vacaciones'])])
        
        # Crear DataFrame para mostrar como tabla
        df_conceptos = pd.DataFrame(conceptos_data, columns=["Concepto", "Importe"])
        
        # Mostrar como markdown table compacta
        for concepto, importe in conceptos_data:
            col_c, col_i = st.columns([3, 1])
            with col_c:
                st.markdown(concepto, unsafe_allow_html=True)
            with col_i:
                st.markdown(f"**{importe}**")
        
        # Total final en rojo
        total_final = datos['total']
        st.error("**💰 INDEMNIZACIÓN TOTAL**")
        st.metric(
            label="Total",
            value=formato_moneda(total_final),
            label_visibility="collapsed"
        )
else:
    with col_results:
        st.info("👈 Ingrese los datos y presione CALCULAR")

# Actualizaciones estilo LRT
if 'datos_actualizacion' in st.session_state:
    st.markdown("---")
    st.markdown("### 📈 Actualizaciones e intereses")
    
    datos_act = st.session_state.datos_actualizacion
    
    # Determinar cuál es mayor
    es_ripte_mayor = datos_act['ripte'] >= datos_act['tasa']
    
    # Primera fila - RIPTE y TASA (2 columnas)
    col_1, col_2 = st.columns(2)
    
    with col_1:
        st.success("**RIPTE + 3% ANUAL**") if es_ripte_mayor else st.info("**RIPTE + 3% ANUAL**")
        st.metric(
            label="Total Actualizado",
            value=formato_moneda(datos_act['ripte']),
            delta=f"+{formato_moneda(datos_act['ripte'] - st.session_state.datos_rubros['total'])}" if 'datos_rubros' in st.session_state else None
        )
        with st.expander("Ver detalle"):
            st.write(f"**Período:** {st.session_state.datos_calculo['fecha_despido']} a {st.session_state.datos_calculo['fecha_liquidacion']}")
    
    with col_2:
        st.success("**TASA ACTIVA BNA**") if not es_ripte_mayor else st.info("**TASA ACTIVA BNA**")
        st.metric(
            label="Total Actualizado",
            value=formato_moneda(datos_act['tasa']),
            delta=f"+{formato_moneda(datos_act['tasa'] - st.session_state.datos_rubros['total'])}" if 'datos_rubros' in st.session_state else None
        )
        with st.expander("Ver detalle"):
            st.write(f"**Período:** {st.session_state.datos_calculo['fecha_despido']} a {st.session_state.datos_calculo['fecha_liquidacion']}")
    
    st.markdown("---")
    
    # Segunda fila - Inflación (columna derecha, dejando espacio a la izquierda)
    col_vacio, col_inflacion = st.columns(2)
    
    with col_vacio:
        pass  # Espacio para futura tasa
    
    with col_inflacion:
        st.error("**INFLACIÓN ACUMULADA (Referencia)**")
        st.metric(
            label="Total Acumulado",
            value=f"{datos_act['ipc']:.2f}%"
        )
        with st.expander("Ver detalle"):
            st.write(f"**Período:** {st.session_state.datos_calculo['fecha_despido']} a {st.session_state.datos_calculo['fecha_liquidacion']}")
    
    # Últimos datos disponibles
    ultimo_ripte_txt = ""
    ultimo_ipc_txt = ""
    ultima_tasa_txt = ""
    
    # RIPTE
    if not df_ripte.empty:
        ultimo_ripte = get_ultimo_dato(df_ripte)
        fecha_ripte = ultimo_ripte['fecha']
        valor_ripte = ultimo_ripte['indice_ripte']
        if pd.notnull(fecha_ripte):
            if isinstance(fecha_ripte, pd.Timestamp):
                mes_ripte = fecha_ripte.month
                año_ripte = fecha_ripte.year
            else:
                mes_ripte = fecha_ripte.month
                año_ripte = fecha_ripte.year
            ultimo_ripte_txt = f"RIPTE {mes_ripte}/{año_ripte}: {valor_ripte:,.0f}"
    
    # IPC
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
            ultimo_ipc_txt = f"IPC {mes_ipc}/{año_ipc}: {variacion_ipc:.2f}%"
    
    # TASA ACTIVA
    if not df_tasa.empty:
        ultima_tasa = get_ultimo_dato(df_tasa)
        valor_tasa = ultima_tasa['Valor']
        fecha_hasta = ultima_tasa['Hasta']
        if pd.notnull(fecha_hasta):
            if isinstance(fecha_hasta, pd.Timestamp):
                fecha_txt = fecha_hasta.strftime("%d/%m/%Y")
            else:
                fecha_txt = pd.to_datetime(fecha_hasta).strftime("%d/%m/%Y")
            ultima_tasa_txt = f"TASA ACTIVA {fecha_txt}: {valor_tasa:.2f}%"

# Tabs para resultados y PDF (fuera del bloque condicional)
if 'datos_actualizacion' in st.session_state and 'datos_rubros' in st.session_state:
    st.markdown("---")
    tab_pdf, tab_info = st.tabs(["🖨️ Imprimir PDF", "ℹ️ Información"])
    
    datos_act = st.session_state.datos_actualizacion
    
    with tab_pdf:
        st.subheader("🖨️ Imprimir PDF")
        
        # Inputs opcionales para PDF
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            nro_expediente = st.text_input("Nro. Expediente (opcional)", key="nro_exp_despidos", help="Aparecerá en el PDF si lo completa")
        with col_exp2:
            caratula = st.text_input("Carátula (opcional)", key="caratula_despidos", help="Aparecerá en el PDF si lo completa")
        
        st.markdown("---")
        
        # Determinar método más favorable
        es_ripte_mayor = datos_act['ripte'] >= datos_act['tasa']
        
        # HTML estilo LRT moderno mejorado
        rubros = st.session_state.datos_rubros
        
        # Preparar header con expediente y carátula si existen
        header_extra = ""
        if nro_expediente or caratula:
            header_extra = '<div style="font-size: 10px; color: #718096; margin-top: 5px;">'
            if nro_expediente:
                header_extra += f'<strong>Expte.:</strong> {nro_expediente}'
            if nro_expediente and caratula:
                header_extra += ' | '
            if caratula:
                header_extra += f'<strong>Carátula:</strong> {caratula}'
            header_extra += '</div>'
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        @page {{size: A4; margin: 1cm;}}
        * {{box-sizing: border-box; margin: 0; padding: 0;}}
        body {{font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; font-size: 11px; padding: 20px; line-height: 1.4;}}
        .container {{max-width: 100%;}}
        .header {{text-align: center; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #e2e8f0;}}
        .header h1 {{font-size: 20px; color: #2d3748; margin-bottom: 5px;}}
        .header p {{font-size: 11px; color: #718096;}}
        
        .rubros-section {{margin: 15px 0;}}
        .rubros-table {{width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);}}
        .rubros-table tr {{border-bottom: 1px solid #e2e8f0;}}
        .rubros-table tr:last-child {{border-bottom: none;}}
        .rubros-table td {{padding: 8px 12px; font-size: 10px;}}
        .rubros-table td:first-child {{color: #4a5568; width: 70%;}}
        .rubros-table td:last-child {{font-weight: bold; color: #2d3748; text-align: right; width: 30%;}}
        
        .formula-section {{background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: center;}}
        .formula-title {{font-size: 13px; font-weight: bold; margin-bottom: 8px;}}
        .formula-total {{font-size: 32px; font-weight: bold; margin: 10px 0;}}
        .formula-note {{font-size: 9px; opacity: 0.9;}}
        
        .actualizaciones {{margin: 15px 0;}}
        .act-row {{display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px;}}
        .act-card {{padding: 12px; border-radius: 8px; text-align: center;}}
        .act-card.winner {{background: rgba(40, 167, 69, 0.1); border: 2px solid #28a745;}}
        .act-card.normal {{background: rgba(128, 128, 128, 0.1); border: 1px solid #cbd5e0;}}
        .act-title {{font-size: 12px; font-weight: bold; color: #2d3748; margin-bottom: 5px;}}
        .act-value {{font-size: 28px; font-weight: bold; color: #2d3748; margin: 5px 0;}}
        .act-badge {{display: inline-block; background: #28a745; color: white; padding: 3px 8px; border-radius: 12px; font-size: 8px; font-weight: bold; margin-top: 5px;}}
        .act-detail {{font-size: 10px; color: #718096; margin-top: 5px;}}
        
        .inflacion-full {{padding: 12px; border-radius: 8px; text-align: center; background: rgba(220, 53, 69, 0.1); border: 1px solid #dc3545; margin-top: 10px;}}
        
        .period-info {{background: #f7fafc; padding: 10px; border-radius: 8px; font-size: 10px; text-align: center; color: #4a5568; margin: 15px 0; line-height: 1.4;}}
        
        .footer {{text-align: center; font-size: 9px; color: #a0aec0; margin-top: 12px; padding-top: 10px; border-top: 1px solid #e2e8f0; line-height: 1.3;}}
        
        .print-btn {{background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-size: 14px; font-weight: bold; margin-bottom: 15px; transition: background 0.3s;}}
        .print-btn:hover {{background: #5568d3;}}
        
        @media print {{.no-print {{display: none;}}}}
    </style>
</head>
<body>
    <button class="print-btn no-print" onclick="window.print()">🖨️ IMPRIMIR PDF</button>
    
    <div class="container">
        <div class="header">
            <h1>⚖️ LIQUIDACIÓN POR DESPIDO</h1>
            <p>Ley 20.744 - Contrato de Trabajo</p>
            {header_extra}
        </div>
        
        <div class="rubros-section">
            <table class="rubros-table">
"""
        
        # Agregar rubros en tabla vertical
        for concepto, monto in rubros.items():
            if concepto not in ['total', 'antiguedad_años'] and monto > 0:
                html_content += f'                <tr><td>{concepto}</td><td>${monto:,.2f}</td></tr>\n'
        
        html_content += f"""
            </table>
        </div>
        
        <div class="formula-section">
            <div class="formula-title">💰 INDEMNIZACIÓN POR DESPIDO</div>
            <div class="formula-total">${rubros['total']:,.2f}</div>
            <div class="formula-note">Total de conceptos liquidados</div>
        </div>
        
        <div class="actualizaciones">
            <div class="act-row">
                <div class="act-card {'winner' if es_ripte_mayor else 'normal'}">
                    <div class="act-title">📈 RIPTE + 3%</div>
                    <div class="act-value">${datos_act['ripte']:,.2f}</div>
                    {'<span class="act-badge">✓ MÁS FAVORABLE</span>' if es_ripte_mayor else ''}
                    <div class="act-detail">Coef: {(datos_act['ripte'] / rubros['total']):.4f}</div>
                </div>
                <div class="act-card {'winner' if not es_ripte_mayor else 'normal'}">
                    <div class="act-title">💵 TASA ACTIVA BNA</div>
                    <div class="act-value">${datos_act['tasa']:,.2f}</div>
                    {'<span class="act-badge">✓ MÁS FAVORABLE</span>' if not es_ripte_mayor else ''}
                    <div class="act-detail">Tasa acum: {((datos_act['tasa'] / rubros['total'] - 1) * 100):.2f}%</div>
                </div>
            </div>
            
            <div class="inflacion-full">
                <div class="act-title">📊 INFLACIÓN ACUMULADA (Referencia)</div>
                <div class="act-value">{datos_act['ipc']:.2f}%</div>
                <div class="act-detail">Acumulado período IPC</div>
            </div>
        </div>
        
        <div class="period-info">
            📅 <strong>Período:</strong> {st.session_state.datos_calculo['fecha_despido']} - {st.session_state.datos_calculo['fecha_liquidacion']} | 
            👤 <strong>Antigüedad:</strong> {rubros.get('antiguedad_años', 0)} años | 
            💰 <strong>Salario:</strong> ${st.session_state.datos_calculo['salario']:,.2f}
        </div>
        
        <div class="footer">
            Sistema Integrado - Tribunal de Trabajo 2 Quilmes<br>
            Generado el {date.today().strftime('%d/%m/%Y')}
        </div>
    </div>
</body>
</html>
"""
        
        # Mostrar PDF en iframe
        st.components.v1.html(html_content, height=950, scrolling=True)


    
    with tab_info:
        st.markdown("""
        ### 📘 Marco Legal - Ley 20.744 (LCT)
        
        **Antigüedad (Art. 245):** Se calcula 1 mes de salario por cada año de servicio o fracción mayor a 3 meses.
        
        **Sustitutiva de Preaviso:** 
        - Antigüedad menor a 5 años: 1 mes de salario
        - Antigüedad mayor a 4 años: 2 meses de salario
        
        **SAC Preaviso:** Doceava parte de la sustitutiva de preaviso.
        
        **Días Trabajados:** Se divide el salario por la cantidad de días del mes y se multiplica por los días trabajados durante el mes de despido.
        
        **Integración Mes de Despido:** Corresponde a los días que restan para completar el mes. No se paga si el despido coincide con el último día del mes.
        
        **SAC Integración:** Doceava parte de la integración del mes.
        
        **SAC Proporcional:** Se calcula proporcionalmente desde el último aguinaldo pagado (enero o julio) hasta la fecha de despido.
        
        **Vacaciones no Gozadas:** Según antigüedad:
        - Menos de 5 años: 14 días corridos
        - De 5 a 10 años: 21 días corridos
        - De 10 a 20 años: 28 días corridos
        - Más de 20 años: 35 días corridos
        
        **SAC Vacaciones:** Doceava parte del valor de las vacaciones.
        
        ### 📊 Métodos de Actualización
        
        **RIPTE + 3%:** Remuneración Imponible Promedio de los Trabajadores Estables, más un 3% adicional.
        - **Fuente:** Secretaría de Seguridad Social - Ministerio de Trabajo
        
        **Tasa Activa:** Tasa activa promedio del Banco Nación
        - **Fuente:** Banco de la Nación Argentina
        
        **IPC (Referencia):** Índice de Precios al Consumidor
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
st.caption("**CALCULADORA DE DESPIDOS** | Sistema de Cálculo de Indemnizaciones Laborales")
st.caption("Los resultados son aproximados y no constituyen asesoramiento legal.")