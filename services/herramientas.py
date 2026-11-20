"""Herramientas que el agente (LLM) puede llamar, y el despachador que las ejecuta.

Cada herramienta tiene:
- un modelo Pydantic con sus argumentos (de él sale el JSON Schema que ve el LLM y la validación),
- una función de Python que hace el trabajo real (consultar la BD, calcular el match).

Las herramientas son de SOLO LECTURA: el LLM nunca puede modificar datos.
Los errores no se lanzan hacia el agente: se devuelven al LLM como resultado con `es_error=True`
para que pueda corregir su llamada.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, ValidationError

from services.esquemas import Esquema, Nivel, PerfilCV, Recomendaciones, VacanteEstructurada, esquema_json_estricto
from services.habilidades import normalizar_lista
from services.llm import Herramienta, LlamadaHerramienta, ResultadoHerramienta
from services.matching import calcular_match_determinista
from vacantes.models import Vacante

logger = logging.getLogger(__name__)

LIMITE_BUSQUEDA = 10
HERRAMIENTA_FINAL = "entregar_recomendaciones"


class ErrorHerramienta(Exception):
    """Error que se le explica al LLM (por ejemplo, un id de vacante que no existe)."""


@dataclass(frozen=True)
class ContextoAgente:
    """Datos que las herramientas necesitan y que NO vienen del LLM (el LLM no puede alterarlos)."""

    perfil: PerfilCV
    vacante_externa: VacanteEstructurada | None = None


def habilidades_del_perfil(perfil: PerfilCV) -> list[str]:
    """Todo lo que cuenta para el matching: técnicas, blandas e idiomas."""
    return perfil.habilidades_tecnicas + perfil.habilidades_blandas + [i.idioma for i in perfil.idiomas]


# --- Argumentos ---------------------------------------------------------------------------------


class ArgsBuscarVacantes(Esquema):
    nivel: Nivel | None = Field(description="Filtra por nivel; null para no filtrar.")
    modalidad: Literal["remoto", "hibrido", "presencial"] | None = Field(description="Filtra por modalidad; null para no filtrar.")
    habilidades: list[str] = Field(description="Ordena por cuántas de estas habilidades pide cada vacante. Lista vacía para no ordenar.")
    limite: Annotated[int, Field(ge=1, le=LIMITE_BUSQUEDA)] = Field(description=f"Máximo de resultados (1 a {LIMITE_BUSQUEDA}).")


class ArgsVacanteId(Esquema):
    vacante_id: int


# --- Implementaciones ---------------------------------------------------------------------------


def _resumen(vacante: Vacante) -> dict[str, Any]:
    return {
        "id": vacante.id,
        "titulo": vacante.titulo,
        "empresa": vacante.empresa,
        "nivel": vacante.nivel,
        "modalidad": vacante.modalidad,
        "ubicacion": vacante.ubicacion,
        "habilidades_requeridas": vacante.habilidades_requeridas,
    }


def _vacante_activa(vacante_id: int) -> Vacante:
    vacante = Vacante.objects.filter(pk=vacante_id, activa=True).first()
    if vacante is None:
        raise ErrorHerramienta(f"No existe una vacante activa con id {vacante_id}. Usa buscar_vacantes para ver los ids válidos.")
    return vacante


def buscar_vacantes(contexto: ContextoAgente, args: ArgsBuscarVacantes) -> dict[str, Any]:
    """Lista resumida de vacantes activas, filtrada y ordenada por afinidad de habilidades."""
    consulta = Vacante.objects.filter(activa=True)
    if args.nivel:
        consulta = consulta.filter(nivel=args.nivel)
    if args.modalidad:
        consulta = consulta.filter(modalidad=args.modalidad)

    buscadas = set(normalizar_lista(args.habilidades))
    resultados = []
    for vacante in consulta.order_by("id"):
        pedidas = set(normalizar_lista(vacante.habilidades_requeridas + vacante.habilidades_deseables))
        resultados.append({**_resumen(vacante), "coincidencias": len(buscadas & pedidas)})
    if buscadas:
        resultados.sort(key=lambda r: r["coincidencias"], reverse=True)  # sort estable: empata por id

    return {"total_encontradas": len(resultados), "vacantes": resultados[: args.limite]}


def obtener_vacante(contexto: ContextoAgente, args: ArgsVacanteId) -> dict[str, Any]:
    """Detalle completo de una vacante."""
    vacante = _vacante_activa(args.vacante_id)
    return {
        **_resumen(vacante),
        "habilidades_deseables": vacante.habilidades_deseables,
        "descripcion": vacante.descripcion,
    }


def calcular_match(contexto: ContextoAgente, args: ArgsVacanteId) -> dict[str, Any]:
    """Puntaje determinista entre el perfil del contexto y una vacante."""
    vacante = _vacante_activa(args.vacante_id)
    resultado = calcular_match_determinista(
        habilidades_del_perfil(contexto.perfil), vacante.habilidades_requeridas, vacante.habilidades_deseables
    )
    return {
        "vacante_id": vacante.id,
        "titulo": vacante.titulo,
        "puntaje_determinista": resultado.puntaje,
        "coincidentes": resultado.coincidentes,
        "faltantes_requeridas": resultado.faltantes_requeridas,
        "faltantes_deseables": resultado.faltantes_deseables,
    }


# --- Registro y despachador ---------------------------------------------------------------------


@dataclass(frozen=True)
class _Registro:
    argumentos: type[BaseModel]
    funcion: Callable[[ContextoAgente, Any], dict[str, Any]]


REGISTRO: dict[str, _Registro] = {
    "buscar_vacantes": _Registro(ArgsBuscarVacantes, buscar_vacantes),
    "obtener_vacante": _Registro(ArgsVacanteId, obtener_vacante),
    "calcular_match": _Registro(ArgsVacanteId, calcular_match),
}

HERRAMIENTAS_AGENTE: list[Herramienta] = [
    Herramienta(
        "buscar_vacantes",
        "Busca vacantes de TI activas en el catálogo. Devuelve un resumen de cada una (id, título, empresa, "
        "nivel, modalidad y habilidades requeridas) y cuántas de las habilidades indicadas pide.",
        esquema_json_estricto(ArgsBuscarVacantes),
    ),
    Herramienta(
        "obtener_vacante",
        "Devuelve el detalle completo de una vacante: habilidades requeridas y deseables, y descripción.",
        esquema_json_estricto(ArgsVacanteId),
    ),
    Herramienta(
        "calcular_match",
        "Calcula el puntaje determinista (0-100) entre el perfil del candidato y una vacante, con las "
        "habilidades que coinciden y las que faltan. Úsala antes de recomendar una vacante.",
        esquema_json_estricto(ArgsVacanteId),
    ),
    Herramienta(
        HERRAMIENTA_FINAL,
        "Entrega el resultado final del análisis. Llámala UNA sola vez, al terminar, con el top de vacantes "
        "(máximo 5), las brechas de habilidades con su mini plan y las sugerencias para el CV.",
        esquema_json_estricto(Recomendaciones),
    ),
]


def a_json(datos: Any) -> str:
    return json.dumps(datos, ensure_ascii=False)


def ejecutar_herramienta(llamada: LlamadaHerramienta, contexto: ContextoAgente) -> ResultadoHerramienta:
    """Valida los argumentos y ejecuta la herramienta. Nunca lanza: los errores vuelven al LLM."""
    registro = REGISTRO.get(llamada.nombre)
    if registro is None:
        return ResultadoHerramienta(llamada.id, a_json({"error": f"La herramienta {llamada.nombre!r} no existe."}), es_error=True)
    try:
        argumentos = registro.argumentos.model_validate(llamada.argumentos)
        return ResultadoHerramienta(llamada.id, a_json(registro.funcion(contexto, argumentos)))
    except ValidationError as error:
        detalle = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'argumentos'}: {e['msg']}" for e in error.errors())
        return ResultadoHerramienta(llamada.id, a_json({"error": f"Argumentos inválidos: {detalle}"}), es_error=True)
    except ErrorHerramienta as error:
        return ResultadoHerramienta(llamada.id, a_json({"error": str(error)}), es_error=True)
    except Exception:  # un fallo inesperado no debe tumbar el análisis completo
        logger.exception("Fallo inesperado en la herramienta %s", llamada.nombre)
        return ResultadoHerramienta(llamada.id, a_json({"error": "Error interno al ejecutar la herramienta."}), es_error=True)
