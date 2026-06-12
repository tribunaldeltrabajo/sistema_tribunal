#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
INFO DATASETS — Visor de últimos datos disponibles
"""

import streamlit as st
import pandas as pd
import xlrd
from datetime import date
import calendar as _cal
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR  = os.path.join(BASE_DIR, "data")

MESES = {1:'enero',2:'febrero',3:'marzo',4:'abril',5:'mayo',6:'junio',
         7:'julio',8:'agosto',9:'septiembre',10:'octubre',11:'noviembre',12:'diciembre'}

def _mes_letras(fecha):
    if isinstance(fecha, pd.Timestamp):
        return f"{fecha.day} de {MESES[fecha.month]} {fecha.year}"
    return str(fecha)

def _mes_anio(mes, anio):
    return f"{MESES[mes].capitalize()} {anio}"


def mostrar_ultimos_datos():
    mostrar_ultimos_datos_universal()


def mostrar_ultimos_datos_universal():
    try:
        tarjetas = []

        # ── IPC ──
        try:
            df_ipc = pd.read_csv(os.path.join(DATA_DIR, "dataset_ipc.csv"))
            df_ipc.columns = df_ipc.columns.str.strip().str.lower()
            df_ipc['periodo'] = pd.to_datetime(df_ipc['periodo'])
            df_ipc = df_ipc.sort_values('periodo')
            ult = df_ipc.iloc[-1]
            mes = ult['periodo'].month; anio = ult['periodo'].year
            tarjetas.append({
                'icon': '📈', 'titulo': 'IPC',
                'valor': f"{float(ult['indice']):,.2f}".replace(',','X').replace('.',',').replace('X','.'),
                'subtitulo': _mes_anio(mes, anio),
            })
        except: pass

        # ── RIPTE ──
        try:
            df_r = pd.read_csv(os.path.join(DATA_DIR, "dataset_ripte.csv"))
            df_r.columns = df_r.columns.str.strip().str.lower()
            ult_r = df_r.iloc[0]
            val_ripte = None
            for col in ['monto_en_pesos','indice_ripte','ripte','valor','monto']:
                if col in df_r.columns:
                    val_ripte = float(ult_r[col]); break
            if val_ripte:
                mes_r = str(ult_r.get('mes',''))
                anio_r = str(ult_r.get('año', ult_r.get('anio','')))
                periodo_r = f"{mes_r} {anio_r}".strip()
                tarjetas.append({
                    'icon': '📊', 'titulo': 'RIPTE',
                    'valor': f"${val_ripte:,.0f}".replace(',','.'),
                    'subtitulo': periodo_r,
                })
        except: pass

        # ── Tasa Activa BNA ──
        try:
            df_ta = pd.read_csv(os.path.join(DATA_DIR, "tasas_activa_bna.csv"))
            df_ta.columns = df_ta.columns.str.strip().str.lower()
            df_ta['mes']  = df_ta['fecha'].str.split('/').str[0].astype(int)
            df_ta['anio'] = df_ta['fecha'].str.split('/').str[1].astype(int)
            df_ta = df_ta.sort_values(['anio','mes'])
            ult_ta = df_ta.iloc[-1]
            tarjetas.append({
                'icon': '💰', 'titulo': 'Tasa Activa BNA',
                'valor': f"{float(ult_ta['tasa_activa']):.2f}%".replace('.',','),
                'subtitulo': _mes_anio(int(ult_ta['mes']), int(ult_ta['anio'])),
            })
        except: pass

        # ── JUS ──
        try:
            df_jus = pd.read_csv(os.path.join(DATA_DIR, "Dataset_JUS.csv"))
            df_jus.columns = [c.strip() for c in df_jus.columns]
            ult_j = df_jus.iloc[0]
            val_jus_str = str(ult_j['VALOR IUS']).replace('$','').replace('.','').replace(',','.').strip()
            val_jus = float(val_jus_str)
            acuerdo = str(ult_j.get('ACUERDO','')).strip()
            fecha_jus = str(ult_j.get('FECHA ENTRADA EN VIGENCIA','')).strip()
            tarjetas.append({
                'icon': '⚖️', 'titulo': 'JUS',
                'valor': f"${val_jus:,.2f}".replace(',','X').replace('.',',').replace('X','.'),
                'subtitulo': f"{acuerdo} · desde {fecha_jus}",
            })
        except: pass

        # ── Piso LRT ──
        try:
            df_p = pd.read_csv(os.path.join(DATA_DIR, "dataset_pisos.csv"))
            df_p.columns = df_p.columns.str.strip().str.lower()
            df_p['desde'] = pd.to_datetime(df_p['fecha_inicio'], dayfirst=True, errors='coerce')
            df_p = df_p.dropna(subset=['desde']).sort_values('desde', ascending=False)
            ult_p = df_p.iloc[0]
            monto_p = float(ult_p['monto_minimo'])
            norma_p = str(ult_p.get('norma','')).strip()
            fi = ult_p['desde'].strftime('%d/%m/%Y')
            ff_raw = str(ult_p.get('fecha_fin','')).strip()
            ff = pd.to_datetime(ff_raw, dayfirst=True, errors='coerce')
            rango = f"{fi} — {ff.strftime('%d/%m/%Y')}" if pd.notna(ff) else f"desde {fi}"
            tarjetas.append({
                'icon': '🛡️', 'titulo': 'Piso LRT',
                'valor': f"${monto_p:,.0f}".replace(',','.'),
                'subtitulo': f"{norma_p} · {rango}",
            })
        except: pass

        # ── Tasa Pasiva BCRA ──
        try:
            wb = xlrd.open_workbook(os.path.join(DATA_DIR, "diar_ind.xls"))
            sh = wb.sheet_by_name('Totales_diarios')
            last_fecha, last_val = None, None
            for r in range(27, sh.nrows):
                if sh.row_len(r) < 11: continue
                fv = sh.cell_value(r, 0); cv = sh.cell_value(r, 10)
                if isinstance(fv, str) and '/' in fv and isinstance(cv, float) and cv > 0:
                    try:
                        p = fv.strip().split('/')
                        d = date(int(p[2]), int(p[1]), int(p[0]))
                        last_fecha, last_val = d, cv
                    except: pass
            if last_fecha:
                tarjetas.append({
                    'icon': '📉', 'titulo': 'Tasa Pasiva BCRA',
                    'valor': f"{last_val:,.3f}".replace(',','X').replace('.',',').replace('X','.'),
                    'subtitulo': f"{last_fecha.day} de {MESES[last_fecha.month]} {last_fecha.year}",
                })
        except: pass

        # ── CER ──
        try:
            wb2 = xlrd.open_workbook(os.path.join(DATA_DIR, "diar_cer.xls"))
            sh2 = wb2.sheet_by_name('Totales_diarios')
            last_fc, last_vc = None, None
            for r in range(sh2.nrows):
                if sh2.row_len(r) < 2: continue
                fv = sh2.cell_value(r, 0); cv = sh2.cell_value(r, 1)
                if isinstance(fv, str) and '/' in fv and isinstance(cv, float):
                    try:
                        p = fv.strip().split('/')
                        d = date(int(p[2]), int(p[1]), int(p[0]))
                        last_fc, last_vc = d, cv
                    except: pass
            if last_fc:
                tarjetas.append({
                    'icon': '📐', 'titulo': 'CER',
                    'valor': f"{last_vc:,.4f}".replace(',','X').replace('.',',').replace('X','.'),
                    'subtitulo': f"{last_fc.day} de {MESES[last_fc.month]} {last_fc.year}",
                })
        except: pass

        if not tarjetas:
            return

        # ── Render ──
        cols_html = ""
        for t in tarjetas:
            cols_html += f"""
            <div style="background:#f0f2f6;border-radius:8px;padding:12px 14px;border:0.5px solid #d0d0d0;">
              <div style="font-size:11px;color:#666;margin-bottom:4px;">{t['icon']} {t['titulo']}</div>
              <div style="font-size:18px;font-weight:500;color:#111;">{t['valor']}</div>
              <div style="font-size:10px;color:#888;margin-top:4px;">{t['subtitulo']}</div>
            </div>"""

        st.caption("📊 Últimos datos disponibles en los datasets del sistema")
        st.markdown(
            f"<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:8px'>"
            f"{cols_html}</div>",
            unsafe_allow_html=True
        )

    except Exception as e:
        st.warning(f"⚠️ No se pudieron cargar los últimos datos: {str(e)}")