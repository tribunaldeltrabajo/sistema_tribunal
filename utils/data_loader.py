#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DATA LOADER - Sistema de Carga de Datos
Funciones para cargar y obtener último dato de datasets
"""

import pandas as pd


def get_ultimo_dato(df):
    """
    Obtiene el último registro de un DataFrame.
    
    IMPORTANTE: Los datasets del sistema están ordenados descendente 
    (más reciente primero), por lo tanto retorna iloc[0].
    
    Args:
        df: DataFrame de pandas ordenado cronológicamente (descendente)
        
    Returns:
        Series: Primera fila del DataFrame (dato más reciente)
        
    Ejemplos:
        >>> df_ripte = pd.read_csv('dataset_ripte.csv')
        >>> ultimo = get_ultimo_dato(df_ripte)  # Retorna fila 0 (Sep 2025)
        >>> print(ultimo['indice_ripte'])
    """
    if df is None or df.empty:
        return None
    
    return df.iloc[0]


def cargar_dataset_csv(ruta, encoding='utf-8'):
    """
    Carga un dataset CSV con manejo robusto de errores.
    
    Args:
        ruta: Path al archivo CSV
        encoding: Codificación del archivo (default: utf-8)
        
    Returns:
        DataFrame: Dataset cargado o DataFrame vacío si hay error
    """
    try:
        return pd.read_csv(ruta, encoding=encoding)
    except FileNotFoundError:
        print(f"⚠️ Archivo no encontrado: {ruta}")
        return pd.DataFrame()
    except Exception as e:
        print(f"⚠️ Error al cargar {ruta}: {str(e)}")
        return pd.DataFrame()