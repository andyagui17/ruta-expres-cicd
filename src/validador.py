"""
src/validador.py - Validación de integridad de datos para pipeline CI/CD.

Aplica reglas vectorizadas sobre los datasets sin iterar por filas (evitando bucles for):
1. Exactamente 7 columnas: pedido_id, fecha_lote, lote, zona, distancia_km, entrega_min, importe_bs.
2. pedido_id no vacío y único.
3. fecha_lote con formato AAAA-MM-DD.
4. zona con valores permitidos: 'centro' o 'periferia'.
5. Un solo valor único en 'lote' y en 'fecha_lote'.
6. Si el archivo es 'referencia.csv', lote debe ser 'base'. Si es 'actual.csv', 'control' o 'expansion'.
7. distancia_km, entrega_min e importe_bs deben ser números finitos mayores a cero (usa .isna(), > 0 y numpy.isfinite()).
"""

import io
from pathlib import Path
from typing import Union
import numpy as np
import pandas as pd

COLUMNAS_ESPERADAS = [
    "pedido_id",
    "fecha_lote",
    "lote",
    "zona",
    "distancia_km",
    "entrega_min",
    "importe_bs",
]

COLUMNAS_NUMERICAS = ["distancia_km", "entrega_min", "importe_bs"]
ZONAS_PERMITIDAS = ["centro", "periferia"]


def validar_csv(
    origen: Union[str, Path, pd.DataFrame, io.StringIO, io.TextIOBase],
    nombre_archivo: str | None = None,
) -> pd.DataFrame:
    """
    Lee y valida un dataset en formato CSV aplicando reglas estrictas y vectorizadas.

    Args:
        origen: Ruta al archivo CSV, DataFrame o flujo en memoria (StringIO) a validar.
        nombre_archivo: Nombre descriptivo opcional para mensajes de error.

    Returns:
        pd.DataFrame con los datos validados.

    Raises:
        ValueError: Si alguna regla de validación falla.
        FileNotFoundError: Si la ruta especificada no existe.
    """
    if isinstance(origen, pd.DataFrame):
        df = origen.copy()
        nombre = nombre_archivo or "dataframe"
    elif isinstance(origen, (io.StringIO, io.TextIOBase)):
        df = pd.read_csv(origen)
        nombre = nombre_archivo or "stream.csv"
    else:
        ruta = Path(origen)
        if not ruta.exists():
            raise FileNotFoundError(f"No se encontró el archivo a validar: {ruta}")
        df = pd.read_csv(ruta)
        nombre = nombre_archivo or ruta.name

    nombre_lower = Path(nombre).name.lower()

    # 1. Verificar que el archivo tenga exactamente las 7 columnas requeridas
    if list(df.columns) != COLUMNAS_ESPERADAS:
        raise ValueError(
            f"Error de validación en archivo '{nombre}', columnas: "
            f"Se esperaban exactamente {len(COLUMNAS_ESPERADAS)} columnas {COLUMNAS_ESPERADAS}, "
            f"pero se encontraron {len(df.columns)} columnas: {list(df.columns)}."
        )

    # 2. pedido_id no debe estar vacío y debe ser único en todo el archivo
    # Verificación de valores vacíos o nulos (vectorizada)
    vacios_id = df["pedido_id"].isna() | (df["pedido_id"].astype(str).str.strip() == "")
    if vacios_id.any():
        idx = df.index[vacios_id][0]
        num_fila = idx + 2
        raise ValueError(
            f"Error de validación en archivo '{nombre}', fila {num_fila}, "
            f"columna 'pedido_id': El identificador de pedido no debe estar vacío ni ser nulo."
        )

    # Verificación de unicidad (vectorizada)
    duplicados_id = df["pedido_id"].duplicated()
    if duplicados_id.any():
        idx = df.index[duplicados_id][0]
        num_fila = idx + 2
        pedido = df.loc[idx, "pedido_id"]
        raise ValueError(
            f"Error de validación en archivo '{nombre}', fila {num_fila} (pedido_id: '{pedido}'), "
            f"columna 'pedido_id': El identificador está duplicado en el archivo."
        )

    # 3. fecha_lote debe tener formato AAAA-MM-DD
    formato_regex = df["fecha_lote"].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$").fillna(False)
    fecha_dt = pd.to_datetime(df["fecha_lote"], format="%Y-%m-%d", errors="coerce")
    fechas_validas = formato_regex & (~fecha_dt.isna())
    fechas_invalidas = ~fechas_validas

    if fechas_invalidas.any():
        idx = df.index[fechas_invalidas][0]
        num_fila = idx + 2
        pedido = df.loc[idx, "pedido_id"]
        valor_fecha = df.loc[idx, "fecha_lote"]
        raise ValueError(
            f"Error de validación en archivo '{nombre}', fila {num_fila} (pedido_id: '{pedido}'), "
            f"columna 'fecha_lote': La fecha debe tener formato AAAA-MM-DD válido, pero se encontró '{valor_fecha}'."
        )

    # 4. zona solo puede contener los valores 'centro' o 'periferia'
    zonas_invalidas = ~df["zona"].astype(str).str.strip().isin(ZONAS_PERMITIDAS)
    if zonas_invalidas.any():
        idx = df.index[zonas_invalidas][0]
        num_fila = idx + 2
        pedido = df.loc[idx, "pedido_id"]
        valor_zona = df.loc[idx, "zona"]
        raise ValueError(
            f"Error de validación en archivo '{nombre}', fila {num_fila} (pedido_id: '{pedido}'), "
            f"columna 'zona': Solo se permiten los valores {ZONAS_PERMITIDAS}, pero se encontró '{valor_zona}'."
        )

    # 5. El archivo debe contener un solo valor único en la columna lote y en fecha_lote
    if df["lote"].nunique(dropna=False) != 1:
        valores_lote = df["lote"].unique().tolist()
        raise ValueError(
            f"Error de validación en archivo '{nombre}', columna 'lote': "
            f"El archivo debe contener un solo valor único en la columna 'lote', pero se encontraron {len(valores_lote)}: {valores_lote}."
        )

    if df["fecha_lote"].nunique(dropna=False) != 1:
        valores_fecha = df["fecha_lote"].unique().tolist()
        raise ValueError(
            f"Error de validación en archivo '{nombre}', columna 'fecha_lote': "
            f"El archivo debe contener un solo valor único en la columna 'fecha_lote', pero se encontraron {len(valores_fecha)}: {valores_fecha}."
        )

    # 6. Si el archivo es 'referencia.csv', la columna lote debe ser 'base'.
    #    Si es 'actual.csv', debe ser 'control' o 'expansion'.
    if nombre_lower == "referencia.csv":
        lote_ref_invalido = df["lote"] != "base"
        if lote_ref_invalido.any():
            idx = df.index[lote_ref_invalido][0]
            num_fila = idx + 2
            pedido = df.loc[idx, "pedido_id"]
            valor_lote = df.loc[idx, "lote"]
            raise ValueError(
                f"Error de validación en archivo '{nombre}', fila {num_fila} (pedido_id: '{pedido}'), "
                f"columna 'lote': Para 'referencia.csv' la columna lote debe ser exactamente 'base', pero se encontró '{valor_lote}'."
            )
    elif nombre_lower == "actual.csv":
        lote_act_invalido = ~df["lote"].isin(["control", "expansion"])
        if lote_act_invalido.any():
            idx = df.index[lote_act_invalido][0]
            num_fila = idx + 2
            pedido = df.loc[idx, "pedido_id"]
            valor_lote = df.loc[idx, "lote"]
            raise ValueError(
                f"Error de validación en archivo '{nombre}', fila {num_fila} (pedido_id: '{pedido}'), "
                f"columna 'lote': Para 'actual.csv' la columna lote debe ser 'control' o 'expansion', pero se encontró '{valor_lote}'."
            )

    # 7. Las columnas distancia_km, entrega_min e importe_bs deben ser números finitos mayores a cero.
    #    Usa .isna(), > 0 y numpy.isfinite().
    for col in COLUMNAS_NUMERICAS:
        serie_num = pd.to_numeric(df[col], errors="coerce")
        # Reglas vectorizadas usando explícitamente .isna(), np.isfinite() y > 0
        invalido = serie_num.isna() | (~np.isfinite(serie_num)) | ~(serie_num > 0)
        if invalido.any():
            idx = df.index[invalido][0]
            num_fila = idx + 2
            pedido = df.loc[idx, "pedido_id"]
            valor_original = df.loc[idx, col]
            raise ValueError(
                f"Error de validación en archivo '{nombre}', fila {num_fila} (pedido_id: '{pedido}'), "
                f"columna '{col}': El valor debe ser un número finito mayor a cero (> 0), pero se encontró '{valor_original}'."
            )

    return df


# Alias de conveniencia
validar_datos = validar_csv
validar_archivo = validar_csv


if __name__ == "__main__":
    # Rutas dinámicas relativas a este archivo
    BASE_DIR = Path(__file__).parent.parent
    BASE_DIR = BASE_DIR.resolve()

    DATOS_DIR = BASE_DIR / "datos"
    ARCHIVO_REFERENCIA = DATOS_DIR / "referencia.csv"
    ARCHIVO_ACTUAL = DATOS_DIR / "actual.csv"

    print("=" * 60)
    print("Iniciando validación de calidad de datos para CI/CD")
    print("=" * 60)

    # Validar datos/referencia.csv
    print(f"Validando: {ARCHIVO_REFERENCIA.name}...")
    validar_csv(ARCHIVO_REFERENCIA)
    print(f"[OK] {ARCHIVO_REFERENCIA.name} validado exitosamente.")

    # Validar datos/actual.csv
    print(f"Validando: {ARCHIVO_ACTUAL.name}...")
    validar_csv(ARCHIVO_ACTUAL)
    print(f"[OK] {ARCHIVO_ACTUAL.name} validado exitosamente.")

    print("=" * 60)
    print("Todas las validaciones completadas sin errores.")
    print("=" * 60)
