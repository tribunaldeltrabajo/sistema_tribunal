#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CALCULADORA INDEMNIZACIONES LEY 24.557
Sistema de cálculo de indemnizaciones laborales
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import os
from dataclasses import dataclass
from typing import Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from utils.navegacion import mostrar_sidebar_navegacion
from utils.info_datasets import mostrar_ultimos_datos_universal
from utils.funciones_comunes import (
    safe_parse_date, 
    days_in_month, 
    redondear, 
    numero_a_letras, 
    get_mes_nombre
)

# Sidebar de navegación
mostrar_sidebar_navegacion('lrt')

# Paths de datasets
DATASET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PATH_RIPTE = os.path.join(DATASET_DIR, "dataset_ripte.csv")
PATH_TASA = os.path.join(DATASET_DIR, "dataset_tasa.csv")
PATH_IPC = os.path.join(DATASET_DIR, "dataset_ipc.csv")
PATH_PISOS = os.path.join(DATASET_DIR, "dataset_pisos.csv")

@dataclass
class InputData:
    """Estructura para los datos de entrada"""
    pmi_date: date
    final_date: date
    ibm: float
    edad: int
    incapacidad_pct: float
    incluir_20_pct: bool

@dataclass
class Results:
    """Estructura para los resultados de cálculo"""
    capital_formula: float
    capital_base: float
    piso_aplicado: bool
    piso_info: str
    piso_monto: float
    piso_proporcional: float
    piso_norma: str
    adicional_20_pct: float
    
    ripte_coef: float
    ripte_pmi: float
    ripte_final: float
    ripte_actualizado: float
    interes_puro_3_pct: float
    total_ripte_3: float
    
    tasa_activa_pct: float
    total_tasa_activa: float
    
    inflacion_acum_pct: float

class DataManager:
    """Gestor de datasets CSV"""
    
    def __init__(self):
        self.ipc_data = None
        self.pisos_data = None
        self.ripte_data = None
        self.tasa_data = None
        self.load_all_datasets()
    
    def _load_csv(self, path):
        """Carga CSV con múltiples separadores"""
        if not os.path.exists(path):
            st.error(f"No se encontró el dataset: {path}")
            return pd.DataFrame()
        
        for sep in [",", ";", "\t"]:
            try:
                df = pd.read_csv(path, sep=sep)
                if df.shape[1] >= 1:
                    return df
            except Exception:
                continue
        
        try:
            return pd.read_csv(path, sep=",", encoding="utf-8")
        except Exception as e:
            st.error(f"No se pudo leer el dataset {path}.\n{e}")
            return pd.DataFrame()
    
    def load_all_datasets(self):
        """Carga todos los datasets"""
        try:
            self.ripte_data = self._load_csv(PATH_RIPTE)
            self.tasa_data = self._load_csv(PATH_TASA)  
            self.ipc_data = self._load_csv(PATH_IPC)
            self.pisos_data = self._load_csv(PATH_PISOS)
            
            self._norm_ripte()
            self._norm_tasa()
            self._norm_ipc()
            self._norm_pisos()
                
        except Exception as e:
            st.error(f"Error cargando datasets: {str(e)}")
    
    def _norm_ripte(self):
        """Normalización RIPTE"""
        if self.ripte_data.empty: 
            return
        cols = [c.lower() for c in self.ripte_data.columns]
        self.ripte_data.columns = cols
        
        if 'año' in cols and 'mes' in cols:
            meses_dict = {
                'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
                'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
                'ene': 1, 'abr': 4, 'ago': 8, 'set': 9, 'dic': 12
            }
            
            def convertir_mes(valor):
                if pd.isna(valor):
                    return None
                valor_str = str(valor).strip().lower()
                
                try:
                    return int(float(valor_str))
                except ValueError:
                    pass
                
                if valor_str in meses_dict:
                    return meses_dict[valor_str]
                
                for mes_nombre, mes_num in meses_dict.items():
                    if mes_nombre.startswith(valor_str[:3]) or valor_str.startswith(mes_nombre[:3]):
                        return mes_num
                
                return None
            
            def crear_fecha_combined(row):
                try:
                    año = int(row['año'])
                    mes_num = convertir_mes(row['mes'])
                    if mes_num is None:
                        return None
                    return f"{año}-{mes_num:02d}-01"
                except (ValueError, TypeError):
                    return None
            
            self.ripte_data['fecha_combined'] = self.ripte_data.apply(crear_fecha_combined, axis=1)
            fecha_col = 'fecha_combined'
        else:
            fecha_col = None
            for c in cols:
                if ("fecha" in c) or ("periodo" in c) or ("mes" in c):
                    fecha_col = c
                    break
            if fecha_col is None:
                fecha_col = cols[0]
        
        val_col = None
        if 'indice_ripte' in cols:
            val_col = 'indice_ripte'
        else:
            for c in cols:
                if ("ripte" in c) or ("valor" in c) or ("indice" in c):
                    val_col = c
                    break
            if val_col is None:
                num_cols = self.ripte_data.select_dtypes(include="number").columns.tolist()
                val_col = num_cols[0] if num_cols else cols[1] if len(cols)>1 else cols[0]
        
        self.ripte_data["fecha"] = self.ripte_data[fecha_col].apply(safe_parse_date)
        self.ripte_data["ripte"] = pd.to_numeric(self.ripte_data[val_col], errors="coerce")
        # SIN ORDENAR - respetar orden del CSV
        self.ripte_data = self.ripte_data.dropna(subset=["fecha", "ripte"]).reset_index(drop=True)

    def _norm_tasa(self):
        """Normalización TASA"""
        if self.tasa_data.empty:
            return

        # normaliza nombres de columnas (y limpia BOM si existiera)
        cols = [str(c).strip().lower().replace("\ufeff", "") for c in self.tasa_data.columns]
        self.tasa_data.columns = cols

        # parseo de fechas
        if "desde" in self.tasa_data.columns:
            self.tasa_data["desde"] = self.tasa_data["desde"].apply(safe_parse_date)
        if "hasta" in self.tasa_data.columns:
            self.tasa_data["hasta"] = self.tasa_data["hasta"].apply(safe_parse_date)
        else:
            if "desde" in self.tasa_data.columns:
                self.tasa_data["hasta"] = self.tasa_data["desde"]

        if "desde" in self.tasa_data.columns:
            self.tasa_data["fecha"] = self.tasa_data["desde"]

        # columna base para la tasa
        base_col = None
        for cand in ("valor", "porcentaje", "tasa"):
            if cand in self.tasa_data.columns:
                base_col = cand
                break

        if base_col is not None:
            # convierte "3,982" o "3.982" → 3.982 (sin eliminar punto decimal)
            self.tasa_data["tasa"] = (
                self.tasa_data[base_col]
                .astype(str)
                .str.replace(",", ".", regex=False)             
            )
            self.tasa_data["tasa"] = pd.to_numeric(self.tasa_data["tasa"], errors="coerce")

        # columnas útiles pero SIN ORDENAR - respetar orden del CSV
        keep_cols = [c for c in ("fecha", "tasa", "desde", "hasta") if c in self.tasa_data.columns]
        if "fecha" in self.tasa_data.columns and "tasa" in self.tasa_data.columns:
            self.tasa_data = (
                self.tasa_data.dropna(subset=["fecha", "tasa"])
                .reset_index(drop=True)
            )[keep_cols]

    def _norm_ipc(self):
        """Normalización IPC"""
        if self.ipc_data.empty: 
            return
        cols = [c.lower() for c in self.ipc_data.columns]
        self.ipc_data.columns = cols
        
        fecha_col = None
        if 'periodo' in cols:
            fecha_col = 'periodo'
        else:
            for c in cols:
                if ("fecha" in c) or ("periodo" in c) or ("mes" in c):
                    fecha_col = c
                    break
            if fecha_col is None:
                fecha_col = cols[0]
        
        val_col = None
        if 'variacion_mensual' in cols:
            val_col = 'variacion_mensual'
        else:
            for c in cols:
                if ("variacion" in c) or ("inflacion" in c) or ("ipc" in c) or ("porcentaje" in c) or ("mensual" in c) or ("indice" in c):
                    val_col = c
                    break
            if val_col is None:
                num_cols = self.ipc_data.select_dtypes(include="number").columns.tolist()
                val_col = num_cols[0] if num_cols else cols[1] if len(cols)>1 else cols[0]
        
        self.ipc_data["fecha"] = self.ipc_data[fecha_col].apply(safe_parse_date)
        self.ipc_data["ipc"] = pd.to_numeric(self.ipc_data[val_col], errors="coerce")
        # SIN ORDENAR - respetar orden del CSV
        self.ipc_data = self.ipc_data.dropna(subset=["fecha", "ipc"]).reset_index(drop=True)

    def _norm_pisos(self):
        """Normalización PISOS"""
        if self.pisos_data.empty: 
            return
        cols = [c.lower() for c in self.pisos_data.columns]
        self.pisos_data.columns = cols
        
        # El dataset tiene: fecha_inicio, fecha_fin, norma, monto_minimo, enlace
        self.pisos_data["desde"] = self.pisos_data["fecha_inicio"].apply(safe_parse_date)
        self.pisos_data["hasta"] = self.pisos_data["fecha_fin"].apply(safe_parse_date)
        self.pisos_data["piso"] = pd.to_numeric(self.pisos_data["monto_minimo"], errors="coerce")
        self.pisos_data["resol"] = self.pisos_data["norma"].astype(str)
        self.pisos_data["enlace"] = self.pisos_data["enlace"].astype(str).replace('nan', '')
        
        self.pisos_data = self.pisos_data.dropna(subset=["desde", "piso"]).sort_values("desde").reset_index(drop=True)
    
    def get_piso_minimo(self, fecha_pmi: date) -> Tuple[Optional[float], str]:
        """Obtiene piso mínimo"""
        if self.pisos_data.empty:
            return (None, "")
            
        candidate = None
        for _, r in self.pisos_data.iterrows():
            d0 = r["desde"]
            d1 = r["hasta"] if not pd.isna(r["hasta"]) else None
            if d1 is None:
                if fecha_pmi >= d0:
                    candidate = (float(r["piso"]), r.get("resol", ""))
            else:
                if d0 <= fecha_pmi <= d1:
                    return (float(r["piso"]), r.get("resol", ""))
        return candidate if candidate else (None, "")
    
    def get_ripte_coeficiente(self, fecha_pmi: date, fecha_final: date) -> Tuple[float, float, float]:
        """Cálculo RIPTE - ahora CSV está ordenado de más reciente a más antiguo"""
        if self.ripte_data.empty:
            return 1.0, 0.0, 0.0
        
        # Buscar RIPTE en fecha PMI (tomar el más reciente <= fecha_pmi)
        ripte_pmi_data = self.ripte_data[self.ripte_data['fecha'] <= fecha_pmi]
        if ripte_pmi_data.empty:
            # Si no hay datos antes de PMI, usar el más antiguo disponible
            ripte_pmi = float(self.ripte_data.iloc[-1]['ripte'])
        else:
            # Tomar el primero (más reciente) de los que cumplen <= fecha_pmi
            ripte_pmi = float(ripte_pmi_data.iloc[0]['ripte'])
        
        # Buscar RIPTE en fecha final (tomar el más reciente <= fecha_final)
        ripte_final_data = self.ripte_data[self.ripte_data['fecha'] <= fecha_final]
        if ripte_final_data.empty:
            ripte_final = float(self.ripte_data.iloc[-1]['ripte'])
        else:
            ripte_final = float(ripte_final_data.iloc[0]['ripte'])
        
        coeficiente = ripte_final / ripte_pmi if ripte_pmi > 0 else 1.0
        
        return coeficiente, ripte_pmi, ripte_final
    
    def calcular_tasa_activa(self, fecha_pmi: date, fecha_final: date, capital_base: float) -> Tuple[float, float]:
        """Cálculo de tasa activa"""
        if self.tasa_data.empty:
            return 0.0, capital_base
            
        total_aporte_pct = 0.0
        
        for _, row in self.tasa_data.iterrows():
            if "desde" in self.tasa_data.columns and not pd.isna(row.get("desde")):
                fecha_desde = row["desde"]
            else:
                fecha_desde = row["fecha"]
                
            if "hasta" in self.tasa_data.columns and not pd.isna(row.get("hasta")):
                fecha_hasta = row["hasta"]
            else:
                fecha_hasta = date(fecha_desde.year, fecha_desde.month, days_in_month(fecha_desde))
            
            if isinstance(fecha_desde, pd.Timestamp):
                fecha_desde = fecha_desde.date()
            if isinstance(fecha_hasta, pd.Timestamp):
                fecha_hasta = fecha_hasta.date()
            
            inicio_interseccion = max(fecha_pmi, fecha_desde)
            fin_interseccion = min(fecha_final, fecha_hasta)
            
            if inicio_interseccion <= fin_interseccion:
                dias_interseccion = (fin_interseccion - inicio_interseccion).days + 1
                
                if "tasa" in self.tasa_data.columns and not pd.isna(row.get("tasa")):
                    valor_mensual_pct = float(row["tasa"])
                elif "valor" in self.tasa_data.columns and not pd.isna(row.get("valor")):
                    valor_mensual_pct = float(row["valor"])
                else:
                    continue
                
                aporte_pct = valor_mensual_pct * (dias_interseccion / 30.0)
                total_aporte_pct += aporte_pct
        
        total_actualizado = capital_base * (1.0 + total_aporte_pct / 100.0)
        
        return total_aporte_pct, total_actualizado
    
    def calcular_inflacion(self, fecha_pmi: date, fecha_final: date) -> float:
        """Cálculo de inflación"""
        if self.ipc_data.empty:
            return 0.0
            
        fecha_inicio_mes = pd.Timestamp(fecha_pmi.replace(day=1))
        fecha_final_mes = pd.Timestamp(fecha_final.replace(day=1))
        
        ipc_periodo = self.ipc_data[
            (pd.to_datetime(self.ipc_data['fecha']) >= fecha_inicio_mes) &
            (pd.to_datetime(self.ipc_data['fecha']) <= fecha_final_mes)
        ]
        
        if ipc_periodo.empty:
            return 0.0
        
        factor_acumulado = 1.0
        for _, row in ipc_periodo.iterrows():
            variacion = row['ipc']
            if not pd.isna(variacion):
                factor_acumulado *= (1 + variacion / 100)
        
        inflacion_acumulada = (factor_acumulado - 1) * 100
        return inflacion_acumulada

class Calculator:
    """Motor de cálculos"""
    
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager
    
    def calcular_indemnizacion(self, input_data: InputData) -> Results:
        """Realiza todos los cálculos"""
        
        capital_formula = self._calcular_capital_formula(input_data)
        
        piso_minimo, piso_norma = self.data_manager.get_piso_minimo(input_data.pmi_date)
        capital_aplicado, piso_aplicado, piso_info, piso_proporcional = self._aplicar_piso_minimo(
            capital_formula, piso_minimo, piso_norma, input_data.incapacidad_pct
        )
        
        adicional_20_pct = float(redondear(Decimal(str(capital_aplicado)) * Decimal('0.20'))) if input_data.incluir_20_pct else 0.0
        capital_base = float(redondear(Decimal(str(capital_aplicado)) + Decimal(str(adicional_20_pct))))
        
        ripte_coef, ripte_pmi, ripte_final = self.data_manager.get_ripte_coeficiente(
            input_data.pmi_date, input_data.final_date
        )
        ripte_actualizado = float(redondear(Decimal(str(capital_base)) * Decimal(str(ripte_coef))))
        
        dias_transcurridos = (input_data.final_date - input_data.pmi_date).days
        factor_dias = Decimal(str(dias_transcurridos)) / Decimal('365.0')
        interes_puro_3_pct = float(redondear(Decimal(str(ripte_actualizado)) * Decimal('0.03') * factor_dias))
        total_ripte_3 = float(redondear(Decimal(str(ripte_actualizado)) + Decimal(str(interes_puro_3_pct))))
        
        tasa_activa_pct, total_tasa_activa = self.data_manager.calcular_tasa_activa(
            input_data.pmi_date, input_data.final_date, capital_base
        )
        
        inflacion_acum_pct = self.data_manager.calcular_inflacion(
            input_data.pmi_date, input_data.final_date
        )
        
        return Results(
            capital_formula=capital_formula,
            capital_base=capital_base,
            piso_aplicado=piso_aplicado,
            piso_info=piso_info,
            piso_monto=piso_minimo if piso_minimo else 0.0,
            piso_proporcional=piso_proporcional,
            piso_norma=piso_norma,
            adicional_20_pct=adicional_20_pct,
            ripte_coef=ripte_coef,
            ripte_pmi=ripte_pmi,
            ripte_final=ripte_final,
            ripte_actualizado=ripte_actualizado,
            interes_puro_3_pct=interes_puro_3_pct,
            total_ripte_3=total_ripte_3,
            tasa_activa_pct=tasa_activa_pct,
            total_tasa_activa=total_tasa_activa,
            inflacion_acum_pct=inflacion_acum_pct
        )
    
    def _calcular_capital_formula(self, input_data: InputData) -> float:
        """Calcula capital según fórmula"""
        capital = Decimal(str(input_data.ibm)) * Decimal('53') * (Decimal('65') / Decimal(str(input_data.edad))) * (Decimal(str(input_data.incapacidad_pct)) / Decimal('100'))
        return float(redondear(capital))
    
    def _aplicar_piso_minimo(self, capital_formula: float, piso_minimo: Optional[float], 
                           piso_norma: str, incapacidad_pct: float) -> Tuple[float, bool, str, float]:
        """Aplica piso mínimo si corresponde"""
        if piso_minimo is None:
            return capital_formula, False, "No se encontró piso mínimo para la fecha", 0.0
        
        piso_proporcional = piso_minimo * (incapacidad_pct / 100)
        
        if capital_formula >= piso_proporcional:
            return capital_formula, False, f"Supera piso mínimo {piso_norma}", piso_proporcional
        else:
            return piso_proporcional, True, f"Se aplica piso mínimo {piso_norma}", piso_proporcional

class NumberUtils:
    """Utilidades para formateo de números"""
    
    @staticmethod
    def format_money(amount: float) -> str:
        """Formatea cantidad como dinero argentino"""
        return f"$ {amount:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    
    @staticmethod
    def format_percentage(percentage: float) -> str:
        """Formatea porcentaje"""
        return f"{percentage:.2f}%".replace('.', ',')

# --- Carga forzada de datasets en cada ejecución ---
data_mgr = DataManager()
st.session_state.data_manager = data_mgr
st.session_state.calculator = Calculator(data_mgr)

if 'results' not in st.session_state:
    st.session_state.results = None
if 'input_data' not in st.session_state:
    st.session_state.input_data = None

# Header personalizado
st.markdown("""
<div class="main-header">
    <h1>🧮 CALCULADORA INDEMNIZACIONES LEY 24.557</h1>
</div>
""", unsafe_allow_html=True)

# Formulario horizontal
st.subheader("📋 Datos del Caso")

# Primera fila - Fechas
col1, col2 = st.columns(2)
with col1:
    pmi_date_input = st.date_input(
        "📅 Fecha del siniestro (PMI)",
        value=date(2020, 1, 1),
        format="DD/MM/YYYY"
    )
with col2:
    final_date_input = st.date_input(
        "📅 Fecha final",
        value=date.today(),
        format="DD/MM/YYYY"
    )

# Segunda fila - IBM, Edad, Incapacidad
col3, col4, col5 = st.columns(3)
with col3:
    ibm = st.number_input(
        "💰 IBM ($)",
        min_value=0.0,
        value=100000.0,
        step=1000.0,
        format="%.2f"
    )
with col4:
    edad = st.number_input(
        "👤 Edad",
        min_value=18,
        max_value=100,
        value=45,
        step=1
    )
with col5:
    incapacidad_pct = st.number_input(
        "📊 Incapacidad (%)",
        min_value=0.01,
        max_value=100.0,
        value=50.0,
        step=0.1,
        format="%.2f"
    )

# Tercera fila - Checkbox y botón
col6, col7 = st.columns([2, 1])
with col6:
    incluir_20_pct = st.checkbox(
        "Incluir 20% adicional (art. 3, Ley 26.773)",
        value=True
    )
with col7:
    calcular = st.button("⚡ CALCULAR", use_container_width=True, type="primary")

if calcular:
    try:
        input_data = InputData(
            pmi_date=pmi_date_input,
            final_date=final_date_input,
            ibm=ibm,
            edad=edad,
            incapacidad_pct=incapacidad_pct,
            incluir_20_pct=incluir_20_pct
        )
        
        if input_data.pmi_date > input_data.final_date:
            st.error("⚠️ La fecha PMI no puede ser posterior a la fecha final")
        else:
            st.session_state.results = st.session_state.calculator.calcular_indemnizacion(input_data)
            st.session_state.input_data = input_data
            st.rerun()
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")

st.markdown("---")
    
# Main content - Resultados
if st.session_state.results is not None:
    results = st.session_state.results
    input_data = st.session_state.input_data
    
    # Tabs principales (agregamos tab6 para PDF)
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Resultados",
        "🖨️ Imprimir PDF",
        "📄 Sentencia", 
        "💰 Liquidación", 
        "📋 Mínimos SRT",
        "ℹ️ Información"
    ])
    
    with tab1:
        st.subheader("📊 Resultados del Cálculo")
        
        # Primera fila - Capital Base
        st.markdown("### 💼 Capital Base (Ley 24.557)")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric(
                "Capital Fórmula",
                NumberUtils.format_money(results.capital_formula)
            )
        with col_b:
            st.metric(
                "Adicional 20%",
                NumberUtils.format_money(results.adicional_20_pct) if results.adicional_20_pct > 0 else "No aplica"
            )
        with col_c:
            # Agregar (piso) si corresponde
            label_piso = " (piso)" if results.piso_aplicado else ""
            st.markdown(
                f'<div style="text-align: left;"><p style="color: red; font-size: 14px; margin-bottom: 4px; font-weight: bold;">CAPITAL BASE TOTAL</p>'
                f'<p style="color: red; font-size: 36px; font-weight: 600; margin: 0;">{NumberUtils.format_money(results.capital_base)}{label_piso}</p></div>',
                unsafe_allow_html=True
            )
        
        st.info(f"ℹ️ {results.piso_info}")
        
        # Fórmula aplicada (movida aquí)
        with st.expander("🔢 Ver fórmula aplicada"):
            st.code(f"""
Fórmula: IBM × 53 × (65 / Edad) × (Incapacidad% / 100)

Cálculo:
{NumberUtils.format_money(input_data.ibm)} × 53 × (65 / {input_data.edad}) × ({input_data.incapacidad_pct}% / 100)

Capital calculado: {NumberUtils.format_money(results.capital_formula)}
            """, language=None)
        
        st.markdown("---")
        
        # Segunda fila - Actualizaciones
        st.markdown("### 📈 Actualizaciones e intereses")
        col_1, col_2 = st.columns(2)
        
        with col_1:
            # Determinar si RIPTE es mayor
            es_mayor = results.total_ripte_3 >= results.total_tasa_activa
            st.success("**RIPTE + 3% ANUAL**") if es_mayor else st.info("**RIPTE + 3% ANUAL**")
            st.metric(
                "Total Actualizado",
                NumberUtils.format_money(results.total_ripte_3),
                delta=f"+{NumberUtils.format_money(results.total_ripte_3 - results.capital_base)}"
            )
            with st.expander("Ver detalle"):
                st.write(f"**Coeficiente RIPTE:** {results.ripte_coef:.6f}")
                st.write(f"**Capital actualizado RIPTE:** {NumberUtils.format_money(results.ripte_actualizado)}")
                st.write(f"**Interés puro 3%:** {NumberUtils.format_money(results.interes_puro_3_pct)}")
        
        with col_2:
            # Determinar si Tasa es mayor
            es_mayor = results.total_tasa_activa > results.total_ripte_3
            st.success("**TASA ACTIVA BNA**") if es_mayor else st.info("**TASA ACTIVA BNA**")
            st.metric(
                "Total Actualizado",
                NumberUtils.format_money(results.total_tasa_activa),
                delta=f"+{NumberUtils.format_money(results.total_tasa_activa - results.capital_base)}"
            )
            with st.expander("Ver detalle"):
                st.write(f"**Tasa acumulada período:** {NumberUtils.format_percentage(results.tasa_activa_pct)}")
        
        st.markdown("---")
        
        # Inflación (misma estructura de columnas que arriba)
        col_vacio, col_inflacion = st.columns(2)
        
        with col_vacio:
            # Espacio reservado para futura tasa adicional
            pass
        
        with col_inflacion:
            st.error("**INFLACIÓN ACUMULADA (Referencia)**")
            st.metric(
                "Total Acumulado",
                NumberUtils.format_percentage(results.inflacion_acum_pct)
            )
            with st.expander("Ver detalle"):
                st.write(f"**Período:** {input_data.pmi_date.strftime('%d/%m/%Y')} - {input_data.final_date.strftime('%d/%m/%Y')}")
    
    
    with tab2:
        st.subheader("🖨️ Imprimir PDF")
        
        # Determinar método más favorable
        if results.total_ripte_3 >= results.total_tasa_activa:
            metodo_favorable = "RIPTE + 3%"
            color_ripte = "#28a745"
            color_tasa = "#6c757d"
        else:
            metodo_favorable = "Tasa Activa BNA"
            color_ripte = "#6c757d"
            color_tasa = "#28a745"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Cálculo Indemnización LRT</title>
            <style>
                @page {{size: A4; margin: 1cm;}}
                @media print {{
                    body {{background: white !important;}}
                    .container {{box-shadow: none !important;}}
                    .no-print {{display: none !important;}}
                    /* Optimización para B&N */
                    .formula-section {{
                        background: white !important;
                        color: black !important;
                        border: 2px solid black !important;
                    }}
                    .update-card {{
                        background: white !important;
                        border: 2px solid black !important;
                    }}
                    .card-inner {{
                        background: #f5f5f5 !important;
                        border: 1px solid #333 !important;
                    }}
                    .winner-badge {{
                        background: black !important;
                        color: white !important;
                        border: 2px solid black !important;
                    }}
                }}
                body {{
                    font-family: 'Segoe UI', sans-serif;
                    margin: 0;
                    padding: 10px;
                    background: #f0f2f5;
                }}
                .container {{
                    background: white;
                    border-radius: 8px;
                    padding: 20px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                    max-width: 800px;
                    margin: 0 auto;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 15px;
                    padding-bottom: 10px;
                    border-bottom: 3px solid black;
                }}
                .header h1 {{
                    color: #000;
                    font-size: 20px;
                    margin: 0;
                    font-weight: 700;
                }}
                .formula-section {{
                    background: #f8f9fa;
                    color: #000;
                    padding: 15px;
                    border-radius: 8px;
                    margin-bottom: 12px;
                    text-align: center;
                    border: 2px solid #333;
                }}
                .formula-section h2 {{
                    font-size: 13px;
                    margin: 0 0 8px 0;
                    font-weight: 700;
                }}
                .formula-text {{
                    font-size: 13px;
                    margin: 4px 0;
                    font-family: 'Courier New', monospace;
                    font-weight: 600;
                }}
                .result-big {{
                    font-size: 32px;
                    font-weight: 800;
                    margin: 10px 0 8px 0;
                    color: #000;
                }}
                .result-label {{
                    font-size: 11px;
                    font-weight: 600;
                    color: #000;
                }}
                .update-card {{
                    border-radius: 8px;
                    padding: 12px;
                    margin-bottom: 10px;
                    border: 3px solid #333;
                    background: white;
                }}
                .card-inner {{
                    background: #f5f5f5;
                    padding: 10px;
                    border-radius: 6px;
                    border: 1px solid #666;
                }}
                .update-ripte {{border-color: #000;}}
                .update-tasa {{border-color: #555;}}
                .update-inflacion {{border-color: #333;}}
                .card-title {{
                    font-size: 12px;
                    font-weight: 700;
                    text-transform: uppercase;
                    margin-bottom: 8px;
                    letter-spacing: 0.5px;
                    color: #000;
                }}
                .card-value {{
                    font-size: 28px;
                    font-weight: 800;
                    margin: 8px 0;
                    color: #000;
                }}
                .card-detail {{
                    font-size: 10px;
                    color: #333;
                    margin-top: 6px;
                    font-weight: 500;
                }}
                .winner-badge {{
                    display: inline-block;
                    background: #000;
                    color: white;
                    padding: 3px 10px;
                    border-radius: 12px;
                    font-size: 9px;
                    font-weight: 700;
                    margin-top: 6px;
                    border: 2px solid #000;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 12px;
                    padding-top: 10px;
                    border-top: 2px solid #333;
                    color: #000;
                    font-size: 9px;
                    line-height: 1.3;
                    font-weight: 500;
                }}
                .period-info {{
                    background: #f5f5f5;
                    padding: 8px;
                    border-radius: 6px;
                    margin-top: 10px;
                    text-align: center;
                    font-size: 10px;
                    color: #000;
                    border: 1px solid #333;
                    line-height: 1.4;
                    font-weight: 500;
                }}
                .print-btn {{
                    background: #333;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 8px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 600;
                    margin: 15px auto;
                    display: block;
                }}
                .print-btn:hover {{
                    background: #000;
                }}
            </style>
        </head>
        <body>
            <button class="print-btn no-print" onclick="window.print()">🖨️ IMPRIMIR PDF</button>
            <div class="container">
                <div class="header"><h1>⚖️ CÁLCULO INDEMNIZACIÓN LRT</h1></div>
                <div class="formula-section">
                    <h2>🧮 FÓRMULA APLICADA</h2>
                    <div class="formula-text">IBM × 53 × (65 / Edad) × (Incapacidad% / 100)</div>
                    <div class="formula-text">${input_data.ibm:,.2f} × 53 × (65 / {input_data.edad}) × ({input_data.incapacidad_pct}% / 100)</div>
                    <div class="result-label">CAPITAL BASE TOTAL</div>
                    <div class="result-big">${results.capital_base:,.2f}</div>
                    <div class="result-label">{results.piso_info}</div>
                </div>
                <div class="update-card update-ripte">
                    <div class="card-title ripte-title">📈 RIPTE + 3% ANUAL</div>
                    <div class="card-inner">
                        <div class="card-value ripte-value">${results.total_ripte_3:,.2f}</div>
                        <div class="card-detail"><strong>Coef:</strong> {results.ripte_coef:.4f} | <strong>Interés 3%:</strong> ${results.interes_puro_3_pct:,.2f}</div>
                        {"<div class='winner-badge'>✓ MÁS FAVORABLE</div>" if metodo_favorable == "RIPTE + 3%" else ""}
                    </div>
                </div>
                <div class="update-card update-tasa">
                    <div class="card-title tasa-title">💵 TASA ACTIVA BNA</div>
                    <div class="card-inner">
                        <div class="card-value tasa-value">${results.total_tasa_activa:,.2f}</div>
                        <div class="card-detail"><strong>Tasa acum:</strong> {results.tasa_activa_pct:.2f}%</div>
                        {"<div class='winner-badge'>✓ MÁS FAVORABLE</div>" if metodo_favorable == "Tasa Activa BNA" else ""}
                    </div>
                </div>
                <div class="update-card update-inflacion">
                    <div class="card-title inflacion-title">📊 INFLACIÓN ACUMULADA (Referencia)</div>
                    <div class="card-inner">
                        <div class="card-value inflacion-value">{results.inflacion_acum_pct:.2f}%</div>
                        <div class="card-detail"><strong>Acumulado período IPC</strong></div>
                    </div>
                </div>
                <div class="period-info">
                    <strong>📅 Período:</strong> {input_data.pmi_date.strftime('%d/%m/%Y')} - {input_data.final_date.strftime('%d/%m/%Y')}<br>
                    <strong>🎂 Edad:</strong> {input_data.edad} años | <strong>📊 Incapacidad:</strong> {input_data.incapacidad_pct}% | <strong>💰 IBM:</strong> ${input_data.ibm:,.2f}
                </div>
                <div class="footer">Sistema Integrado - Tribunal de Trabajo<br>Generado el {date.today().strftime('%d/%m/%Y')}</div>
            </div>
        </body>
        </html>
        """
        
        # Mostrar vista previa con altura ajustada
        st.components.v1.html(html_content, height=950, scrolling=True)

    with tab3:
        st.subheader("📄 Texto para Sentencia")
        
        # Generar texto de sentencia según ejemplo
        mes_pmi = get_mes_nombre(input_data.pmi_date.month)
        anio_pmi = input_data.pmi_date.year
        
        # Determinar texto según si supera o no el piso
        if results.piso_aplicado:
            texto_piso = f"""El monto es inferior al piso mínimo determinado por la {results.piso_norma}, que multiplicado por el porcentaje de incapacidad ({input_data.incapacidad_pct}%) alcanza la suma de {NumberUtils.format_money(results.piso_proporcional)}, por lo que se aplica este último."""
        else:
            texto_piso = f"""Dicho monto supera el piso mínimo determinado por la {results.piso_norma}, que multiplicado por el porcentaje de incapacidad ({input_data.incapacidad_pct}%) alcanza la suma de {NumberUtils.format_money(results.piso_proporcional)}."""
        
        monto_letras = numero_a_letras(results.capital_base)
        
        sentencia_text = f"""a) Fórmula:
Valor de IBM ({NumberUtils.format_money(input_data.ibm)}) x 53 x 65/edad({input_data.edad}) x Incapacidad ({input_data.incapacidad_pct}%)
Capital calculado: {NumberUtils.format_money(results.capital_formula)}
{texto_piso}

b) {'20% Art. 3 Ley 26.773: ' + NumberUtils.format_money(results.adicional_20_pct) if input_data.incluir_20_pct else '20% Art. 3 Ley 26.773: no se aplica'}

Total: {NumberUtils.format_money(results.capital_base)}
SON {monto_letras}

c) Mientras la tasa legal aplicable (Tasa Activa Banco Nación) alcanzó para el período comprometido ({mes_pmi} {anio_pmi} a la fecha) un total del {NumberUtils.format_percentage(results.tasa_activa_pct)}, la inflación del mismo período alcanzó la suma de {NumberUtils.format_percentage(results.inflacion_acum_pct)}."""
        
        st.text_area("Texto de Sentencia", sentencia_text, height=450)
        
        if st.button("📋 Copiar Texto", key="copy_sentencia"):
            st.success("✓ Texto copiado al portapapeles")
    
    with tab4:
        st.subheader("💰 Liquidación Judicial")
        
        # Determinar método más favorable
        if results.total_ripte_3 >= results.total_tasa_activa:
            total_actualizacion = results.total_ripte_3
            metodo_usado = "tasa de variación RIPTE"
        else:
            total_actualizacion = results.total_tasa_activa
            metodo_usado = "Tasa Activa BNA"
        
        # Obtener fechas de RIPTE
        mes_final = get_mes_nombre(input_data.final_date.month)
        anio_final = input_data.final_date.year
        mes_pmi = get_mes_nombre(input_data.pmi_date.month)
        anio_pmi = input_data.pmi_date.year
        
        # Calcular porcentaje de incremento RIPTE
        pct_ripte = (results.ripte_coef - 1) * 100
        
        # Obtener fecha del último RIPTE disponible (primer registro ya que CSV está invertido)
        if not data_mgr.ripte_data.empty:
            fecha_ultimo_ripte = data_mgr.ripte_data.iloc[0]['fecha']
            mes_ultimo_ripte = get_mes_nombre(fecha_ultimo_ripte.month)
            anio_ultimo_ripte = fecha_ultimo_ripte.year
        else:
            mes_ultimo_ripte = get_mes_nombre(input_data.final_date.month)
            anio_ultimo_ripte = input_data.final_date.year
        
        # Calcular tasas judiciales (2.2% según ejemplo)
        tasa_justicia = total_actualizacion * 0.022
        sobretasa_caja = tasa_justicia * 0.10
        total_final = total_actualizacion + tasa_justicia + sobretasa_caja
        
        # Convertir monto a letras
        monto_letras = numero_a_letras(total_final)
        
        liquidacion_text = f"""Quilmes, en la fecha en que se suscribe con firma digital (Ac. SCBA. 3975/20). 
**LIQUIDACION** que practica la Actuaria en el presente expediente. ** **

--Capital {NumberUtils.format_money(results.capital_base)} 
--Actualización mediante {metodo_usado}, ({mes_ultimo_ripte}/{anio_ultimo_ripte} {results.ripte_final:,.2f} -último índice publicado- / {mes_pmi} {anio_pmi} {results.ripte_pmi:,.2f} = coef {results.ripte_coef:.2f} = {pct_ripte:.0f}%) {NumberUtils.format_money(results.ripte_actualizado)} 
--Interés puro del 3% anual desde {input_data.pmi_date.strftime('%d/%m/%Y')} hasta {input_data.final_date.strftime('%d/%m/%Y')} {NumberUtils.format_money(results.interes_puro_3_pct)} 
--SUBTOTAL {NumberUtils.format_money(total_actualizacion)} 

*Tasa de Justicia (2,2%) {NumberUtils.format_money(tasa_justicia)} *
Sobretasa Contribución Caja de Abogados (10% de Tasa) {NumberUtils.format_money(sobretasa_caja)} 

**TOTAL** **{NumberUtils.format_money(total_final)}** 

Importa la presente liquidación la suma de {monto_letras}- 

De la liquidación practicada, traslado a las partes por el plazo de cinco (5) días, bajo apercibimiento de tenerla por consentida (art 59 de la Ley 15.057 - RC 1840/24 SCBA ) Notifíquese.-"""
        
        st.text_area("Liquidación", liquidacion_text, height=500)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📋 Copiar Liquidación", key="copy_liquidacion"):
                st.success("✓ Texto copiado al portapapeles")
        with col2:
            if st.button("🖨️ Ir a Imprimir PDF", key="goto_print"):
                st.info("👉 Use la pestaña 'Imprimir PDF' para generar el documento completo")
    
    with tab5:
        st.subheader("📋 Mínimos de la SRT")
        
        if not st.session_state.data_manager.pisos_data.empty:
            df_pisos = st.session_state.data_manager.pisos_data.copy()
            
            # Invertir orden para mostrar más recientes arriba
            df_pisos = df_pisos.iloc[::-1].reset_index(drop=True)
            
            # Formatear fechas
            df_pisos['desde'] = df_pisos['desde'].apply(lambda x: x.strftime('%d/%m/%Y') if isinstance(x, date) else str(x))
            df_pisos['hasta'] = df_pisos['hasta'].apply(lambda x: x.strftime('%d/%m/%Y') if isinstance(x, date) and not pd.isna(x) else 'Vigente')
            df_pisos['piso'] = df_pisos['piso'].apply(lambda x: NumberUtils.format_money(x))
            
            # Crear columna de enlace clicable
            def crear_link_html(enlace):
                enlace_str = str(enlace).strip()
                if enlace_str and enlace_str != '' and enlace_str.lower() != 'nan' and enlace_str.startswith('http'):
                    return f'<a href="{enlace_str}" target="_blank">Ver norma</a>'
                return 'N/A'
            
            # Crear DataFrame para mostrar
            df_display = pd.DataFrame({
                'Norma': df_pisos['resol'],
                'Vigencia Desde': df_pisos['desde'],
                'Vigencia Hasta': df_pisos['hasta'],
                'Monto Mínimo': df_pisos['piso'],
                'Enlace': df_pisos['enlace'].apply(crear_link_html)
            })
            
            # Mostrar tabla con HTML para los links
            st.markdown(
                df_display.to_html(escape=False, index=False),
                unsafe_allow_html=True
            )
            
            st.markdown("---")
            st.caption("💡 Haga clic en 'Ver norma' para acceder al documento oficial")
        else:
            st.warning("No hay datos de pisos disponibles")
    
    with tab6:
        st.subheader("ℹ️ Información del Sistema")
        
        info_tab1, info_tab2, info_tab3 = st.tabs(["Fórmulas", "Fuentes", "Marco Legal"])
        
        with info_tab1:
            st.markdown("""
            ### FÓRMULAS APLICADAS:

            **1. CAPITAL BASE (Ley 24.557):**
            ```
            Capital = IBM × 53 × (% Incapacidad / 100) × (65 / Edad)
            ```
            - Se compara con piso mínimo vigente a la fecha PMI
            - Si el piso es mayor, se aplica el piso proporcional a la incapacidad
            - Se agrega 20% adicional según Art. 3 Ley 26.773 (excepto in itinere)

            **2. ACTUALIZACIÓN RIPTE + 3% **
            - Coeficiente RIPTE = RIPTE Final / RIPTE PMI
            - Capital actualizado = Capital Base × Coeficiente RIPTE
            - Interés puro 3% = Capital Actualizado RIPTE × 0.03 × (días / 365.25)
            - Total = Capital actualizado + Interés puro 3%

            **3. TASA ACTIVA BNA (Art. 12 inc. 2 Ley 24.557):**
            - Se aplica la tasa activa promedio del Banco Nación
            - Cálculo mensual prorrateado por días
            - Suma acumulativa sin capitalización

            **4. INFLACIÓN ACUMULADA:**
            ```
            Inflación = [(1 + r₁/100) × (1 + r₂/100) × ... × (1 + rₙ/100) - 1] × 100
            ```
            
            **CRITERIO DE APLICACIÓN:**
            Se aplica la actualización más favorable entre RIPTE+3% y Tasa Activa.
            La inflación se muestra como referencia comparativa.
            """)
        
        with info_tab2:
            st.markdown("""
            ### FUENTES DE DATOS:         
            Los datos se obtienen de las siguientes fuentes:
            
            1) Las **VARIACIONES DE LA TASA ACTIVA BANCO NACION** 
            de la tabla publicada por el Consejo Prof. de Cs. Ec. 
            [https://trivia.consejo.org.ar/]
            
            2) El **INDICE DE INFLACIÓN** se obtiene de la siguiente manera: 
            desde 2016 en adelante de los datos publicados en **INDEC** - Índice de Precios al Consumidor (IPC)
            [https://www.indec.gob.ar/](https://www.indec.gob.ar/)
            Con anterioridad a 2016 se aplica las tablas de "Inflación Mensual" del 
            **BCRA** - Banco Central - Tasas de referencia
            [https://www.bcra.gob.ar/](https://www.bcra.gob.ar/)

            3) Los indices **RIPTES** se obtienen de
            [https://www.argentina.gob.ar/trabajo/seguridadsocial/ripte/]

            4) Las tablas sobre minimos aplicables de las resoluciones de SRT y MTySS
            [https://www.srt.gob.ar/](https://www.srt.gob.ar/)
            """)
        
        with info_tab3:
            st.markdown("""
            ### MARCO NORMATIVO:

            **LEY 24.557 - RIESGOS DEL TRABAJO:**
            - Art. 14: Fórmula de cálculo de incapacidad permanente parcial
            - Art. 12 inc. 2: Actualización por tasa activa BNA

            **LEY 26.773 - RÉGIMEN DE ORDENAMIENTO LABORAL:**
            - Art. 3: Incremento del 20% sobre prestaciones dinerarias
            - Excepción: No aplica para accidentes in itinere

            **DECRETO 1694/2009:**
            - Actualización de prestaciones según RIPTE
            - Metodología de aplicación del coeficiente
            """)

# Mostrar últimos datos disponibles
st.markdown("---")
mostrar_ultimos_datos_universal()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p><strong>Calculadora Indemnizaciones LRT</strong><br>
    Tribunal de Trabajo<br>
    Versión 1.0 de prueba
    Los calculos deben ser verificados manualmente</p>
</div>
""", unsafe_allow_html=True)