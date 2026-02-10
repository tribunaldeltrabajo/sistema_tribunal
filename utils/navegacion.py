#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NAVEGACIÓN - Sistema de Sidebar
Barra lateral de navegación entre aplicaciones
"""

import streamlit as st


def mostrar_sidebar_navegacion(app_actual=None):
    """
    Muestra la barra lateral de navegación.
    
    Args:
        app_actual: Identificador de la app actual (para destacarla)
    """
    with st.sidebar:
        st.markdown("## 🧭 Navegación")
        st.markdown("---")
        
        # Botón para volver al menú principal
        if st.button("🏠 Menú Principal", use_container_width=True, type="primary"):
            st.session_state.app_actual = None
            st.rerun()
        
        st.markdown("---")
        st.markdown("### 📋 Aplicaciones")
        
        apps = {
            'ibm': '💰 IBM',
            'actualizacion': '📈 Actualización',
            'lrt': '🧮 LRT',
            'despidos': '📊 Despidos',
            'honorarios': '💵 Honorarios',
            'datasets': '📋 Datasets'
        }
        
        for key, nombre in apps.items():
            tipo = "primary" if key == app_actual else "secondary"
            if st.button(nombre, key=f"nav_{key}", use_container_width=True, type=tipo):
                st.session_state.app_actual = key
                st.rerun()
        
        st.markdown("---")
        st.caption("**Tribunal de Trabajo N° 2**")
        st.caption("Quilmes, Buenos Aires")
