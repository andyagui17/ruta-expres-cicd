import shutil
from pathlib import Path
import pandas as pd

# Definición dinámica de la ruta base del proyecto
BASE_DIR = Path(__file__).parent.parent
BASE_DIR = BASE_DIR.resolve()

# Rutas a directorios y archivos
DATOS_DIR = BASE_DIR / "datos"
ARCHIVO_ORIGEN = DATOS_DIR / "pedidos_ruta_express.csv"

ARCHIVO_REFERENCIA = DATOS_DIR / "referencia.csv"
ARCHIVO_CONTROL = DATOS_DIR / "control.csv"
ARCHIVO_EXPANSION = DATOS_DIR / "expansion.csv"
ARCHIVO_ACTUAL = DATOS_DIR / "actual.csv"


def preparar_datos():
    # Asegurar que el directorio de datos existe
    DATOS_DIR.mkdir(parents=True, exist_ok=True)

    # Verificar que el archivo de entrada existe
    if not ARCHIVO_ORIGEN.exists():
        raise FileNotFoundError(f"No se encontró el archivo de origen: {ARCHIVO_ORIGEN}")

    # Leer el dataset original
    df = pd.read_csv(ARCHIVO_ORIGEN)

    # 1. Filtrar filas donde 'lote' es exactamente 'base' -> referencia.csv
    df_referencia = df[df["lote"] == "base"]
    df_referencia.to_csv(ARCHIVO_REFERENCIA, index=False)
    print(f"Archivo generado: {ARCHIVO_REFERENCIA.name} ({len(df_referencia)} filas)")

    # 2. Filtrar filas con 'lote' igual a 'control' -> control.csv
    df_control = df[df["lote"] == "control"]
    df_control.to_csv(ARCHIVO_CONTROL, index=False)
    print(f"Archivo generado: {ARCHIVO_CONTROL.name} ({len(df_control)} filas)")

    # 3. Filtrar filas con 'lote' igual a 'expansion' -> expansion.csv
    df_expansion = df[df["lote"] == "expansion"]
    df_expansion.to_csv(ARCHIVO_EXPANSION, index=False)
    print(f"Archivo generado: {ARCHIVO_EXPANSION.name} ({len(df_expansion)} filas)")

    # 4. Copia exacta de datos/control.csv guardada como datos/actual.csv
    shutil.copyfile(ARCHIVO_CONTROL, ARCHIVO_ACTUAL)
    print(f"Copia exacta creada: {ARCHIVO_ACTUAL} desde {ARCHIVO_CONTROL.name}")


if __name__ == "__main__":
    preparar_datos()
