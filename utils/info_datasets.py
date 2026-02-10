#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
INFO DATASETS - Sistema de Información de Datasets
Muestra información actualizada de los últimos datos disponibles
"""

import streamlit as st
import pandas as pd
from utils.data_loader import get_ultimo_dato


def mostrar_ultimos_datos():
    """
    Muestra los últimos datos disponibles de cada dataset.
    Versión simplificada para compatibilidad con apps antiguas.
    """
    mostrar_ultimos_datos_universal()


def mostrar_ultimos_datos_universal():
    """
    Muestra información consolidada de últimos datos de todos los datasets.
    """
    try:
        # Cargar datasets
        df_ripte = pd.read_csv("data/dataset_ripte.csv", encoding='utf-8')
        df_ipc = pd.read_csv("data/dataset_ipc.csv", encoding='utf-8')
        df_ipc['periodo'] = pd.to_datetime(df_ipc['periodo'])
        df_tasa = pd.read_csv("data/dataset_tasa.csv", encoding='utf-8')
        df_tasa['Desde'] = pd.to_datetime(df_tasa['Desde'], format='%d/%m/%Y', dayfirst=True)
        df_tasa['Hasta'] = pd.to_datetime(df_tasa['Hasta'], format='%d/%m/%Y', dayfirst=True)
        df_jus = pd.read_csv("data/Dataset_JUS.csv", encoding='utf-8')
        df_pisos = pd.read_csv("data/dataset_pisos.csv", encoding='utf-8')
        
        textos_datos = []
        
        # RIPTE
        if not df_ripte.empty:
            ultimo_ripte = get_ultimo_dato(df_ripte)
            año_ripte = ultimo_ripte['año']
            mes_texto = ultimo_ripte['mes']
            
            # Mapeo de meses
            meses_map = {
                'Enero': 1, 'Febrero': 2, 'Marzo': 3, 'Abril': 4,
                'Mayo': 5, 'Junio': 6, 'Julio': 7, 'Agosto': 8,
                'Septiembre': 9, 'Octubre': 10, 'Noviembre': 11, 'Diciembre': 12,
                'Ene': 1, 'Feb': 2, 'Mar': 3, 'Abr': 4,
                'May': 5, 'Jun': 6, 'Jul': 7, 'Ago': 8,
                'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dic': 12
            }
            
            mes_ripte = meses_map.get(mes_texto[:3], mes_texto) if isinstance(mes_texto, str) else mes_texto
            
            try:
                valor_ripte = ultimo_ripte['indice_ripte']
            except:
                valor_ripte = ultimo_ripte.iloc[2]
            
            textos_datos.append(f'**RIPTE** {mes_ripte}/{año_ripte}: {valor_ripte:,.0f}')
        
        # IPC
        if not df_ipc.empty:
            ultimo_ipc = get_ultimo_dato(df_ipc)
            fecha_ipc = ultimo_ipc['periodo']
            variacion_ipc = ultimo_ipc['variacion_mensual']
            mes_ipc = fecha_ipc.month
            año_ipc = fecha_ipc.year
            textos_datos.append(f'**IPC** {mes_ipc}/{año_ipc}: {variacion_ipc:.2f}%')
        
        # TASA ACT. BNA
        if not df_tasa.empty:
            ultima_tasa = get_ultimo_dato(df_tasa)
            valor_tasa = ultima_tasa['Valor']
            fecha_hasta = ultima_tasa['Hasta']
            fecha_txt = fecha_hasta.strftime("%d/%m/%Y")
            textos_datos.append(f'**TASA ACT. BNA** {fecha_txt}: {valor_tasa:.2f}%')
        
        # JUS ARANC.
        try:
            ultimo_jus = get_ultimo_dato(df_jus)
            fecha_jus = ultimo_jus['FECHA ENTRADA EN VIGENCIA '].strip() if isinstance(ultimo_jus['FECHA ENTRADA EN VIGENCIA '], str) else ultimo_jus['FECHA ENTRADA EN VIGENCIA ']
            valor_jus_str = ultimo_jus['VALOR IUS'].strip()
            acuerdo_jus = ultimo_jus['ACUERDO'].strip()
            
            valor_jus = float(valor_jus_str.replace('$', '').replace('.', '').replace(',', '.').strip())
            acuerdo_num = acuerdo_jus.replace('Acuerdo ', '').replace('acuerdo ', '')
            
            textos_datos.append(f'**JUS ARANC.** {fecha_jus} Ac.{acuerdo_num}: ${valor_jus:,.2f}')
        except:
            pass
        
        # PISOS LRT
        try:
            ultimo_piso = get_ultimo_dato(df_pisos)
            fecha_inicio = ultimo_piso['fecha_inicio']
            norma_piso = ultimo_piso['norma']
            monto_piso = float(ultimo_piso['monto_minimo'])
            
            textos_datos.append(f'**PISO LRT** {fecha_inicio} {norma_piso}: ${monto_piso:,.2f}')
        except:
            pass
        
        # Mostrar información
        if textos_datos:
            st.markdown("**📊 Últimos datos disponibles:**")
            datos_texto = ' <span style="color: #dc3545;">|</span> '.join(textos_datos)
            st.markdown(
                f"<div style='background-color: #e8f4f8; padding: 1rem; border-radius: 5px; "
                f"color: #0c5460; border-left: 4px solid #17a2b8;'>{datos_texto}</div>",
                unsafe_allow_html=True
            )
    
    except Exception as e:
        st.warning(f"⚠️ No se pudieron cargar los últimos datos: {str(e)}")