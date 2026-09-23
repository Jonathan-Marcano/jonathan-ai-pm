"""OCR y extracción de texto de PDF local (Fase 3, CF3-04).

Usa `pymupdf` para extraer el texto embebido y, ante páginas sin texto
(escaneadas), rasteriza y aplica OCR con Tesseract. Todo es local y gratuito;
si Tesseract no está instalado, las páginas escaneadas levantan un error
controlado en lugar de depender de un proveedor remoto.
"""

from __future__ import annotations

import importlib.util
import shutil

from cuentafaro.importing.contract import ImportFormatError
from cuentafaro.importing.extract import ExtractedTable


def ocr_available() -> bool:
    """¿Está disponible Tesseract (binario + wrapper pytesseract)?"""
    return (
        shutil.which("tesseract") is not None
        and importlib.util.find_spec("pytesseract") is not None
    )


def extract_image_text(image_path: str) -> str:
    """OCR local de una imagen (Fase 4, CF4-04). Reutiliza Tesseract."""
    if not ocr_available():
        raise ImportFormatError(
            "no se puede hacer OCR de la imagen y Tesseract no está disponible "
            "localmente (instale `tesseract-ocr`); revise la captura a mano"
        )
    try:
        import pytesseract
        from PIL import Image
    except ImportError as error:  # pragma: no cover - dependencia declarada
        raise ImportFormatError("no se pudo cargar el lector de imágenes local") from error

    try:
        with Image.open(image_path) as image:
            return (pytesseract.image_to_string(image) or "").strip()
    except Exception as error:
        raise ImportFormatError(f"no se pudo leer la imagen para OCR: {error}") from error


def extract_pdf_text(content: bytes) -> str:
    """Devuelve el texto plano de un PDF (texto embebido u OCR local)."""
    try:
        import pymupdf
    except ImportError as error:  # pragma: no cover - dependencia declarada
        raise ImportFormatError("no se pudo cargar el lector de PDF local") from error

    try:
        document = pymupdf.open(stream=content, filetype="pdf")
    except Exception as error:
        raise ImportFormatError(f"no se pudo abrir el PDF: {error}") from error

    parts: list[str] = []
    try:
        for page in document:
            text = (page.get_text() or "").strip()
            if text:
                parts.append(text)
                continue
            parts.append(_ocr_page(page))
    finally:
        document.close()

    text = "\n".join(part.strip() for part in parts if part.strip())
    if not text.strip():
        raise ImportFormatError("no se pudo extraer texto del PDF")
    return text


def _ocr_page(page) -> str:
    if not ocr_available():
        raise ImportFormatError(
            "el PDF parece estar escaneado y Tesseract no está disponible localmente "
            "(instale `tesseract-ocr`)"
        )
    import io

    import pytesseract
    from PIL import Image

    pixmap = page.get_pixmap(dpi=200)
    image = Image.open(io.BytesIO(pixmap.tobytes("png")))
    return (pytesseract.image_to_string(image) or "").strip()


def _split_pdf_line(line: str) -> list[str]:
    cells = [cell.strip() for cell in line.split("  ") if cell.strip()]
    if len(cells) < 2:
        cells = line.split()
    return cells


def extract_pdf_text_as_rows(content: bytes) -> list[list[str]]:
    """Convierte el texto extraído en filas: cada línea es una fila de celdas."""
    text = extract_pdf_text(content)
    rows: list[list[str]] = []
    for line in text.splitlines():
        cells = _split_pdf_line(line)
        if cells:
            rows.append(cells)
    return rows


def pdf_rows_to_table(rows: list[list[str]]) -> ExtractedTable:
    """Construye una `ExtractedTable` con columnas `columna_N` (CF3-04/CF2-01)."""
    width = max((len(row) for row in rows), default=0)
    headers = [f"columna_{index + 1}" for index in range(width)]
    data: list[dict[str, str]] = []
    for row in rows:
        values: dict[str, str] = {
            f"columna_{column_index + 1}": cell for column_index, cell in enumerate(row)
        }
        if any(values.values()):
            data.append(values)
    return ExtractedTable(
        headers=headers,
        rows=data,
        first_row_number=1,
        separator=" ",
    )
