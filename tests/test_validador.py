"""
tests/test_validador.py - Pruebas unitarias para src/validador.py usando pytest.

Simula datasets pequeños en memoria con io.StringIO y pandas,
sin crear archivos físicos en disco.
"""

import io
import sys
from pathlib import Path
import pandas as pd
import pytest

# Asegurar que el directorio raíz del proyecto esté en sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.validador import validar_csv

# Encabezado CSV estándar
HEADER = "pedido_id,fecha_lote,lote,zona,distancia_km,entrega_min,importe_bs\n"


def test_caso_valido():
    """
    Test 1: Caso válido que cumple todas las reglas de calidad e integridad.
    """
    csv_en_memoria = io.StringIO(
        HEADER
        + "RE-0001,2026-10-05,base,centro,2.5,15.0,50.0\n"
        + "RE-0002,2026-10-05,base,periferia,4.2,25.0,80.0\n"
    )
    df = pd.read_csv(csv_en_memoria)

    # Validar el DataFrame simulando 'referencia.csv'
    df_validado = validar_csv(df, nombre_archivo="referencia.csv")

    assert df_validado is not None
    assert len(df_validado) == 2
    assert list(df_validado["pedido_id"]) == ["RE-0001", "RE-0002"]


def test_pedido_id_duplicado():
    """
    Test 2: Caso inválido donde existe un pedido_id duplicado.
    Debe levantar ValueError indicando el error en pedido_id.
    """
    csv_en_memoria = io.StringIO(
        HEADER
        + "RE-0001,2026-10-05,base,centro,2.5,15.0,50.0\n"
        + "RE-0001,2026-10-05,base,periferia,3.0,18.0,45.0\n"
    )
    df = pd.read_csv(csv_en_memoria)

    with pytest.raises(ValueError) as exc_info:
        validar_csv(df, nombre_archivo="referencia.csv")

    mensaje = str(exc_info.value)
    assert "pedido_id" in mensaje
    assert "duplicado" in mensaje.lower()


def test_entrega_min_negativo():
    """
    Test 3: Caso inválido donde entrega_min contiene un valor negativo.
    Debe levantar ValueError indicando que debe ser mayor a cero.
    """
    csv_en_memoria = io.StringIO(
        HEADER
        + "RE-0001,2026-10-05,base,centro,2.5,-12.0,50.0\n"
        + "RE-0002,2026-10-05,base,periferia,4.0,20.0,60.0\n"
    )
    df = pd.read_csv(csv_en_memoria)

    with pytest.raises(ValueError) as exc_info:
        validar_csv(df, nombre_archivo="referencia.csv")

    mensaje = str(exc_info.value)
    assert "entrega_min" in mensaje
    assert "mayor a cero" in mensaje.lower()


def test_zona_distinta_a_centro_o_periferia():
    """
    Test 4: Caso inválido donde la columna zona tiene un valor distinto a 'centro' o 'periferia'.
    Debe levantar ValueError especificando los valores permitidos para zona.
    """
    csv_en_memoria = io.StringIO(
        HEADER
        + "RE-0001,2026-10-05,base,rural,2.5,15.0,50.0\n"
        + "RE-0002,2026-10-05,base,centro,3.5,18.0,40.0\n"
    )
    df = pd.read_csv(csv_en_memoria)

    with pytest.raises(ValueError) as exc_info:
        validar_csv(df, nombre_archivo="referencia.csv")

    mensaje = str(exc_info.value)
    assert "zona" in mensaje
    assert "centro" in mensaje.lower() or "periferia" in mensaje.lower()


def test_caso_valido_actual_control_y_expansion():
    """
    Test adicional: Validar que actual.csv acepte tanto lote 'control' como 'expansion'.
    """
    # Lote control en actual.csv
    csv_control = io.StringIO(
        HEADER + "RE-0100,2026-10-06,control,centro,1.8,12.5,35.0\n"
    )
    df_control = pd.read_csv(csv_control)
    res_control = validar_csv(df_control, nombre_archivo="actual.csv")
    assert len(res_control) == 1

    # Lote expansion en actual.csv
    csv_exp = io.StringIO(
        HEADER + "RE-0200,2026-10-07,expansion,periferia,5.2,30.0,95.0\n"
    )
    df_exp = pd.read_csv(csv_exp)
    res_exp = validar_csv(df_exp, nombre_archivo="actual.csv")
    assert len(res_exp) == 1


def test_paso_directo_stringio():
    """
    Test adicional: Validar que validar_csv acepte directamente un objeto io.StringIO.
    """
    csv_stream = io.StringIO(
        HEADER + "RE-0001,2026-10-05,base,centro,2.5,15.0,50.0\n"
    )
    df_validado = validar_csv(csv_stream, nombre_archivo="referencia.csv")
    assert len(df_validado) == 1
