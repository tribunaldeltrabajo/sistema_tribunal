#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FUNCIONES COMUNES
Sistema de Cálculos y Herramientas - Tribunal de Trabajo 2 de Quilmes

Funciones compartidas entre todas las aplicaciones del sistema.
Consolidación realizada para evitar duplicación de código.
"""

import pandas as pd
import math
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


def safe_parse_date(s) -> Optional[date]:
    """
    Parsea una fecha desde diversos formatos a objeto date.
    
    Soporta múltiples formatos comunes: ISO, DD/MM/YYYY, MM/YYYY, etc.
    
    Args:
        s: String, datetime, date, o valor numérico representando fecha
        
    Returns:
        date object o None si no se puede parsear
        
    Ejemplos:
        >>> safe_parse_date("2024-12-01")
        date(2024, 12, 1)
        >>> safe_parse_date("01/12/2024")
        date(2024, 12, 1)
        >>> safe_parse_date("12/2024")
        date(2024, 12, 1)
    """
    if s is None or (isinstance(s, float) and math.isnan(s)):
        return None
    if isinstance(s, (datetime, date)):
        return s.date() if isinstance(s, datetime) else s
    s = str(s).strip()
    if not s:
        return None
    
    fmts = [
        "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%Y", "%Y/%m/%d", "%Y-%m",
        "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%B %Y", "%b %Y", 
        "%Y/%m", "%m-%Y",
    ]
    
    for f in fmts:
        try:
            dt = datetime.strptime(s, f)
            if f in ("%m/%Y", "%Y-%m", "%Y/%m", "%m-%Y", "%B %Y", "%b %Y"):
                return date(dt.year, dt.month, 1)
            return dt.date()
        except Exception:
            continue
    
    # Intentar parsear año-mes manualmente
    if "/" in s or "-" in s:
        parts = s.replace("/", "-").split("-")
        if len(parts) == 2:
            try:
                year, month = int(parts[0]), int(parts[1])
                if 1900 <= year <= 2100 and 1 <= month <= 12:
                    return date(year, month, 1)
            except ValueError:
                pass
    
    # Último intento con pandas
    try:
        dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
        if pd.isna(dt):
            return None
        if isinstance(dt, pd.Timestamp):
            return dt.date()
        return None
    except Exception:
        return None


def days_in_month(d: date) -> int:
    """
    Retorna la cantidad de días en el mes de una fecha dada.
    
    Args:
        d: Fecha de la cual obtener días del mes
        
    Returns:
        int: Cantidad de días (28-31)
        
    Ejemplos:
        >>> days_in_month(date(2024, 2, 15))
        29  # Febrero 2024 es bisiesto
        >>> days_in_month(date(2024, 12, 1))
        31
    """
    if d.month == 12:
        nxt = date(d.year + 1, 1, 1)
    else:
        nxt = date(d.year, d.month + 1, 1)
    return (nxt - date(d.year, d.month, 1)).days


def redondear(valor):
    """
    Redondea un valor a 2 decimales según criterio contable/judicial.
    
    Utiliza ROUND_HALF_UP (redondeo comercial): 0.5 redondea hacia arriba.
    
    Args:
        valor: Número a redondear (float, int, o Decimal)
        
    Returns:
        Decimal: Valor redondeado a 2 decimales
        
    Ejemplos:
        >>> redondear(10.125)
        Decimal('10.13')
        >>> redondear(10.124)
        Decimal('10.12')
    """
    if isinstance(valor, Decimal):
        return valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return Decimal(str(valor)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def formato_moneda(valor):
    """
    Formatea un valor numérico como moneda argentina.
    
    Formato: $ 1.234.567,89
    
    Args:
        valor: Número a formatear
        
    Returns:
        str: String formateado como pesos argentinos
        
    Ejemplos:
        >>> formato_moneda(1234567.89)
        '$ 1.234.567,89'
        >>> formato_moneda(100.5)
        '$ 100,50'
    """
    return f"$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def numero_a_letras(numero):
    """
    Convierte un número a su representación en letras (formato jurídico argentino).
    
    Args:
        numero: Número decimal a convertir
        
    Returns:
        str: Representación en letras (ej: "PESOS UN MIL DOSCIENTOS CON 50/100")
        
    Ejemplos:
        >>> numero_a_letras(1200.50)
        'PESOS UN MIL DOSCIENTOS CON 50/100'
        >>> numero_a_letras(0)
        'CERO PESOS'
    """
    unidades = ['', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE']
    decenas = ['', '', 'VEINTE', 'TREINTA', 'CUARENTA', 'CINCUENTA', 'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA']
    especiales = ['DIEZ', 'ONCE', 'DOCE', 'TRECE', 'CATORCE', 'QUINCE', 'DIECISÉIS', 'DIECISIETE', 'DIECIOCHO', 'DIECINUEVE']
    centenas = ['', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS', 'QUINIENTOS', 'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS', 'NOVECIENTOS']
    
    def convertir_grupo(n):
        """Convierte un grupo de hasta 3 dígitos a letras"""
        if n == 0:
            return ''
        elif n == 100:
            return 'CIEN'
        elif n < 10:
            return unidades[n]
        elif n < 20:
            return especiales[n - 10]
        elif n < 100:
            dec = n // 10
            uni = n % 10
            if uni == 0:
                return decenas[dec]
            else:
                return decenas[dec] + (' Y ' if dec > 2 else 'I') + unidades[uni]
        else:
            cen = n // 100
            resto = n % 100
            if resto == 0:
                return centenas[cen]
            else:
                return centenas[cen] + ' ' + convertir_grupo(resto)
    
    if numero == 0:
        return 'CERO PESOS'
    
    entero = int(numero)
    decimal = int(round((numero - entero) * 100))
    
    if entero >= 1000000000:
        miles_millon = entero // 1000000000
        resto = entero % 1000000000
        texto = convertir_grupo(miles_millon) + ' MIL'
        if resto >= 1000000:
            millones = resto // 1000000
            resto = resto % 1000000
            texto += ' ' + (convertir_grupo(millones) if millones > 1 else 'UN') + ' MILLÓN' + ('ES' if millones > 1 else '')
        if resto > 0:
            if resto >= 1000:
                miles = resto // 1000
                resto = resto % 1000
                texto += ' ' + convertir_grupo(miles) + ' MIL'
            if resto > 0:
                texto += ' ' + convertir_grupo(resto)
    elif entero >= 1000000:
        millones = entero // 1000000
        resto = entero % 1000000
        texto = (convertir_grupo(millones) if millones > 1 else 'UN') + ' MILLÓN' + ('ES' if millones > 1 else '')
        if resto > 0:
            if resto >= 1000:
                miles = resto // 1000
                resto = resto % 1000
                texto += ' ' + convertir_grupo(miles) + ' MIL'
            if resto > 0:
                texto += ' ' + convertir_grupo(resto)
    elif entero >= 1000:
        miles = entero // 1000
        resto = entero % 1000
        texto = convertir_grupo(miles) + ' MIL'
        if resto > 0:
            texto += ' ' + convertir_grupo(resto)
    else:
        texto = convertir_grupo(entero)
    
    return f'PESOS {texto} CON {decimal:02d}/100'


def get_mes_nombre(mes):
    """
    Retorna el nombre del mes en español.
    
    Args:
        mes: Número de mes (1-12)
        
    Returns:
        str: Nombre del mes en español
        
    Ejemplos:
        >>> get_mes_nombre(1)
        'Enero'
        >>> get_mes_nombre(12)
        'Diciembre'
    """
    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
             'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    return meses[mes - 1]
