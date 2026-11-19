"""Orquestador: une todas las piezas del análisis y guarda el resultado (SPEC §4.6).

    texto del CV → perfil (LLM) → [vacante pegada] → agente (o respaldo) → puntaje final → BD

Es la única pieza de `services/` que escribe en la base de datos.
"""

import logging

from django.conf import settings
from django.db import transaction

from analisis.models import Analisis, ResultadoMatch
from services.agente import AgenteSinResultadoError, ejecutar_agente
from services.esquemas import Recomendaciones, VacanteEstructurada
from services.herramientas import habilidades_del_perfil
from services.llm import ProveedorLLM, obtener_proveedor
from services.matching import ResultadoDeterminista, calcular_match_determinista, combinar_puntajes
from services.perfil import extraer_perfil
from services.respaldo import recomendaciones_de_respaldo
from services.vacante_externa import estructurar_vacante, match_vacante_externa
from vacantes.models import Vacante

logger = logging.getLogger(__name__)


class CatalogoVacioError(Exception):
    """No hay vacantes activas contra las cuales comparar."""

    mensaje_usuario = (
        "Todavía no hay vacantes cargadas. Ejecuta `python manage.py cargar_vacantes_ejemplo` o agrégalas desde el admin."
    )


def analizar_cv(
    texto_cv: str,
    origen: str,
    texto_vacante: str | None = None,
    proveedor: ProveedorLLM | None = None,
) -> Analisis:
    """Ejecuta el análisis completo y devuelve el Analisis guardado.

    Errores que pueden salir de aquí (la vista los convierte en mensajes):
    ErrorLLM (y subclases), VacanteExternaInvalidaError y CatalogoVacioError.
    """
    if not Vacante.objects.filter(activa=True).exists():
        raise CatalogoVacioError()
    proveedor = proveedor or obtener_proveedor()

    perfil = extraer_perfil(texto_cv, proveedor)

    vacante_externa: VacanteEstructurada | None = None
    match_externo: ResultadoDeterminista | None = None
    if texto_vacante and texto_vacante.strip():
        vacante_externa = estructurar_vacante(texto_vacante, proveedor)
        match_externo = match_vacante_externa(perfil, vacante_externa)

    try:
        resultado = ejecutar_agente(perfil, proveedor, vacante_externa, match_externo)
        recomendaciones, iteraciones, parcial = resultado.recomendaciones, resultado.iteraciones, False
    except AgenteSinResultadoError as error:
        logger.warning("Se usa el respaldo determinista: %s", error)
        recomendaciones = recomendaciones_de_respaldo(perfil, match_externo)
        iteraciones, parcial = settings.AGENTE_MAX_ITERACIONES, True

    return _guardar(perfil, origen, recomendaciones, vacante_externa, match_externo, proveedor, iteraciones, parcial)


def _guardar(perfil, origen, recomendaciones: Recomendaciones, vacante_externa, match_externo, proveedor, iteraciones, parcial) -> Analisis:
    """Calcula los puntajes finales y guarda todo en una sola transacción (todo o nada)."""
    peso = settings.MATCH_PESO_DETERMINISTA
    habilidades = habilidades_del_perfil(perfil)
    vacantes = Vacante.objects.in_bulk([e.vacante_id for e in recomendaciones.top_vacantes])

    filas = []
    for evaluacion in recomendaciones.top_vacantes:
        vacante = vacantes[evaluacion.vacante_id]
        # El puntaje determinista lo recalcula el código: no se confía en lo que diga el LLM.
        det = calcular_match_determinista(habilidades, vacante.habilidades_requeridas, vacante.habilidades_deseables)
        filas.append(
            ResultadoMatch(
                vacante=vacante,
                titulo=vacante.titulo,
                empresa=vacante.empresa,
                puntaje_determinista=det.puntaje,
                puntaje_llm=evaluacion.puntaje_llm,
                puntaje_final=combinar_puntajes(det.puntaje, evaluacion.puntaje_llm, peso),
                habilidades_coincidentes=det.coincidentes,
                habilidades_faltantes=det.faltantes,
                explicacion=evaluacion.explicacion,
            )
        )
    # HU-03: el top se muestra ordenado por puntaje final.
    filas.sort(key=lambda f: f.puntaje_final, reverse=True)
    for posicion, fila in enumerate(filas, start=1):
        fila.posicion = posicion

    if vacante_externa is not None and match_externo is not None and recomendaciones.vacante_externa is not None:
        evaluacion = recomendaciones.vacante_externa
        filas.append(
            ResultadoMatch(
                es_externa=True,
                posicion=1,
                titulo=vacante_externa.titulo,
                empresa=vacante_externa.empresa,
                puntaje_determinista=match_externo.puntaje,
                puntaje_llm=evaluacion.puntaje_llm,
                puntaje_final=combinar_puntajes(match_externo.puntaje, evaluacion.puntaje_llm, peso),
                habilidades_coincidentes=match_externo.coincidentes,
                habilidades_faltantes=match_externo.faltantes,
                explicacion=evaluacion.explicacion,
            )
        )

    with transaction.atomic():
        analisis = Analisis.objects.create(
            origen_cv=origen,
            perfil=perfil.model_dump(),
            recomendaciones=recomendaciones.model_dump(include={"brechas", "sugerencias_cv", "palabras_clave_ats"}),
            vacante_externa=vacante_externa.model_dump() if vacante_externa else None,
            proveedor=proveedor.nombre,
            modelo=proveedor.modelo,
            resultado_parcial=parcial,
            iteraciones_agente=iteraciones,
        )
        for fila in filas:
            fila.analisis = analisis
        ResultadoMatch.objects.bulk_create(filas)
    return analisis
