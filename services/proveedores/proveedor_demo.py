"""Proveedor de demostración: imita al LLM con reglas simples, sin red y sin costo.

Sirve para que cualquiera (por ejemplo, un reclutador) pueda correr el proyecto sin API key.
No devuelve respuestas fijas: analiza el texto real del CV con el catálogo de habilidades.
"""

import json
import re

from services.catalogo_habilidades import detectar_habilidades_blandas, detectar_habilidades_tecnicas, texto_comparable
from services.esquemas import (
    Educacion,
    EvaluacionExterna,
    EvaluacionVacante,
    Experiencia,
    Idioma,
    PerfilCV,
    Recomendaciones,
    VacanteEstructurada,
)
from services.llm import (
    ErrorLLM,
    LlamadaHerramienta,
    MensajeAsistente,
    MensajeResultados,
    ProveedorLLM,
    RespuestaInvalidaError,
    RespuestaLLM,
)
from services.prompts import extraer_delimitado

MAX_MATCHES_DEMO = 8
ORDEN_NIVELES = {"trainee": 0, "jr": 1, "mid": 2}

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
        if esquema is VacanteEstructurada:
            return vacante_heuristica(extraer_delimitado("vacante", mensaje))
        raise ErrorLLM(f"El modo demo no sabe generar {esquema.__name__}.")

    def chat_con_herramientas(self, sistema, mensajes, herramientas):
        """Guion fijo que usa las herramientas REALES: buscar → calcular_match × N → entregar.

        El proveedor no guarda estado: deduce en qué paso va contando sus turnos anteriores.
        """
        paso = sum(isinstance(m, MensajeAsistente) for m in mensajes)
        mensaje_inicial = mensajes[0].texto
        perfil = PerfilCV.model_validate_json(extraer_delimitado("perfil", mensaje_inicial))
        resultados = [m for m in mensajes if isinstance(m, MensajeResultados)]
        if resultados and any(r.es_error for r in resultados[-1].resultados):
            raise ErrorLLM("El guion demo recibió un error de una herramienta.")

        if paso == 0:
            from services.herramientas import habilidades_del_perfil  # import local: evita un ciclo

            argumentos = {"nivel": None, "modalidad": None, "habilidades": habilidades_del_perfil(perfil), "limite": 10}
            return _pedir("Busco vacantes afines a tu perfil.", [("buscar_vacantes", argumentos)])
        if paso == 1:
            vacantes = json.loads(resultados[0].resultados[0].contenido)["vacantes"][:MAX_MATCHES_DEMO]
            return _pedir("Calculo el match con las más prometedoras.", [("calcular_match", {"vacante_id": v["id"]}) for v in vacantes])
        if paso == 2:
            niveles = {v["id"]: v["nivel"] for v in json.loads(resultados[0].resultados[0].contenido)["vacantes"]}
            matches = [json.loads(r.contenido) for r in resultados[1].resultados]
            recomendaciones = _recomendaciones_demo(perfil, matches, niveles, mensaje_inicial)
            return _pedir("Entrego el análisis.", [("entregar_recomendaciones", recomendaciones.model_dump())])
        raise ErrorLLM("El guion demo no esperaba más turnos.")


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


# --- Vacante pegada (heurística) ---------------------------------------------------------------

PALABRAS_DESEABLE = ("deseable", "plus", "valorable", "nice to have", "se valora")


def _nivel_de_vacante(comparable: str, anios: float) -> str:
    if any(p in comparable for p in ("trainee", "practicante", "becario", "pasante")):
        return "trainee"
    if any(p in comparable for p in ("senior", "semi senior", "semisenior", "mid", "sr.")) or anios >= 3:
        return "mid"
    return "jr"


def _modalidad_de_vacante(comparable: str) -> str:
    if "hibrid" in comparable:
        return "hibrido"
    if "remot" in comparable or "home office" in comparable:
        return "remoto"
    if "presencial" in comparable or "en oficina" in comparable:
        return "presencial"
    return "desconocida"


def vacante_heuristica(texto: str) -> VacanteEstructurada:
    """Estructura una vacante pegada con reglas simples (modo demo)."""
    comparable = texto_comparable(texto)
    requeridas: list[str] = []
    deseables: list[str] = []
    for linea in texto.splitlines():
        destino = deseables if any(p in texto_comparable(linea) for p in PALABRAS_DESEABLE) else requeridas
        destino += [h for h in detectar_habilidades_tecnicas(linea) if h not in requeridas + deseables]
    if not requeridas:
        requeridas, deseables = deseables, []
    if not requeridas:
        raise RespuestaInvalidaError(
            "La vacante no tiene habilidades reconocibles.",
            mensaje_usuario="No reconocimos habilidades técnicas en la vacante pegada. Revisa que incluya los requisitos.",
        )
    titulo = next((linea.strip() for linea in texto.splitlines() if linea.strip()), "Vacante pegada")[:120]
    return VacanteEstructurada(
        titulo=titulo,
        empresa="",
        nivel=_nivel_de_vacante(comparable, estimar_anios(texto)),
        modalidad=_modalidad_de_vacante(comparable),
        habilidades_requeridas=requeridas,
        habilidades_deseables=deseables,
        descripcion="Vacante pegada por el usuario (estructurada en modo demo).",
    )


# --- Guion del agente demo ----------------------------------------------------------------------


def _pedir(texto: str, llamadas: list[tuple[str, dict]]) -> RespuestaLLM:
    return RespuestaLLM(
        texto=texto,
        llamadas=[LlamadaHerramienta(f"demo_{i}", nombre, args) for i, (nombre, args) in enumerate(llamadas)],
        razon_fin="herramientas",
    )


def puntaje_simulado(puntaje_determinista: float, nivel_perfil: str, nivel_vacante: str) -> int:
    """Simula la evaluación del LLM: el puntaje determinista ajustado por cercanía de nivel."""
    distancia = abs(ORDEN_NIVELES[nivel_perfil] - ORDEN_NIVELES.get(nivel_vacante, ORDEN_NIVELES[nivel_perfil]))
    ajuste = {0: 10, 1: 0}.get(distancia, -15)
    return max(0, min(100, round(puntaje_determinista + ajuste)))


def _recomendaciones_demo(perfil: PerfilCV, matches: list[dict], niveles: dict[int, str], mensaje_inicial: str) -> Recomendaciones:
    from services.respaldo import construir_brechas, explicacion_determinista, palabras_clave_ats, sugerencias_cv

    for m in matches:
        m["puntaje_simulado"] = puntaje_simulado(m["puntaje_determinista"], perfil.nivel_estimado, niveles.get(m["vacante_id"], ""))
    top = sorted(matches, key=lambda m: m["puntaje_simulado"], reverse=True)[:5]
    palabras = palabras_clave_ats(m["faltantes_requeridas"] + m["faltantes_deseables"] for m in top)

    externa = None
    if "<vacante_externa>" in mensaje_inicial:
        datos = json.loads(extraer_delimitado("vacante_externa", mensaje_inicial))
        det = datos.get("puntaje_determinista", 0)
        faltan = datos.get("faltantes", [])
        externa = EvaluacionExterna(
            puntaje_llm=puntaje_simulado(det, perfil.nivel_estimado, datos.get("nivel", "")),
            explicacion=(f"Cubres el {det:g} % de lo que pide esta vacante."
                         + (f" Te falta: {', '.join(faltan[:3])}." if faltan else "")
                         + " (Evaluación simulada en modo demo.)"),
        )

    return Recomendaciones(
        top_vacantes=[
            EvaluacionVacante(
                vacante_id=m["vacante_id"],
                puntaje_llm=m["puntaje_simulado"],
                explicacion=explicacion_determinista(m["coincidentes"], m["faltantes_requeridas"]) + " (Evaluación simulada en modo demo.)",
            )
            for m in top
        ],
        vacante_externa=externa,
        brechas=construir_brechas((m["faltantes_requeridas"] for m in top), perfil),
        sugerencias_cv=sugerencias_cv(perfil, palabras),
        palabras_clave_ats=palabras,
    )
