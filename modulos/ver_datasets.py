#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VISUALIZADOR DE DATASETS
Solo lectura - Para copiar datos
"""

import streamlit as st
import pandas as pd

def main():
    st.title("📋 Visualizador de Datasets")
    st.markdown("Datasets actuales del sistema (solo lectura)")
    st.markdown("---")
    
    # Selector de dataset
    dataset_seleccionado = st.selectbox(
        "Seleccionar dataset:",
        ["RIPTE", "IPC", "Tasas", "JUS", "Pisos"]
    )
    
    st.markdown("---")
    
    try:
        if dataset_seleccionado == "RIPTE":
            df = pd.read_csv("data/dataset_ripte.csv", encoding='utf-8')
            st.subheader("📊 Dataset RIPTE")
            st.dataframe(df, use_container_width=True, hide_index=False)
            
        elif dataset_seleccionado == "IPC":
            df = pd.read_csv("data/dataset_ipc.csv", encoding='utf-8')
            st.subheader("📊 Dataset IPC")
            st.dataframe(df, use_container_width=True, hide_index=False)
            
        elif dataset_seleccionado == "Tasas":
            df = pd.read_csv("data/dataset_tasa.csv", encoding='utf-8')
            st.subheader("📊 Dataset Tasas de Interés")
            st.dataframe(df, use_container_width=True, hide_index=False)
            
        elif dataset_seleccionado == "JUS":
            df = pd.read_csv("data/Dataset_JUS.csv", encoding='utf-8')
            st.subheader("📊 Dataset JUS")
            st.dataframe(df, use_container_width=True, hide_index=False)
            
        elif dataset_seleccionado == "Pisos":
            df = pd.read_csv("data/dataset_pisos.csv", encoding='utf-8')
            st.subheader("📊 Dataset Pisos Salariales")
            st.dataframe(df, use_container_width=True, hide_index=False)
        
        # Información adicional
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de registros", len(df))
        with col2:
            st.metric("Columnas", len(df.columns))
        with col3:
            st.metric("Último registro", len(df))
        
        # Botón para copiar
        st.markdown("---")
        st.info("💡 Selecciona las celdas que necesites y copia con Ctrl+C")
        
    except Exception as e:
        st.error(f"Error al cargar el dataset: {str(e)}")

if __name__ == "__main__":
    main()
