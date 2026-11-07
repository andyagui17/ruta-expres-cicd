import pandas as pd
from pandas.api.types import infer_dtype
import pandas.core.dtypes.common

# Monkey Patch: Engañamos a Evidently inyectando la función moderna de Pandas 
# en la ruta antigua que Evidently espera encontrar.
pandas.core.dtypes.common.infer_dtype_from_object = infer_dtype

# A partir de aquí, puedes dejar el resto de tus imports originales:
from evidently import DataDefinition, Dataset, Report
from pathlib import Path
# ... (resto de tu código)
"""
src/generar_informe.py - Generación de informes de calidad y deriva de datos.

Compara datos/referencia.csv y datos/actual.csv usando evidently con DataDriftPreset.
Genera:
  - public/comparacion.html: Informe interactivo de Data Drift de Evidently.
  - public/index.html: Portada estructurada con métricas de lotes, zonas, commit y enlace.
"""

from datetime import datetime, timezone
import html
import os
from pathlib import Path
import pandas as pd

# Rutas dinámicas relativas al proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
DATOS_DIR = BASE_DIR / "datos"
PUBLIC_DIR = BASE_DIR / "public"

ARCHIVO_REFERENCIA = DATOS_DIR / "referencia.csv"
ARCHIVO_ACTUAL = DATOS_DIR / "actual.csv"
ARCHIVO_COMPARACION = PUBLIC_DIR / "comparacion.html"
ARCHIVO_INDEX = PUBLIC_DIR / "index.html"

# Definición de variables del dataset
COLUMNAS_NUMERICAS = ["distancia_km", "entrega_min", "importe_bs"]
COLUMNAS_CONTEXTO = ["zona"]
COLUMNAS_RASTREO = ["pedido_id", "fecha_lote", "lote"]

# Importación compatible con múltiples versiones de Evidently
try:
    from evidently import DataDefinition, Dataset, Report
    from evidently.presets import DataDriftPreset
    _EVIDENTLY_MODERNO = True
except ImportError:
    from evidently.report import Report
    from evidently.metric_preset import DataDriftPreset
    from evidently.pipeline.column_mapping import ColumnMapping
    _EVIDENTLY_MODERNO = False


def ejecutar_data_drift(df_ref: pd.DataFrame, df_act: pd.DataFrame, ruta_salida: Path) -> None:
    """
    Ejecuta el DataDriftPreset de evidently comparando datos de referencia y actuales.
    Compara numéricamente distancia_km, entrega_min e importe_bs,
    utiliza zona como contexto y conserva pedido_id, fecha_lote y lote para rastreo.
    """
    if _EVIDENTLY_MODERNO:
        esquema = DataDefinition(
            numerical_columns=COLUMNAS_NUMERICAS,
            categorical_columns=COLUMNAS_CONTEXTO,
            id_column="pedido_id",
        )
        ds_ref = Dataset.from_pandas(df_ref, data_definition=esquema)
        ds_act = Dataset.from_pandas(df_act, data_definition=esquema)

        reporte = Report([DataDriftPreset()])
        resultado = reporte.run(current_data=ds_act, reference_data=ds_ref)

        if hasattr(resultado, "save_html"):
            resultado.save_html(str(ruta_salida))
        else:
            reporte.save_html(str(ruta_salida))
    else:
        mapeo_columnas = ColumnMapping(
            numerical_features=COLUMNAS_NUMERICAS,
            categorical_features=COLUMNAS_CONTEXTO,
            id="pedido_id",
        )
        reporte = Report(metrics=[DataDriftPreset()])
        reporte.run(
            reference_data=df_ref,
            current_data=df_act,
            column_mapping=mapeo_columnas,
        )
        reporte.save_html(str(ruta_salida))


def _construir_seccion_meta(github_sha: str, fecha_utc: str) -> str:
    """Genera la sección HTML con metadatos del commit y fecha de ejecución."""
    items = [
        f"<li><strong>Commit (GITHUB_SHA):</strong> <code>{html.escape(github_sha)}</code></li>",
        f"<li><strong>Fecha de ejecución:</strong> {html.escape(fecha_utc)} (UTC)</li>",
        '<li><strong>Reporte de Deriva:</strong> <a href="comparacion.html">Ver reporte Evidently (DataDriftPreset)</a></li>',
    ]
    return f"""
    <section class="card">
        <h2>Metadatos de Ejecución (CI/CD)</h2>
        <ul>
            {"".join(items)}
        </ul>
    </section>
    """


def _construir_tabla_lotes(
    lote_ref: str, fecha_ref: str, total_ref: int,
    lote_act: str, fecha_act: str, total_act: int,
) -> str:
    """Genera la tabla HTML con los nombres de lotes, fechas y total de filas."""
    filas = [
        f"<tr><td>Referencia</td><td><code>{html.escape(lote_ref)}</code></td>"
        f"<td>{html.escape(fecha_ref)}</td><td>{total_ref:,}</td></tr>",
        f"<tr><td>Actual</td><td><code>{html.escape(lote_act)}</code></td>"
        f"<td>{html.escape(fecha_act)}</td><td>{total_act:,}</td></tr>",
    ]
    return f"""
    <section>
        <h2>Resumen de Grupos y Lotes</h2>
        <table>
            <thead>
                <tr>
                    <th>Grupo</th>
                    <th>Nombre de Lote</th>
                    <th>Fecha de Lote</th>
                    <th>Cantidad de Filas</th>
                </tr>
            </thead>
            <tbody>
                {"".join(filas)}
            </tbody>
        </table>
    </section>
    """


def _construir_tabla_zonas(
    zonas_ref: dict[str, int],
    zonas_act: dict[str, int],
    total_ref: int,
    total_act: int,
) -> str:
    """Genera la tabla HTML con el conteo de pedidos por zona (centro/periferia)."""
    todas_zonas = sorted(set(zonas_ref.keys()) | set(zonas_act.keys()))
    filas_zonas = []
    for z in todas_zonas:
        c_ref = zonas_ref.get(z, 0)
        c_act = zonas_act.get(z, 0)
        filas_zonas.append(
            f"<tr><td>{html.escape(z.capitalize())}</td><td>{c_ref:,}</td><td>{c_act:,}</td></tr>"
        )

    return f"""
    <section>
        <h2>Conteo de Pedidos por Zona</h2>
        <table>
            <thead>
                <tr>
                    <th>Zona</th>
                    <th>Pedidos en Referencia</th>
                    <th>Pedidos en Actual</th>
                </tr>
            </thead>
            <tbody>
                {"".join(filas_zonas)}
                <tr class="total-row">
                    <td><strong>Total</strong></td>
                    <td><strong>{total_ref:,}</strong></td>
                    <td><strong>{total_act:,}</strong></td>
                </tr>
            </tbody>
        </table>
    </section>
    """


def _construir_seccion_variables() -> str:
    """Genera la sección informativa de las variables numéricas comparadas."""
    vars_list = [
        "<li><code>distancia_km</code>: Distancia del trayecto en kilómetros.</li>",
        "<li><code>entrega_min</code>: Tiempo de entrega del pedido en minutos.</li>",
        "<li><code>importe_bs</code>: Importe total de la compra en Bolivianos (Bs).</li>",
    ]
    return f"""
    <section>
        <h2>Variables Numéricas Analizadas</h2>
        <p>Se ejecutó el preset <code>DataDriftPreset</code> sobre las siguientes variables continuas:</p>
        <ul>
            {"".join(vars_list)}
        </ul>
        <p>Variables contextuales y de rastreo: <code>zona</code> (contexto), <code>pedido_id</code>, <code>fecha_lote</code>, <code>lote</code>.</p>
    </section>
    """


def construir_portada_html(info: dict) -> str:
    """
    Construye el documento HTML completo y válido para public/index.html
    estructurado por componentes semánticos sin un único f-string masivo.
    """
    seccion_meta = _construir_seccion_meta(info["github_sha"], info["fecha_utc"])
    seccion_lotes = _construir_tabla_lotes(
        info["lote_ref"], info["fecha_ref"], info["total_ref"],
        info["lote_act"], info["fecha_act"], info["total_act"],
    )
    seccion_zonas = _construir_tabla_zonas(
        info["zonas_ref"], info["zonas_act"],
        info["total_ref"], info["total_act"],
    )
    seccion_vars = _construir_seccion_variables()

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monitoreo de Calidad y Deriva - Ruta Express</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            max-width: 960px;
            margin: 40px auto;
            padding: 0 24px;
            color: #1f2328;
            line-height: 1.6;
        }}
        h1 {{
            color: #0969da;
            border-bottom: 2px solid #d0d7de;
            padding-bottom: 12px;
        }}
        h2 {{
            color: #1f2328;
            margin-top: 28px;
        }}
        .card {{
            background-color: #f6f8fa;
            border: 1px solid #d0d7de;
            border-radius: 8px;
            padding: 16px 20px;
            margin-top: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 14px;
            margin-bottom: 24px;
        }}
        th, td {{
            padding: 10px 14px;
            border: 1px solid #d0d7de;
            text-align: left;
        }}
        th {{
            background-color: #eaeef2;
            font-weight: 600;
        }}
        .total-row {{
            background-color: #f6f8fa;
            font-weight: bold;
        }}
        code {{
            background-color: #eff1f3;
            padding: 3px 6px;
            border-radius: 4px;
            font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
            font-size: 0.9em;
        }}
        .cta-container {{
            margin: 30px 0;
            text-align: center;
        }}
        .btn {{
            display: inline-block;
            background-color: #1f883d;
            color: #ffffff;
            text-decoration: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 1.05em;
            transition: background-color 0.2s ease;
        }}
        .btn:hover {{
            background-color: #1a7f37;
        }}
        a {{
            color: #0969da;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <header>
        <h1>Monitoreo de Calidad y Deriva de Datos - Ruta Express</h1>
        <p>Pipeline automatizado de monitoreo continuo de datos con Evidently AI y GitHub Actions.</p>
    </header>

    <main>
        {seccion_meta}
        {seccion_lotes}
        {seccion_zonas}
        {seccion_vars}

        <div class="cta-container">
            <a class="btn" href="comparacion.html">Explorar Informe Interactivo de Data Drift &rarr;</a>
        </div>
    </main>

    <footer>
        <hr style="border: 0; border-top: 1px solid #d0d7de; margin-top: 40px;">
        <p><small>&copy; Ruta Express - Monitoreo CI/CD continuo de deriva de datos.</small></p>
    </footer>
</body>
</html>"""


def generar_informe() -> None:
    """
    Función principal que coordina la lectura de CSVs, ejecución de Evidently
    y generación de la portada index.html.
    """
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    if not ARCHIVO_REFERENCIA.exists():
        raise FileNotFoundError(f"No existe el archivo de referencia: {ARCHIVO_REFERENCIA}")
    if not ARCHIVO_ACTUAL.exists():
        raise FileNotFoundError(f"No existe el archivo actual: {ARCHIVO_ACTUAL}")

    df_ref = pd.read_csv(ARCHIVO_REFERENCIA)
    df_act = pd.read_csv(ARCHIVO_ACTUAL)

    # 1. Ejecutar análisis de Data Drift y guardar comparacion.html
    print("Ejecutando Evidently DataDriftPreset...")
    ejecutar_data_drift(df_ref, df_act, ARCHIVO_COMPARACION)
    print(f"Informe de comparacion guardado en: {ARCHIVO_COMPARACION}")

    # 2. Extraer estadísticas para la portada
    info = {
        "github_sha": os.getenv("GITHUB_SHA", "local-run"),
        "fecha_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "lote_ref": str(df_ref["lote"].iloc[0]) if len(df_ref) > 0 else "N/A",
        "fecha_ref": str(df_ref["fecha_lote"].iloc[0]) if len(df_ref) > 0 else "N/A",
        "total_ref": len(df_ref),
        "lote_act": str(df_act["lote"].iloc[0]) if len(df_act) > 0 else "N/A",
        "fecha_act": str(df_act["fecha_lote"].iloc[0]) if len(df_act) > 0 else "N/A",
        "total_act": len(df_act),
        "zonas_ref": df_ref["zona"].value_counts().to_dict(),
        "zonas_act": df_act["zona"].value_counts().to_dict(),
    }

    # 3. Generar y guardar portada public/index.html
    html_contenido = construir_portada_html(info)
    ARCHIVO_INDEX.write_text(html_contenido, encoding="utf-8")
    print(f"Portada index.html generada exitosamente en: {ARCHIVO_INDEX}")


if __name__ == "__main__":
    generar_informe()
