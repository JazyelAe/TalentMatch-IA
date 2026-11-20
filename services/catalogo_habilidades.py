"""Catálogo de habilidades conocidas, usado por el modo demo para detectarlas en un texto sin IA.

Cada entrada es: nombre para mostrar → variantes con que puede aparecer en un CV o una vacante.
Las variantes van en minúsculas y sin acentos (el texto se compara ya normalizado).
"""

import re
import unicodedata

HABILIDADES_TECNICAS: dict[str, list[str]] = {
    # Lenguajes
    "Python": ["python", "python3"],
    "JavaScript": ["javascript", "js", "ecmascript"],
    "TypeScript": ["typescript", "ts"],
    "Java": ["java"],
    "C#": ["c#", "csharp"],
    "C++": ["c++"],
    "PHP": ["php"],
    "Go": ["golang"],
    "Dart": ["dart"],
    "Kotlin": ["kotlin"],
    "Swift": ["swift"],
    "Bash": ["bash", "shell scripting"],
    "SQL": ["sql"],
    # Web y frameworks
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "Tailwind CSS": ["tailwind", "tailwind css", "tailwindcss"],
    "React": ["react", "reactjs", "react.js"],
    "Vue.js": ["vue", "vuejs", "vue.js"],
    "Angular": ["angular"],
    "Next.js": ["next.js", "nextjs"],
    "Node.js": ["node", "nodejs", "node.js"],
    "Express": ["express", "expressjs", "express.js"],
    "Django": ["django"],
    "Django REST Framework": ["django rest framework", "drf"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi"],
    "Laravel": ["laravel"],
    "Spring Boot": ["spring boot", "springboot"],
    ".NET": [".net", "dotnet", "net core"],
    "Flutter": ["flutter"],
    "APIs REST": ["api rest", "apis rest", "rest api", "rest apis", "restful", "api restful"],
    "GraphQL": ["graphql"],
    # Datos
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "SQL Server": ["sql server", "mssql"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "Pandas": ["pandas"],
    "Scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "Machine Learning": ["machine learning", "aprendizaje automatico"],
    "Estadística": ["estadistica", "statistics"],
    "Power BI": ["power bi", "powerbi"],
    "Excel": ["excel"],
    "Airflow": ["airflow"],
    "Spark": ["spark", "pyspark"],
    "dbt": ["dbt"],
    "Jupyter": ["jupyter"],
    "LLMs": ["llm", "llms", "modelos de lenguaje"],
    "Prompt engineering": ["prompt engineering", "ingenieria de prompts"],
    # DevOps y nube
    "Git": ["git"],
    "GitHub": ["github"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Linux": ["linux"],
    "CI/CD": ["ci/cd", "cicd", "integracion continua"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure"],
    "Google Cloud": ["gcp", "google cloud"],
    "Terraform": ["terraform"],
    "Celery": ["celery"],
    "Firebase": ["firebase"],
    "Redes": ["redes", "networking", "tcp/ip"],
    "Wireshark": ["wireshark"],
    # Pruebas y herramientas
    "Pytest": ["pytest"],
    "Jest": ["jest"],
    "JUnit": ["junit"],
    "Selenium": ["selenium"],
    "Postman": ["postman"],
    "Testing": ["testing", "pruebas unitarias", "unit testing"],
    "Pruebas manuales": ["pruebas manuales", "manual testing"],
    "Jira": ["jira"],
    "Figma": ["figma"],
    "Maven": ["maven"],
    "Accesibilidad web": ["accesibilidad web", "accesibilidad"],
    "Lógica de programación": ["logica de programacion", "algoritmos"],
}

HABILIDADES_BLANDAS: dict[str, list[str]] = {
    "Trabajo en equipo": ["trabajo en equipo", "teamwork", "colaboracion"],
    "Comunicación": ["comunicacion", "communication"],
    "Resolución de problemas": ["resolucion de problemas", "problem solving"],
    "Aprendizaje continuo": ["aprendizaje continuo", "autodidacta"],
    "Liderazgo": ["liderazgo", "leadership"],
    "Adaptabilidad": ["adaptabilidad", "flexibilidad"],
    "Pensamiento crítico": ["pensamiento critico", "critical thinking"],
    "Organización": ["organizacion", "gestion del tiempo"],
}


def texto_comparable(texto: str) -> str:
    """Minúsculas y sin acentos, para buscar variantes del catálogo."""
    sin_acentos = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return sin_acentos.lower()


def _patron(variante: str) -> re.Pattern:
    # La variante no debe estar pegada a otras letras o símbolos de código ("java" no debe
    # encontrarse dentro de "javascript", ni "c" dentro de "c#").
    return re.compile(rf"(?<![\w#+.]){re.escape(variante)}(?![\w#+]|\.\w)")


_PATRONES_TECNICAS = {nombre: [_patron(v) for v in variantes] for nombre, variantes in HABILIDADES_TECNICAS.items()}
_PATRONES_BLANDAS = {nombre: [_patron(v) for v in variantes] for nombre, variantes in HABILIDADES_BLANDAS.items()}


def _detectar(texto: str, patrones: dict[str, list[re.Pattern]]) -> list[str]:
    comparable = texto_comparable(texto)
    return [nombre for nombre, lista in patrones.items() if any(p.search(comparable) for p in lista)]


def detectar_habilidades_tecnicas(texto: str) -> list[str]:
    """Habilidades técnicas del catálogo que aparecen en el texto (en el orden del catálogo)."""
    return _detectar(texto, _PATRONES_TECNICAS)


def detectar_habilidades_blandas(texto: str) -> list[str]:
    """Habilidades blandas del catálogo que aparecen en el texto."""
    return _detectar(texto, _PATRONES_BLANDAS)
