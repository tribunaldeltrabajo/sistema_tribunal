#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SISTEMA DE CÁLCULOS Y HERRAMIENTAS
Tribunal de Trabajo
"""

import streamlit as st
import sys
import os
from pathlib import Path

# Configurar path absoluto
BASE_DIR = Path(__file__).parent.absolute()
sys.path.insert(0, str(BASE_DIR))

# Cambiar al directorio base para que las rutas relativas funcionen
os.chdir(BASE_DIR)

# Configuración
st.set_page_config(
    page_title="Sistema Tribunal de Trabajo",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Ocultar sidebar y personalizar colores
st.markdown("""
<style>
    [data-testid="stSidebar"] {display: none;}
    
    /* Botones azul Streamlit */
    .stButton > button {
        background-color: #0068c9;
        color: white;
    }
    .stButton > button:hover {
        background-color: #0054a3;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# SISTEMA DE AUTENTICACIÓN
# ============================================

# Configuración de contraseña desde Streamlit Secrets
# Para desarrollo local: crear archivo .streamlit/secrets.toml
# Para Streamlit Cloud: configurar en Settings → Secrets
try:
    CLAVE_ACCESO = st.secrets["TRIBUNAL_PASSWORD"]
except (KeyError, FileNotFoundError):
    # Fallback: si no existe el secret, usa contraseña por defecto
    CLAVE_ACCESO = "tribunal2025"
    st.warning("⚠️ Usando contraseña por defecto. Configure TRIBUNAL_PASSWORD en Streamlit Secrets.")

def verificar_acceso():
    """Verifica si el usuario tiene acceso"""
    
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False
    
    if not st.session_state.autenticado:
        st.markdown("""
            <div style='text-align: center; margin-top: 100px;'>
                <h1 style='font-size: 4rem; margin: 0;'>⚖️</h1>
                <h1>Sistema de Cálculos y Herramientas</h1>
                <h3 style='color: #666;'>Tribunal de Trabajo</h3>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.markdown("### 🔐 Acceso al Sistema")
            
            with st.form(key="form_login"):
                clave_ingresada = st.text_input("Ingrese la clave de acceso:", type="password", key="input_clave")
                submit_button = st.form_submit_button("Ingresar", use_container_width=True)
                
                if submit_button:
                    if clave_ingresada == CLAVE_ACCESO:
                        st.session_state.autenticado = True
                        st.rerun()
                    else:
                        st.error("❌ Clave incorrecta")
        
        st.stop()

# ============================================
# APLICACIONES
# ============================================

APLICACIONES = {
    "audiencias": {
        "nombre": "⚖️ Calculadora de Audiencias",
        "modulo": "modulos.calculadora_audiencias"
    },
    "relatoria": {
        "nombre": "📄 Calculadora Relatoría",
        "modulo": "modulos.calculadora_relatoria"
    },
    "ibm": {
        "nombre": "💰 Actualización IBM por RIPTE (Art. 12 inc. a LRT)",
        "modulo": "modulos.ibm"
    },
    "actualizacion": {
        "nombre": "📈 Actualización e Intereses",
        "modulo": "modulos.actualizacion"
    },

}

def ejecutar_aplicacion(nombre_app):
    """Ejecuta una aplicación"""
    if nombre_app not in APLICACIONES:
        st.error(f"❌ Aplicación '{nombre_app}' no encontrada")
        return
    
    app_info = APLICACIONES[nombre_app]
    
    try:
        import importlib
        
        # Limpiar caché del módulo
        modulo_name = app_info["modulo"]
        if modulo_name in sys.modules:
            del sys.modules[modulo_name]
        
        # Importar módulo
        modulo = importlib.import_module(modulo_name)
        
        # Si el módulo tiene una función main(), ejecutarla
        if hasattr(modulo, 'main'):
            modulo.main()
        
    except Exception as e:
        st.error(f"❌ Error al cargar la aplicación")
        st.error(f"Detalles: {str(e)}")
        with st.expander("🔍 Ver error completo"):
            st.exception(e)

def mostrar_menu_principal():
    """Muestra el menú principal"""
    
    st.markdown("""
        <div style='text-align: center;'>
            <h1 style='font-size: 4rem; margin: 0;'>⚖️</h1>
            <h1 style='margin: 0.5rem 0;'>Sistema de Cálculos y Herramientas</h1>
            <h3 style='color: #666; margin: 0;'>Tribunal de Trabajo</h3>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Grid de aplicaciones
    col1, col2 = st.columns(2)
    
    apps_lista = list(APLICACIONES.items())
    
    for idx, (key, app) in enumerate(apps_lista):
        col = col1 if idx % 2 == 0 else col2
        
        with col:
            if st.button(app['nombre'], key=f"btn_{key}", use_container_width=True):
                st.session_state.app_actual = key
                st.rerun()
                # Mostrar últimos datos disponibles
    st.markdown("---")
    from utils.info_datasets import mostrar_ultimos_datos_universal
    mostrar_ultimos_datos_universal()
    
    st.markdown("---")
    st.caption("**v1.0.0** | Sistema desarrollado para Tribunal de Trabajo")
    

def main():
    """Función principal"""
    
    # Verificar acceso
    verificar_acceso()
    
    # Inicializar session_state
    if 'app_actual' not in st.session_state:
        st.session_state.app_actual = None
    
    # Ejecutar app o mostrar menú
    if st.session_state.app_actual:
        # Botón volver
        if st.button("← Volver al Menú Principal"):
            st.session_state.app_actual = None
            st.rerun()
        
        ejecutar_aplicacion(st.session_state.app_actual)
    else:
        mostrar_menu_principal()

if __name__ == "__main__":
    main()