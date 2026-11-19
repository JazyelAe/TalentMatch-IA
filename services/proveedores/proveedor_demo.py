"""Proveedor de demostración: imita al LLM con reglas simples, sin red y sin costo.

Sirve para que cualquiera (por ejemplo, un reclutador) pueda correr el proyecto sin API key.
No devuelve respuestas fijas: analiza el texto real del CV con el catálogo de habilidades.
"""

import re

from services.catalogo_habilidades import detectar_habilidades_blandas, detectar_habilidades_tecnicas, texto_comparable
from services.esquemas import Educacion, Experiencia, Idioma, PerfilCV
from services.llm import ErrorLLM, ProveedorLLM
from services.prompts import extraer_delimitado

PALABRAS_TRAINEE = ("trainee", "practicante", "becario", "pasante", "estudiante", "residencia profesional")
PALABRAS_EXPERIENCIA = ("desarrollador", "desarrolladora", "developer", "ingeniero", "ingeniera", "analista", "programador", "programadora", "practicante")
PALABRAS_EDUCACION = ("ingenieria", "licenciatura", "carrera", "universidad", "bootcamp", "maestria", "tecnico en", "certificacion")
NIVELES_IDIOMA = ("nativo", "nativa", "a1", "a2", "b1", "b2", "c1", "c2", "basico", "intermedio", "avanzado", "fluido")
IDIOMAS = {"Español": ("espanol", "spanish"), "Inglés": ("ingles", "english"), "Francés": ("frances", "french"), "Alemán": ("aleman", "german")}


class ProveedorDemo(ProveedorLLM):
    """Implementa la misma interfaz que el proveedor real, con heurísticas."""

    nombre = "demo"
    modelo = "demo-heuristico"
    es_demo = True

    def generar_estructurado(self, sistema, mensaje, esquema):
        if esquema is PerfilCV:
            return perfil_heuristico(extraer_delimitado("cv", mensaje))
        raise ErrorLLM(f"El modo demo no sabe generar {esquema.__name__}.")

    def chat_con_herramientas(self, sistema, mensajes, herramientas):
        raise NotImplementedError  # se implementa en T16 (guion del agente)


# --- Perfil heurístico ------------------------------------------------------------------------


def estimar_anios(texto: str) -> float:
    """Toma el mayor número de años mencionado ("2 años", "1.5 years", "3+ años"), con tope de 50."""
    comparable = texto_comparable(texto)
    valores = [float(n.replace(",", ".")) for n in re.findall(r"(\d+(?:[.,]\d+)?)\s*\+?\s*(?:anos?|years?)\b", comparable)]
    # Se ignoran números que parecen años calendario (2024) o edades poco plausibles.
    valores = [v for v in valores if v <= 50]
    return max(valores, default=0.0)


def estimar_nivel(texto: str, anios: float) -> str:
    """Reglas: <1 año o palabras de formación → trainee; <3 años → jr; resto → mid."""
    comparable = texto_comparable(texto)
    if anios < 1 or (anios < 2 and any(p in comparable for p in PALABRAS_TRAINEE)):
        return "trainee"
    if anios < 3:
        return "jr"
    return "mid"


def detectar_idiomas(texto: str) -> list[Idioma]:
    idiomas = []
    for linea in texto_comparable(texto).splitlines():
        for nombre, variantes in IDIOMAS.items():
            for variante in variantes:
                posicion = linea.find(variante)
                if posicion == -1 or any(i.idioma == nombre for i in idiomas):
                    continue
                cercano = linea[posicion : posicion + 40]
                nivel = next((n for n in NIVELES_IDIOMA if re.search(rf"\b{n}\b", cercano)), "")
                idiomas.append(Idioma(idioma=nombre, nivel=nivel.upper() if len(nivel) == 2 else nivel))
    return idiomas


def _lineas_con(texto: str, palabras: tuple[str, ...], limite: int = 3) -> list[str]:
    encontradas = []
    for linea in texto.splitlines():
        if linea.strip() and any(p in texto_comparable(linea) for p in palabras):
            encontradas.append(linea.strip()[:150])
    return encontradas[:limite]


def perfil_heuristico(texto_cv: str) -> PerfilCV:
    """Construye un PerfilCV válido a partir del texto, sin IA."""
    tecnicas = detectar_habilidades_tecnicas(texto_cv)
    anios = estimar_anios(texto_cv)
    nivel = estimar_nivel(texto_cv, anios)
    principales = ", ".join(tecnicas[:5]) or "sin habilidades técnicas reconocidas"

    return PerfilCV(
        resumen=f"Perfil {nivel} con {anios:g} año(s) de experiencia; destaca en {principales}. (Generado en modo demo.)",
        habilidades_tecnicas=tecnicas,
        habilidades_blandas=detectar_habilidades_blandas(texto_cv),
        experiencia=[
            Experiencia(puesto=linea, empresa="", duracion="", descripcion="")
            for linea in _lineas_con(texto_cv, PALABRAS_EXPERIENCIA)
        ],
        educacion=[
            Educacion(titulo=linea, institucion="", anio=(re.findall(r"\b(?:19|20)\d{2}\b", linea) or [""])[-1])
            for linea in _lineas_con(texto_cv, PALABRAS_EDUCACION)
        ],
        idiomas=detectar_idiomas(texto_cv),
        anios_experiencia=anios,
        nivel_estimado=nivel,
    )
