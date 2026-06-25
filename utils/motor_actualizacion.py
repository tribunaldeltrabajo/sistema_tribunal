#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MOTOR DE ACTUALIZACIÓN
Compartido por actualizacion.py, calculadora_audiencias.py y calculadora_relatoria.py

Métodos disponibles:
  1. IPC + 3% simple  — Art. 54 / Art. 276 LCT (régimen general)
  2. Tasa Pasiva BCRA     — Art. 55 inc. a) Ley 27.802
  3. Art. 55 completo     — muestra tasa pasiva, techo (IPC+3%) y piso (67%)
  4. Método BCRA          — CER diario + 3% compuesto (réplica calculadora BCRA)

Datasets requeridos en data/:
  dataset_ipc.csv         — IPC INDEC acumulado, base dic-2016=100
  dataset_cer.csv         — CER mensual hasta nov-2016
  dataset_tasa.csv        — Tasa activa BNA diaria
  dataset_CER.xls         — CER diario BCRA (para método BCRA)
  dataset_tasa_pasiva.xls — Tasa pasiva BCRA Res. 45/26 (para art. 55)
"""

import os
import pandas as pd
import xlrd
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR  = os.path.join(BASE_DIR, "data")

PATH_IPC       = os.path.join(DATA_DIR, "dataset_ipc.csv")
PATH_CER_XLS   = os.path.join(DATA_DIR, "diar_cer.xls")
PATH_TASA      = os.path.join(DATA_DIR, "tasas_activa_bna.csv")
PATH_TP_XLS    = os.path.join(DATA_DIR, "diar_ind.xls")
PATH_RIPTE     = os.path.join(DATA_DIR, "dataset_ripte.csv")

FECHA_INICIO_IPC = date(2016, 12, 1)

# ─────────────────────────────────────────────
# LABELS Y COLORES CENTRALIZADOS
# ─────────────────────────────────────────────
LABEL_IPC       = 'IPC + 3% (Art. 276 LCT conf. Art. 54 LML)'
LABEL_TASA_ACT  = 'Tasa Activa BNA (Art. 12 inc. b LRT conf. Art. 11 Ley 27.348)'
LABEL_ART55_A   = 'Tasa Pasiva BCRA (Art. 55 inc. a LML conf. Res. 45/26 BCRA)'
LABEL_ART55_B   = 'IPC + 3% — techo (Art. 55 inc. b LML)'
LABEL_ART55_C   = 'Art. 55 inc. c LML — 67% de IPC + 3%'
LABEL_CER       = 'CER + 3% (valor de referencia inflación)'
LABEL_CER_BCRA_B = 'CER + 3% — techo BCRA (Art. 55 inc. b LML)'
LABEL_CER_BCRA_C = 'Art. 55 inc. c LML — 67% de CER + 3%'
LABEL_RIPTE     = 'RIPTE + 6% (Art. 8° Ley 24.557)'

# Colores por módulo
COLOR_AUDIENCIAS = {'ipc': '#4a8fa8', 'tasa': '#8e6f9e', 'gris': '#a0a8b0'}
COLOR_RELATORIA  = {'ipc': '#5ba3b8', 'tasa': '#9c82ae', 'art55': '#6a9e7a',
                    'tp': '#b8836a',  'cer':  '#9a9eaa'}
COLOR_ACTUALIZACION = {'ipc': '#b8952a', 'tasa': '#7b9e87', 'cer': '#9a9eaa'}


def redondear(v):
    return Decimal(str(v)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ─────────────────────────────────────────────
# CARGA DE DATASETS
# ─────────────────────────────────────────────

def cargar_ipc() -> pd.DataFrame:
    df = pd.read_csv(PATH_IPC)
    df.columns = df.columns.str.strip().str.lower()
    df['fecha'] = pd.to_datetime(df['periodo']).dt.date
    df['indice'] = pd.to_numeric(df['indice'], errors='coerce')
    return df.dropna(subset=['fecha','indice']).sort_values('fecha').reset_index(drop=True)


def cargar_ripte() -> pd.DataFrame:
    """
    Lee dataset_ripte.csv (año, mes en texto, indice_ripte, variacion_mensual, monto_en_pesos).
    Devuelve DataFrame ordenado ascendente por fecha, con columna 'fecha' = primer día del mes
    e 'indice' = indice_ripte.
    """
    _meses_map = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
        'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
    }
    df = pd.read_csv(PATH_RIPTE)
    df.columns = df.columns.str.strip().str.lower()
    df['mes_txt'] = df['mes'].astype(str).str.strip().str.lower()
    df['mes_num'] = df['mes_txt'].map(_meses_map)
    df['anio']    = pd.to_numeric(df['año'], errors='coerce').astype('Int64')
    df['fecha']   = df.apply(
        lambda r: date(int(r['anio']), int(r['mes_num']), 1)
        if pd.notna(r['anio']) and pd.notna(r['mes_num']) else None, axis=1
    )
    df['indice'] = pd.to_numeric(df['indice_ripte'], errors='coerce')
    return df.dropna(subset=['fecha', 'indice']).sort_values('fecha').reset_index(drop=True)


def cargar_cer_csv() -> pd.DataFrame:
    """
    Lee el CER diario (dataset_CER.xls / diar_cer.xls) y devuelve un DataFrame
    mensual con el valor del último día disponible de cada mes.
    Compatible con la lógica de empalme IPC+CER.
    """
    datos = cargar_cer_xls()  # dict {date: float}
    # Agrupar por mes: tomar el valor del primer día disponible de cada mes
    meses = {}
    for d, v in datos.items():
        clave = date(d.year, d.month, 1)
        if clave not in meses:
            meses[clave] = v
    rows = sorted(meses.items())
    df = pd.DataFrame(rows, columns=['fecha', 'indice'])
    return df.sort_values('fecha').reset_index(drop=True)


def cargar_tasa() -> pd.DataFrame:
    """Lee tasas_activa_bna.csv (promedio mensual %) con columnas fecha (MM/YYYY) y tasa_activa."""
    import calendar as _cal
    df = pd.read_csv(PATH_TASA)
    df.columns = df.columns.str.strip().str.lower()
    df['mes']  = df['fecha'].str.split('/').str[0].astype(int)
    df['anio'] = df['fecha'].str.split('/').str[1].astype(int)
    df['Desde'] = df.apply(lambda r: pd.Timestamp(date(r['anio'], r['mes'], 1)), axis=1)
    df['Hasta'] = df.apply(lambda r: pd.Timestamp(date(r['anio'], r['mes'],
                           _cal.monthrange(r['anio'], r['mes'])[1])), axis=1)
    df['Valor'] = pd.to_numeric(df['tasa_activa'], errors='coerce')
    return df.dropna(subset=['Desde', 'Hasta', 'Valor']).sort_values('Desde').reset_index(drop=True)


def cargar_cer_xls() -> dict:
    """CER diario BCRA para método BCRA. Devuelve {date: float}."""
    wb = xlrd.open_workbook(PATH_CER_XLS)
    sh = wb.sheet_by_name('Totales_diarios')
    datos = {}
    for r in range(sh.nrows):
        if sh.row_len(r) < 2: continue
        fv = sh.cell_value(r, 0)
        cv = sh.cell_value(r, 1)
        if isinstance(fv, str) and '/' in fv and isinstance(cv, float):
            try:
                p = fv.strip().split('/')
                d = date(int(p[2]), int(p[1]), int(p[0]))
                datos[d] = cv
            except: pass
    return datos


def cargar_tasa_pasiva() -> dict:
    """Tasa Pasiva BCRA Res. 45/26, columna 10. Devuelve {date: float}."""
    wb = xlrd.open_workbook(PATH_TP_XLS)
    sh = wb.sheet_by_name('Totales_diarios')
    datos = {}
    for r in range(27, sh.nrows):
        if sh.row_len(r) < 11: continue
        fv = sh.cell_value(r, 0)
        cv = sh.cell_value(r, 10)
        if isinstance(fv, str) and '/' in fv and isinstance(cv, float) and cv > 0:
            try:
                p = fv.strip().split('/')
                d = date(int(p[2]), int(p[1]), int(p[0]))
                datos[d] = cv
            except: pass
    return datos


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _get_ipc(df_ipc, fecha):
    fm = date(fecha.year, fecha.month, 1)
    sub = df_ipc[df_ipc['fecha'] <= fm]
    return float(sub.iloc[-1]['indice']) if not sub.empty else 100.0

def _get_ripte(df_ripte, fecha):
    fm = date(fecha.year, fecha.month, 1)
    sub = df_ripte[df_ripte['fecha'] <= fm]
    return float(sub.iloc[-1]['indice']) if not sub.empty else float(df_ripte.iloc[0]['indice'])

def _get_cer_csv(df_cer, fecha):
    fm = date(fecha.year, fecha.month, 1)
    sub = df_cer[df_cer['fecha'] <= fm]
    return float(sub.iloc[-1]['indice']) if not sub.empty else float(df_cer.iloc[0]['indice'])

def _get_diario(datos: dict, fecha: date) -> float:
    """Busca valor exacto o el más reciente anterior."""
    if fecha in datos: return datos[fecha]
    cands = [d for d in datos if d <= fecha]
    return datos[max(cands)] if cands else list(datos.values())[0]

def _ultimo(datos: dict):
    ultimo = max(datos.keys())
    return ultimo, datos[ultimo]


# ─────────────────────────────────────────────
# MOTOR 1 — IPC + 3% SIMPLE
# ─────────────────────────────────────────────

def calcular_ipc_cer_3(monto, fecha_origen, fecha_calculo, df_ipc, df_cer):
    """
    Actualización por IPC empalmado con CER + 3% anual simple.
    Art. 54 / Art. 276 LCT.
    """
    ipc_ultimo       = _get_ipc(df_ipc, fecha_calculo)
    ipc_ultimo_fecha = df_ipc[df_ipc['fecha'] <= date(fecha_calculo.year, fecha_calculo.month, 1)].iloc[-1]['fecha']

    if fecha_origen >= FECHA_INICIO_IPC:
        ipc_origen  = _get_ipc(df_ipc, fecha_origen)
        coef        = ipc_ultimo / ipc_origen if ipc_origen > 0 else 1.0
        metodo      = 'IPC'
        cer_origen  = None
        cer_nov2016 = None
        coef_cer    = None
        coef_ipc    = coef
    else:
        cer_origen  = _get_cer_csv(df_cer, fecha_origen)
        cer_nov2016 = _get_cer_csv(df_cer, date(2016, 11, 1))
        coef_cer    = cer_nov2016 / cer_origen if cer_origen > 0 else 1.0
        coef_ipc    = ipc_ultimo / 100.0
        coef        = coef_cer * coef_ipc
        metodo      = 'CER+IPC'
        ipc_origen  = 100.0

    capital_indexado = float(redondear(Decimal(str(monto)) * Decimal(str(coef))))
    dias             = (fecha_calculo - fecha_origen).days
    interes_3        = float(redondear(
        Decimal(str(capital_indexado)) * Decimal('0.03') * Decimal(str(dias)) / Decimal('365')
    ))
    total  = float(redondear(Decimal(str(capital_indexado)) + Decimal(str(interes_3))))
    art55_piso = float(redondear(Decimal(str(total)) * Decimal('0.67')))

    return {
        'metodo':           metodo,
        'monto_original':   monto,
        'ipc_origen':       ipc_origen,
        'ipc_origen_fecha': fecha_origen,
        'ipc_ultimo':       ipc_ultimo,
        'ipc_ultimo_fecha': ipc_ultimo_fecha,
        'cer_origen':       cer_origen,
        'cer_nov2016':      cer_nov2016,
        'coef_cer':         coef_cer,
        'coef_ipc':         coef_ipc,
        'coef':             coef,
        'pct_variacion':    (coef - 1) * 100,
        'capital_indexado': capital_indexado,
        'dias':             dias,
        'interes_3':        interes_3,
        'total':            total,
        'art55_piso':       art55_piso,
    }


# ─────────────────────────────────────────────
# MOTOR 1B — RIPTE + 6% SIMPLE
# ─────────────────────────────────────────────

def calcular_ripte_6(monto, fecha_origen, fecha_calculo, df_ripte):
    """
    Actualización por índice RIPTE + 6% anual simple.
    Mismo mecanismo que IPC+3%, pero con índice RIPTE e interés del 6%.
    Capital actualizado = monto × (RIPTE_calculo / RIPTE_origen)
    Interés = Capital actualizado × 0,06 × (días/365)
    """
    ripte_origen        = _get_ripte(df_ripte, fecha_origen)
    ripte_calculo        = _get_ripte(df_ripte, fecha_calculo)
    ripte_calculo_fecha  = df_ripte[df_ripte['fecha'] <= date(fecha_calculo.year, fecha_calculo.month, 1)].iloc[-1]['fecha']

    coef = ripte_calculo / ripte_origen if ripte_origen > 0 else 1.0
    capital_indexado = float(redondear(Decimal(str(monto)) * Decimal(str(coef))))
    dias = (fecha_calculo - fecha_origen).days
    interes_6 = float(redondear(
        Decimal(str(capital_indexado)) * Decimal('0.06') * Decimal(str(dias)) / Decimal('365')
    ))
    total = float(redondear(Decimal(str(capital_indexado)) + Decimal(str(interes_6))))

    return {
        'ripte_origen':        ripte_origen,
        'ripte_origen_fecha':  fecha_origen,
        'ripte_calculo':       ripte_calculo,
        'ripte_calculo_fecha': ripte_calculo_fecha,
        'coef':                coef,
        'pct_variacion':       (coef - 1) * 100,
        'capital_indexado':    capital_indexado,
        'dias':                dias,
        'interes_6':           interes_6,
        'total':               total,
    }


# ─────────────────────────────────────────────
# MOTOR 2 — TASA PASIVA BCRA (Art. 55 inc. a)
# ─────────────────────────────────────────────

def calcular_tasa_pasiva(monto, fecha_origen, fecha_calculo, datos_tp):
    """
    Tasa Pasiva BCRA según metodología Resolución 45/26.
    i = ((100 + Tm) / (100 + T0) - 1) × 100
    T0 = día anterior al inicio.
    """
    T0 = _get_diario(datos_tp, fecha_origen - timedelta(days=1))
    Tm = _get_diario(datos_tp, fecha_calculo)
    ult_fecha, ult_valor = _ultimo(datos_tp)

    i     = ((100 + Tm) / (100 + T0) - 1) * 100
    total = float(redondear(Decimal(str(monto)) * (1 + Decimal(str(i)) / 100)))

    return {
        'T0':             T0,
        'T0_fecha':       fecha_origen - timedelta(days=1),
        'Tm':             Tm,
        'Tm_fecha':       fecha_calculo,
        'tp_ultimo_fecha': ult_fecha,
        'tp_ultimo_valor': ult_valor,
        'tasa_pct':       i,
        'total':          total,
    }


# ─────────────────────────────────────────────
# MOTOR 3 — ART. 55 COMPLETO
# ─────────────────────────────────────────────

def calcular_art55(monto, fecha_origen, fecha_calculo, df_ipc, df_cer, datos_tp, usar_bcra=False, datos_cer_xls=None):
    """
    Calcula los tres valores del art. 55 y determina cuál aplica.
    Devuelve siempre los tres para que el juez pueda apartarse.

    Banda:
      - tasa_pasiva > ipc_3:        aplica ipc_3  (techo inc. b)
      - tasa_pasiva < piso_67:      aplica piso_67 (piso inc. c)
      - piso_67 <= tasa_pasiva <= ipc_3: aplica tasa_pasiva (inc. a)
    """
    if usar_bcra and datos_cer_xls:
        r_ipc = calcular_bcra(monto, fecha_origen, fecha_calculo, datos_cer_xls)
    else:
        r_ipc = calcular_ipc_cer_3(monto, fecha_origen, fecha_calculo, df_ipc, df_cer)
    r_tp  = calcular_tasa_pasiva(monto, fecha_origen, fecha_calculo, datos_tp)

    ipc_3   = r_ipc['total']
    piso_67 = r_ipc['art55_piso']
    tp      = r_tp['total']

    if tp > ipc_3:
        aplica = 'techo'
        valor_aplica = ipc_3
        label_aplica = 'IPC + 3% (techo — inc. b)'
    elif tp < piso_67:
        aplica = 'piso'
        valor_aplica = piso_67
        label_aplica = '67% de IPC + 3% (piso — inc. c)'
    else:
        aplica = 'tasa_pasiva'
        valor_aplica = tp
        label_aplica = 'Tasa Pasiva BCRA (inc. a)'

    return {
        'tasa_pasiva':   tp,
        'ipc_3':         ipc_3,
        'piso_67':       piso_67,
        'aplica':        aplica,
        'valor_aplica':  valor_aplica,
        'label_aplica':  label_aplica,
        'detalle_ipc':   r_ipc,
        'detalle_tp':    r_tp,
    }


# ─────────────────────────────────────────────
# MOTOR 4 — MÉTODO BCRA (CER diario + 3% compuesto)
# ─────────────────────────────────────────────

def calcular_bcra(monto, fecha_origen, fecha_calculo, datos_cer_xls):
    """
    Réplica de la calculadora oficial del BCRA.
    CER diario + 3% anual compuesto.
    """
    cer_origen  = _get_diario(datos_cer_xls, fecha_origen)
    cer_calculo = _get_diario(datos_cer_xls, fecha_calculo)
    ult_fecha, ult_valor = _ultimo(datos_cer_xls)

    coef             = cer_calculo / cer_origen if cer_origen > 0 else 1.0
    capital_indexado = float(redondear(Decimal(str(monto)) * Decimal(str(coef))))
    dias             = (fecha_calculo - fecha_origen).days
    factor           = (1.03 ** (dias / 365)) - 1
    interes_3        = float(redondear(Decimal(str(capital_indexado)) * Decimal(str(factor))))
    total            = float(redondear(Decimal(str(capital_indexado)) + Decimal(str(interes_3))))
    art55_piso       = float(redondear(Decimal(str(total)) * Decimal('0.67')))

    return {
        'cer_origen':       cer_origen,
        'cer_origen_fecha': fecha_origen,
        'cer_calculo':      cer_calculo,
        'cer_calculo_fecha': fecha_calculo,
        'cer_ultimo_fecha': ult_fecha,
        'cer_ultimo_valor': ult_valor,
        'coef':             coef,
        'pct_variacion':    (coef - 1) * 100,
        'capital_indexado': capital_indexado,
        'dias':             dias,
        'interes_3':        interes_3,
        'total':            total,
        'art55_piso':       art55_piso,
    }


# ─────────────────────────────────────────────
# MOTOR 4b — CER DIARIO + 3% SIMPLE (autónomo)
# ─────────────────────────────────────────────

def calcular_cer_simple(monto, fecha_origen, fecha_calculo, datos_cer_xls):
    """CER diario + 3% simple. Mismo índice que método BCRA pero interés simple."""
    cer_origen  = _get_diario(datos_cer_xls, fecha_origen)
    cer_calculo = _get_diario(datos_cer_xls, fecha_calculo)
    ult_fecha, ult_valor = _ultimo(datos_cer_xls)
    coef             = cer_calculo / cer_origen if cer_origen > 0 else 1.0
    capital_indexado = float(redondear(Decimal(str(monto)) * Decimal(str(coef))))
    dias             = (fecha_calculo - fecha_origen).days
    interes_3        = float(redondear(
        Decimal(str(capital_indexado)) * Decimal("0.03") * Decimal(str(dias)) / Decimal("365")
    ))
    total      = float(redondear(Decimal(str(capital_indexado)) + Decimal(str(interes_3))))
    art55_piso = float(redondear(Decimal(str(total)) * Decimal("0.67")))
    return {
        "cer_origen":       cer_origen,
        "cer_origen_fecha": fecha_origen,
        "cer_calculo":      cer_calculo,
        "cer_calculo_fecha": fecha_calculo,
        "cer_ultimo_fecha": ult_fecha,
        "cer_ultimo_valor": ult_valor,
        "coef":             coef,
        "pct_variacion":    (coef - 1) * 100,
        "capital_indexado": capital_indexado,
        "dias":             dias,
        "interes_3":        interes_3,
        "total":            total,
        "art55_piso":       art55_piso,
    }


# ─────────────────────────────────────────────
# TASA ACTIVA BNA (para LRT — comparativa)
# ─────────────────────────────────────────────

def calcular_tasa_activa(monto, fecha_origen, fecha_calculo, df_tasa):
    """Tasa activa BNA mensual acumulada (interés simple, proporcional a días del mes)."""
    import calendar as _cal
    total_pct = 0.0
    for _, row in df_tasa.iterrows():
        f_desde = row['Desde'].date() if isinstance(row['Desde'], pd.Timestamp) else row['Desde']
        f_hasta = row['Hasta'].date()  if isinstance(row['Hasta'],  pd.Timestamp) else row['Hasta']
        ini = max(fecha_origen,  f_desde)
        fin = min(fecha_calculo, f_hasta)
        if ini <= fin:
            dias_mes    = _cal.monthrange(f_desde.year, f_desde.month)[1]
            dias_period = (fin - ini).days + 1
            total_pct  += float(row['Valor']) * dias_period / dias_mes
    total = float(redondear(Decimal(str(monto)) * (1 + Decimal(str(total_pct)) / 100)))
    return {'tasa_pct': total_pct, 'total': total}


# ─────────────────────────────────────────────
# CAPITALIZACIÓN DE INTERESES — ART. 770 INC. B CCyC
# ─────────────────────────────────────────────

def calcular_con_capitalizacion(monto, fecha_origen, fecha_demanda, fecha_calculo, datos, tipo='activa'):
    """
    Capitaliza intereses al momento de interposición de demanda (art. 770 inc. b CCyC).

    Tramo 1: fecha_origen → fecha_demanda, interés simple sobre el capital histórico.
    Capital capitalizado = capital histórico + interés del tramo 1.
    Tramo 2: fecha_demanda → fecha_calculo, interés simple sobre el capital capitalizado.

    tipo: 'activa' (requiere datos=df_tasa) o 'pasiva' (requiere datos=datos_tp).
    """
    if not (fecha_origen < fecha_demanda < fecha_calculo):
        raise ValueError("Las fechas deben cumplir: origen < demanda < cálculo")

    if tipo == 'activa':
        r1 = calcular_tasa_activa(monto, fecha_origen, fecha_demanda, datos)
        capital_capitalizado = r1['total']
        r2 = calcular_tasa_activa(capital_capitalizado, fecha_demanda, fecha_calculo, datos)
    elif tipo == 'pasiva':
        r1 = calcular_tasa_pasiva(monto, fecha_origen, fecha_demanda, datos)
        capital_capitalizado = r1['total']
        r2 = calcular_tasa_pasiva(capital_capitalizado, fecha_demanda, fecha_calculo, datos)
    else:
        raise ValueError("tipo debe ser 'activa' o 'pasiva'")

    return {
        'capital_historico':      monto,
        'tramo1':                 r1,
        'capital_capitalizado':   capital_capitalizado,
        'interes_tramo1':         capital_capitalizado - monto,
        'tramo2':                 r2,
        'total':                  r2['total'],
        'fecha_origen':           fecha_origen,
        'fecha_demanda':          fecha_demanda,
        'fecha_calculo':          fecha_calculo,
        'tipo':                   tipo,
    }


# ─────────────────────────────────────────────
# CARGA UNIFICADA
# ─────────────────────────────────────────────

def cargar_todo():
    """Carga todos los datasets. Para usar con @st.cache_data."""
    return {
        'df_ipc':       cargar_ipc(),
        'df_cer':       cargar_cer_csv(),
        'df_tasa':      cargar_tasa(),
        'df_ripte':     cargar_ripte(),
        'datos_cer_xls': cargar_cer_xls(),
        'datos_tp':     cargar_tasa_pasiva(),
    }