#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CALCULADORA DE INGRESO BASE MENSUAL (IBM)
Ley 24.557 - Art. 12 Inc. 1
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
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
from utils.funciones_comunes import numero_a_letras

# Sidebar de navegacion
mostrar_sidebar_navegacion('ibm')

# Titulo de la app
st.markdown("# 💰 CALCULADORA IBM - LEY 24.557")
st.markdown("### Ingreso Base Mensual - Art. 12 Inc. 1")

# Cargar dataset RIPTE
def cargar_ripte():
    """Carga el dataset RIPTE"""
    df = pd.read_csv("data/dataset_ripte.csv", encoding='utf-8')
    
    # Crear columna de fecha
    df['fecha'] = pd.to_datetime(
        df['año'].astype(str) + '-' + 
        df['mes'].str[:3].map({
            'Ene': '01', 'Feb': '02', 'Mar': '03', 'Abr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Ago': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dic': '12'
        }) + '-01'
    )
    return df

def obtener_ripte(df_ripte, año, mes):
    """Obtiene el índice RIPTE para un año y mes"""
    fila = df_ripte[
        (df_ripte['año'] == año) & 
        (df_ripte['mes'].str.lower().str[:3] == mes.lower()[:3])
    ]
    if not fila.empty:
        return float(get_ultimo_dato(fila)['indice_ripte'])
    return None

def calcular_variacion_ripte(df_ripte, año_desde, mes_desde, año_hasta, mes_hasta):
    """Calcula la variación RIPTE entre dos fechas"""
    indice_desde = obtener_ripte(df_ripte, año_desde, mes_desde)
    indice_hasta = obtener_ripte(df_ripte, año_hasta, mes_hasta)
    
    if indice_desde is None or indice_hasta is None or indice_desde == 0:
        return None
    
    return (indice_hasta - indice_desde) / indice_desde

def obtener_meses_anteriores(fecha_pmi, cantidad=12):
    """Obtiene lista de meses anteriores a la PMI"""
    meses = []
    fecha = fecha_pmi
    for i in range(cantidad):
        fecha = fecha - relativedelta(months=1)
        meses.append(fecha)
    meses.reverse()
    return meses

def obtener_nombre_mes(fecha):
    """Obtiene nombre del mes en formato mes-año"""
    meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 
             'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
    return f"{meses[fecha.month-1]}.-{str(fecha.year)[2:]}"

def obtener_dias_mes(año, mes):
    """Obtiene días de un mes"""
    if mes == 12:
        sig_mes = date(año + 1, 1, 1)
    else:
        sig_mes = date(año, mes + 1, 1)
    
    ultimo = sig_mes - relativedelta(days=1)
    return ultimo.day

def formatear_moneda(valor):
    """Formatea como moneda argentina"""
    if valor is None:
        return "$0,00"
    decimal_val = Decimal(str(valor))
    redondeado = decimal_val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    valor_str = f"{redondeado:,.2f}"
    valor_str = valor_str.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"${valor_str}"

def formatear_porcentaje(valor):
    """Formatea como porcentaje"""
    if valor is None:
        return "N/A"
    return f"{valor:.6f}".replace(".", ",")

def generar_texto_plano(datos, fecha_pmi, ibm):
    """Genera texto para copiar a Word usando tabulaciones"""
    
    texto = f"Fecha PMI: {fecha_pmi.strftime('%d/%m/%Y')}\n\n"
    
    total_orig = Decimal('0')
    total_act = Decimal('0')
    total_dias = 0
    meses_datos = 0
    
    # Contar meses con datos
    for d in datos:
        if d['incluir'] and d['salario'] > 0:
            total_orig += Decimal(str(d['salario']))
            total_act += Decimal(str(d['salario_act']))
            total_dias += d['dias']
            meses_datos += 1
    
    texto += f"Meses con datos: {meses_datos}\n\n"
    
    texto += "DETALLE DE SALARIOS ACTUALIZADOS:\n\n"
    
    # Encabezados con tabulaciones
    texto += "Período\tSalario\tRIPTE\tVariación\tActualizado\tDías\n"
    texto += "-" * 70 + "\n"
    
    for d in datos:
        if d['incluir'] and d['salario'] > 0:
            # Variación con 3 decimales
            var = f"{d['variacion']:.3f}".replace(".", ",") if d['variacion'] else "N/A"
            
            texto += f"{d['periodo']}\t"
            texto += f"{formatear_moneda(d['salario'])}\t"
            texto += f"{d['ripte']:.2f}\t"
            texto += f"{var}\t"
            texto += f"{formatear_moneda(d['salario_act'])}\t"
            texto += f"{d['dias']}\n"
    
    texto += "-" * 70 + "\n"
    texto += f"TOTALES\t{formatear_moneda(total_orig)}\t\t\t{formatear_moneda(total_act)}\t{total_dias}\n"
    texto += "=" * 70 + "\n\n"
    
    texto += f"IBM (Actualizado): {formatear_moneda(ibm)}\n"
    texto += f"(SON {numero_a_letras(ibm)})\n\n"
    texto += f"Fórmula: {formatear_moneda(total_act)} / {meses_datos} = {formatear_moneda(ibm)}\n"
    texto += "=" * 70 + "\n"
    
    return texto

def generar_pdf_ibm(datos, fecha_pmi, ibm):
    """Genera PDF con el cálculo del IBM"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)
    
    elementos = []
    styles = getSampleStyleSheet()
    
    # Título
    titulo_style = ParagraphStyle(
        'TituloCustom',
        parent=styles['Title'],
        fontSize=16,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=10,
        alignment=TA_CENTER
    )
    
    subtitulo_style = ParagraphStyle(
        'SubtituloCustom',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.grey,
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    elementos.append(Paragraph("CÁLCULO DEL INGRESO BASE MENSUAL (IBM)", titulo_style))
    elementos.append(Paragraph("Ley 24.557 - Art. 12 Inc. 1", subtitulo_style))
    elementos.append(Spacer(1, 0.5*cm))
    
    # Fecha PMI
    elementos.append(Paragraph(f"<b>Fecha PMI:</b> {fecha_pmi.strftime('%d/%m/%Y')}", styles['Normal']))
    elementos.append(Spacer(1, 0.5*cm))
    
    # Tabla de datos
    data_tabla = [
        ['Período', 'Salario', 'RIPTE', 'Variación', 'Actualizado', 'Días']
    ]
    
    total_orig = Decimal('0')
    total_act = Decimal('0')
    total_dias = 0
    meses_datos = 0
    
    for d in datos:
        if d['incluir'] and d['salario'] > 0:
            total_orig += Decimal(str(d['salario']))
            total_act += Decimal(str(d['salario_act']))
            total_dias += d['dias']
            meses_datos += 1
            
            var_texto = formatear_porcentaje(d['variacion']) if d['variacion'] else "N/A"
            
            data_tabla.append([
                d['periodo'],
                formatear_moneda(d['salario']),
                f"{d['ripte']:.2f}" if d['ripte'] else "N/A",
                var_texto,
                formatear_moneda(d['salario_act']),
                str(d['dias'])
            ])
    
    # Fila de totales
    data_tabla.append([
        'TOTALES',
        formatear_moneda(total_orig),
        '',
        '',
        formatear_moneda(total_act),
        str(total_dias)
    ])
    
    tabla = Table(data_tabla, colWidths=[3*cm, 3*cm, 2*cm, 2.5*cm, 3*cm, 1.5*cm])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f0f0f0')]),
    ]))
    
    elementos.append(tabla)
    elementos.append(Spacer(1, 0.5*cm))
    
    # Resultado IBM
    resultado_style = ParagraphStyle(
        'ResultadoCustom',
        parent=styles['Normal'],
        fontSize=14,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    elementos.append(Paragraph(f"<b>Meses con datos:</b> {meses_datos}", styles['Normal']))
    elementos.append(Spacer(1, 0.3*cm))
    elementos.append(Paragraph(f"INGRESO BASE MENSUAL (IBM): {formatear_moneda(ibm)}", resultado_style))
    elementos.append(Paragraph(
        f"Fórmula: {formatear_moneda(total_act)} / {meses_datos} = {formatear_moneda(ibm)}",
        styles['Normal']
    ))
    
    doc.build(elementos)
    buffer.seek(0)
    return buffer

# Cargar datos
try:
    df_ripte = cargar_ripte()
except Exception as e:
    st.error(f"Error al cargar RIPTE: {str(e)}")
    st.stop()

# Fecha PMI
col_fecha1, col_fecha2, col_fecha3 = st.columns([1, 2, 1])
with col_fecha2:
    fecha_pmi = st.date_input(
        "📅 Fecha PMI (Primera Manifestación Invalidante)",
        value=date(2021, 12, 1),
        format="DD/MM/YYYY"
    )

# Obtener 12 meses anteriores
meses = obtener_meses_anteriores(fecha_pmi, 12)
# Invertir orden para mostrar primero el más reciente
meses.reverse()

# Inicializar session_state
if 'salarios' not in st.session_state:
    st.session_state.salarios = {}

# TABLA DE CÁLCULO
st.subheader("🔢 Tabla de Cálculo de Salarios")

# Encabezados de la tabla
col_headers = st.columns([1.2, 1.5, 1, 1.2, 1.5, 0.8])
with col_headers[0]:
    st.markdown("**Período**")
with col_headers[1]:
    st.markdown("**Salario**")
with col_headers[2]:
    st.markdown("**RIPTE**")
with col_headers[3]:
    st.markdown("**Variación**")
with col_headers[4]:
    st.markdown("**Actualizado**")
with col_headers[5]:
    st.markdown("**Días**")

datos_calc = []

# Filas de la tabla
for mes in meses:
    nombre = obtener_nombre_mes(mes)
    key = f"{mes.year}_{mes.month}"
    
    cols = st.columns([1.2, 1.5, 1, 1.2, 1.5, 0.8])
    
    # Período
    with cols[0]:
        st.text(nombre)
    
    # Input Salario
    with cols[1]:
        salario = st.number_input(
            f"Salario {nombre}",
            min_value=0.0,
            value=0.0,
            step=1000.0,
            format="%.2f",
            key=f"s_{key}",
            label_visibility="collapsed"
        )
    
    # Calcular variación RIPTE
    mes_nombre = nombre.split('.-')[0]
    año_mes = mes.year
    año_pmi = fecha_pmi.year
    mes_pmi = obtener_nombre_mes(fecha_pmi).split('.-')[0]
    
    variacion = calcular_variacion_ripte(df_ripte, año_mes, mes_nombre, año_pmi, mes_pmi)
    
    # Calcular salario actualizado
    if variacion is not None and salario > 0:
        salario_act = salario * (1 + variacion)
    else:
        salario_act = salario
    
    # Obtener RIPTE
    ripte = obtener_ripte(df_ripte, año_mes, mes_nombre)
    dias = obtener_dias_mes(mes.year, mes.month)
    
    # Mostrar RIPTE
    with cols[2]:
        if ripte:
            st.text(f"{ripte:.2f}")
        else:
            st.text("N/A")
    
    # Mostrar Variación
    with cols[3]:
        if variacion is not None:
            st.text(formatear_porcentaje(variacion))
        else:
            st.text("N/A")
    
    # Mostrar Actualizado
    with cols[4]:
        if salario > 0:
            st.text(formatear_moneda(salario_act))
        else:
            st.text("-")
    
    # Mostrar Días
    with cols[5]:
        st.text(str(dias))
    
    datos_calc.append({
        'periodo': nombre,
        'salario': salario,
        'ripte': ripte if ripte else 0,
        'variacion': variacion,
        'salario_act': salario_act,
        'dias': dias,
        'incluir': salario > 0  # Automático: incluir si tiene salario
    })

# Línea separadora
st.markdown("---")

# TOTALES Y IBM
total_orig = sum(Decimal(str(d['salario'])) for d in datos_calc if d['incluir'] and d['salario'] > 0)
total_act = sum(Decimal(str(d['salario_act'])) for d in datos_calc if d['incluir'] and d['salario'] > 0)
total_dias = sum(d['dias'] for d in datos_calc if d['incluir'] and d['salario'] > 0)
meses_datos = sum(1 for d in datos_calc if d['incluir'] and d['salario'] > 0)

# Calcular IBM
if meses_datos > 0:
    ibm = total_act / Decimal(str(meses_datos))
    ibm = ibm.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
else:
    ibm = Decimal('0')

# Mostrar totales en la tabla
col_tot = st.columns([1.2, 1.5, 1, 1.2, 1.5, 0.8])
with col_tot[0]:
    st.markdown("**TOTALES**")
with col_tot[1]:
    st.markdown(f"**{formatear_moneda(total_orig)}**")
with col_tot[2]:
    st.markdown("")
with col_tot[3]:
    st.markdown("")
with col_tot[4]:
    st.markdown(f"**{formatear_moneda(total_act)}**")
with col_tot[5]:
    st.markdown(f"**{total_dias}**")

# Resultado IBM
col_ibm1, col_ibm2, col_ibm3 = st.columns([1, 2, 1])
with col_ibm2:
    st.success("**INGRESO BASE MENSUAL (IBM) (Actualizado)**")
    st.markdown(f"# {formatear_moneda(ibm)}")
    st.caption(f"Promedio de {meses_datos} meses con datos")
    st.caption(f"Fórmula: {formatear_moneda(total_act)} / {meses_datos} = {formatear_moneda(ibm)}")

# Tabs para salidas
tab1, tab2, tab3 = st.tabs(["📋 Texto Plano", "📄 PDF", "ℹ️ Información"])

# TAB 1: TEXTO PLANO
with tab1:
    st.markdown("### 📋 Texto para copiar a Augusta")
    texto = generar_texto_plano(datos_calc, fecha_pmi, ibm)
    
    # st.code tiene botón de copiar incorporado en la esquina
    st.code(texto, language=None)

# TAB 2: PDF
with tab2:
    st.markdown("### 📄 Descargar PDF")
    
    # Generar PDF automáticamente
    pdf_buffer = generar_pdf_ibm(datos_calc, fecha_pmi, ibm)
    
    st.download_button(
        label="📥 DESCARGAR PDF",
        data=pdf_buffer,
        file_name=f"IBM_{fecha_pmi.strftime('%Y%m%d')}.pdf",
        mime="application/pdf",
        use_container_width=True,
        type="primary"
    )

# TAB 3: INFORMACIÓN
with tab3:
    st.markdown("### ℹ️ BASE LEGAL - LEY 24.557 ART. 12 INC. 1")
    
    st.markdown("""
    #### Artículo 12 inciso 1 - Ley 24.557
    
    *"A los fines del cálculo del valor del ingreso base se considerará el promedio mensual 
    de todos los salarios devengados -de conformidad con lo establecido por el artículo 1° 
    del Convenio N° 95 de la OIT- por el trabajador durante el año anterior a la primera 
    manifestación invalidante, o en el tiempo de prestación de servicio si fuera menor. 
    Los salarios mensuales tomados a fin de establecer el promedio se actualizarán mes a mes 
    aplicándose la variación del índice Remuneraciones Imponibles Promedio de los Trabajadores 
    Estables (RIPTE), elaborado y difundido por el MINISTERIO DE SALUD Y DESARROLLO SOCIAL."*
    
    #### Metodología de Cálculo
    
    1. **Período**: 12 meses anteriores a la PMI (o menor si trabajó menos tiempo)
    2. **Actualización**: Cada salario se actualiza por variación RIPTE desde su mes hasta el mes de la PMI
    3. **Promedio**: El IBM es el promedio de los salarios actualizados
    
    **Fórmula:**
    - Variación RIPTE = (RIPTE PMI - RIPTE Mes) / RIPTE Mes
    - Salario Actualizado = Salario × (1 + Variación RIPTE)
    - IBM = Suma Salarios Actualizados / Cantidad de Meses con Datos
    """)

# Mostrar últimos datos disponibles
mostrar_ultimos_datos_universal()

st.markdown("---")
st.caption("**CALCULADORA IBM** | Ley 24.557 Art. 12 Inc. 1 | Actualización RIPTE")