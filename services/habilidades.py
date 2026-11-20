"""Normalización de nombres de habilidades.

El CV puede decir "ReactJS" y la vacante "React.js": para el matching deben contar como la misma
habilidad. La normalización se hace en dos pasos:

1. `_forma_base`: minúsculas, sin acentos, espacios simples y sin puntuación sobrante en los extremos.
   Se respetan símbolos con significado, como en "c#", "c++", ".net" o "node.js".
2. Diccionario de sinónimos: se busca por una *clave compacta* (sin espacios, puntos, guiones ni
   diagonales), así "react.js", "reactjs" y "react js" caen en la misma entrada.

Propiedad importante (probada en los tests): normalizar es idempotente,
es decir, normalizar(normalizar(x)) == normalizar(x).
"""

import re
import unicodedata
from collections.abc import Iterable

# Clave compacta → forma canónica. Las formas canónicas ya están normalizadas (minúsculas, sin acentos).
SINONIMOS: dict[str, str] = {
    # Lenguajes
    "js": "javascript",
    "javascript": "javascript",
    "ecmascript": "javascript",
    "ts": "typescript",
    "typescript": "typescript",
    "py": "python",
    "python": "python",
    "python3": "python",
    "csharp": "c#",
    "golang": "go",
    # Frameworks y librerías
    "react": "react",
    "reactjs": "react",
    "node": "node.js",
    "nodejs": "node.js",
    "vue": "vue.js",
    "vuejs": "vue.js",
    "next": "next.js",
    "nextjs": "next.js",
    "express": "express",
    "expressjs": "express",
    "drf": "django rest framework",
    "djangorest": "django rest framework",
    "djangorestframework": "django rest framework",
    "springboot": "spring boot",
    "net": ".net",
    "dotnet": ".net",
    "netcore": ".net",
    "tailwind": "tailwind css",
    "tailwindcss": "tailwind css",
    "sklearn": "scikit-learn",
    "scikitlearn": "scikit-learn",
    # Web
    "html": "html",
    "html5": "html",
    "css": "css",
    "css3": "css",
    "rest": "apis rest",
    "restapi": "apis rest",
    "restapis": "apis rest",
    "apirest": "apis rest",
    "apisrest": "apis rest",
    "apirestful": "apis rest",
    "apisrestful": "apis rest",
    # Bases de datos
    "postgres": "postgresql",
    "postgre": "postgresql",
    "postgresql": "postgresql",
    "mongo": "mongodb",
    "mongodb": "mongodb",
    "mssql": "sql server",
    "sqlserver": "sql server",
    # Nube y DevOps
    "amazonwebservices": "aws",
    "gcp": "google cloud",
    "googlecloud": "google cloud",
    "googlecloudplatform": "google cloud",
    "k8s": "kubernetes",
    "cicd": "ci/cd",
    # Datos e IA
    "ml": "machine learning",
    "machinelearning": "machine learning",
    "aprendizajeautomatico": "machine learning",
    "llm": "llms",
    "llms": "llms",
    "powerbi": "power bi",
    "msexcel": "excel",
    "microsoftexcel": "excel",
    # Idiomas y habilidades blandas
    "english": "ingles",
    "teamwork": "trabajo en equipo",
}

# Caracteres que se quitan de los extremos ("Python," → "python"). No incluye # ni + (C#, C++).
_PUNTUACION_EXTREMOS = " \t\n.,;:·•-–—*()[]{}\"'"
# Separadores que se ignoran al formar la clave compacta.
_SEPARADORES = re.compile(r"[\s.\-_/]+")


def _quitar_acentos(texto: str) -> str:
    """'Programación' → 'Programacion' (descompone la letra y elimina la marca del acento)."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def _forma_base(habilidad: str) -> str:
    """Minúsculas, sin acentos, espacios simples y sin puntuación sobrante en los extremos."""
    texto = _quitar_acentos(habilidad).lower()
    texto = re.sub(r"\s+", " ", texto)
    # Nota: ".NET" queda como "net" aquí; el diccionario de sinónimos lo devuelve a ".net".
    return texto.strip(_PUNTUACION_EXTREMOS)


def normalizar(habilidad: str) -> str:
    """Devuelve la forma canónica de una habilidad, o "" si no queda texto útil."""
    if not isinstance(habilidad, str):
        return ""
    base = _forma_base(habilidad)
    if not base:
        return ""
    clave = _SEPARADORES.sub("", base)
    return SINONIMOS.get(clave, base)


def normalizar_lista(habilidades: Iterable[str]) -> list[str]:
    """Normaliza una lista, quita vacíos y duplicados y conserva el orden original."""
    resultado: list[str] = []
    vistas: set[str] = set()
    for habilidad in habilidades:
        normalizada = normalizar(habilidad)
        if normalizada and normalizada not in vistas:
            vistas.add(normalizada)
            resultado.append(normalizada)
    return resultado
