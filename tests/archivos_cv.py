"""Generadores de archivos de CV para las pruebas (se crean en memoria, sin archivos fijos en el repo)."""

import io

import docx

TEXTO_CV = (
    "Ana Lopez - Desarrolladora Python Jr\n"
    "Experiencia: 1 año como desarrolladora backend en una startup de logistica, "
    "construyendo APIs REST con Django y PostgreSQL.\n"
    "Habilidades: Python, Django, SQL, Git, HTML, CSS, JavaScript, Docker.\n"
    "Educacion: Ingenieria en Sistemas Computacionales, 2024.\n"
    "Idiomas: Español nativo, Ingles intermedio (B1).\n"
    "Habilidades blandas: trabajo en equipo, comunicacion, aprendizaje continuo."
)


def crear_docx(parrafos: list[str], tabla: list[list[str]] | None = None) -> bytes:
    """Crea un DOCX con los párrafos dados y, opcionalmente, una tabla."""
    documento = docx.Document()
    for parrafo in parrafos:
        documento.add_paragraph(parrafo)
    if tabla:
        t = documento.add_table(rows=len(tabla), cols=len(tabla[0]))
        for i, fila in enumerate(tabla):
            for j, valor in enumerate(fila):
                t.cell(i, j).text = valor
    salida = io.BytesIO()
    documento.save(salida)
    return salida.getvalue()


def crear_pdf(lineas: list[str]) -> bytes:
    """Crea un PDF mínimo válido con texto (fuente Helvetica, solo caracteres latin-1)."""

    def escapar(texto: str) -> str:
        return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    comandos = ["BT", "/F1 11 Tf", "14 TL", "50 780 Td"]
    for linea in lineas:
        comandos.append(f"({escapar(linea)}) Tj T*")
    comandos.append("ET")
    contenido = "\n".join(comandos).encode("latin-1")

    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(contenido)).encode() + b" >>\nstream\n" + contenido + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    salida = io.BytesIO()
    salida.write(b"%PDF-1.4\n")
    posiciones = []
    for numero, cuerpo in enumerate(objetos, start=1):
        posiciones.append(salida.tell())
        salida.write(f"{numero} 0 obj\n".encode() + cuerpo + b"\nendobj\n")
    inicio_xref = salida.tell()
    salida.write(f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode())
    for posicion in posiciones:
        salida.write(f"{posicion:010d} 00000 n \n".encode())
    salida.write(f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n".encode())
    return salida.getvalue()
