"""Extracción de texto de un CV (PDF, DOCX o texto pegado).

Todo ocurre en memoria: el archivo subido nunca se escribe en disco ni en la base de datos (SPEC F1).
Cada problema lanza una excepción con un mensaje listo para mostrar al usuario.
"""

import io
import re
from dataclasses import dataclass

import docx
from pypdf import PdfReader
from pypdf.errors import PdfReadError

TAMANO_MAXIMO_BYTES = 5 * 1024 * 1024  # 5 MB
MINIMO_CARACTERES = 200
MAXIMO_CARACTERES = 30_000
EXTENSIONES_PERMITIDAS = {".pdf": "pdf", ".docx": "docx"}


class ErrorExtraccion(Exception):
    """Error base: `str(error)` es un mensaje en español apto para el usuario."""


class ArchivoInvalidoError(ErrorExtraccion):
    """Extensión no permitida, archivo corrupto, protegido o demasiado grande."""


class CVVacioError(ErrorExtraccion):
    """No se obtuvo texto suficiente (CV vacío, escaneado o ilegible)."""


class CVDemasiadoLargoError(ErrorExtraccion):
    """El texto supera el máximo permitido; nunca se recorta en silencio."""


@dataclass(frozen=True)
class TextoExtraido:
    texto: str
    origen: str  # "pdf" | "docx" | "texto"


def extraer_texto(archivo=None, texto: str | None = None) -> TextoExtraido:
    """Obtiene el texto del CV desde un archivo subido o desde texto pegado.

    `archivo` es cualquier objeto con `.name` y `.read()` (por ejemplo, un UploadedFile de Django).
    Si llegan ambos, se usa el archivo.
    """
    if archivo is not None:
        origen = _origen_por_extension(archivo.name)
        datos = _leer_con_limite(archivo)
        crudo = _texto_de_pdf(datos) if origen == "pdf" else _texto_de_docx(datos)
    elif texto is not None and texto.strip():
        origen, crudo = "texto", texto
    else:
        raise CVVacioError("Sube tu CV en PDF o DOCX, o pega su texto.")

    limpio = limpiar_texto(crudo)
    validar_longitud(limpio)
    return TextoExtraido(texto=limpio, origen=origen)


def limpiar_texto(texto: str) -> str:
    """Quita espacios repetidos y líneas vacías consecutivas, sin perder los saltos de línea útiles."""
    texto = texto.replace("\x00", "")
    lineas = [re.sub(r"[ \t ]+", " ", linea).strip() for linea in texto.splitlines()]
    resultado = "\n".join(lineas)
    return re.sub(r"\n{3,}", "\n\n", resultado).strip()


def validar_longitud(texto: str) -> None:
    """Rechaza CVs demasiado cortos o largos con mensajes que dicen qué hacer."""
    if len(texto) < MINIMO_CARACTERES:
        raise CVVacioError(
            "No pudimos leer suficiente texto de tu CV (¿está vacío o es una imagen escaneada?). "
            "Prueba pegando el texto directamente."
        )
    if len(texto) > MAXIMO_CARACTERES:
        raise CVDemasiadoLargoError(
            f"Tu CV tiene {len(texto):,} caracteres y el máximo es {MAXIMO_CARACTERES:,}. "
            "Resume las secciones menos relevantes e inténtalo de nuevo."
        )


def _origen_por_extension(nombre: str) -> str:
    extension = "." + nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if extension not in EXTENSIONES_PERMITIDAS:
        raise ArchivoInvalidoError("Formato no permitido. Sube un archivo PDF o DOCX.")
    return EXTENSIONES_PERMITIDAS[extension]


def _leer_con_limite(archivo) -> bytes:
    """Lee el archivo sin pasar del límite (lee 1 byte extra para detectar si lo excede)."""
    tamano = getattr(archivo, "size", None)
    if tamano is not None and tamano > TAMANO_MAXIMO_BYTES:
        raise ArchivoInvalidoError("El archivo pesa más de 5 MB.")
    datos = archivo.read(TAMANO_MAXIMO_BYTES + 1)
    if len(datos) > TAMANO_MAXIMO_BYTES:
        raise ArchivoInvalidoError("El archivo pesa más de 5 MB.")
    if not datos:
        raise CVVacioError("El archivo está vacío.")
    return datos


def _texto_de_pdf(datos: bytes) -> str:
    try:
        lector = PdfReader(io.BytesIO(datos))
        if lector.is_encrypted:
            raise ArchivoInvalidoError("El PDF está protegido con contraseña. Quita la protección o pega el texto.")
        return "\n".join(pagina.extract_text() or "" for pagina in lector.pages)
    except ArchivoInvalidoError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError) as error:
        raise ArchivoInvalidoError("No pudimos abrir el PDF; parece dañado. Prueba con otro archivo o pega el texto.") from error


def _texto_de_docx(datos: bytes) -> str:
    try:
        documento = docx.Document(io.BytesIO(datos))
    except Exception as error:  # python-docx lanza varios tipos (BadZipFile, KeyError, ValueError…)
        raise ArchivoInvalidoError("No pudimos abrir el DOCX; parece dañado. Prueba con otro archivo o pega el texto.") from error

    partes = [parrafo.text for parrafo in documento.paragraphs]
    # Muchos CVs usan tablas para maquetar: también leemos sus celdas.
    for tabla in documento.tables:
        for fila in tabla.rows:
            partes.append(" | ".join(celda.text for celda in fila.cells))
    return "\n".join(partes)
