"""Puntaje de coincidencia entre un perfil y una vacante.

Dos piezas, ambas puras (sin base de datos ni LLM), para que sean fáciles de probar:

- `calcular_match_determinista`: compara habilidades normalizadas. Mismo input → mismo output.
- `combinar_puntajes`: mezcla la parte determinista con la evaluación del LLM (SPEC §4.5).
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from services.habilidades import normalizar, normalizar_lista

PESO_REQUERIDAS = 0.8
PESO_DESEABLES = 0.2


@dataclass(frozen=True)
class ResultadoDeterminista:
    """Resultado de comparar habilidades. Los nombres conservan cómo los escribió la vacante."""

    puntaje: float
    coincidentes: list[str] = field(default_factory=list)
    faltantes_requeridas: list[str] = field(default_factory=list)
    faltantes_deseables: list[str] = field(default_factory=list)

    @property
    def faltantes(self) -> list[str]:
        """Todas las habilidades que faltan, primero las requeridas."""
        return self.faltantes_requeridas + self.faltantes_deseables


def _sin_duplicados(habilidades: Iterable[str]) -> list[str]:
    """Quita habilidades repetidas tras normalizar, conservando el primer nombre original."""
    vistas: set[str] = set()
    resultado = []
    for habilidad in habilidades:
        clave = normalizar(habilidad)
        if clave and clave not in vistas:
            vistas.add(clave)
            resultado.append(habilidad.strip())
    return resultado


def calcular_match_determinista(
    habilidades_perfil: Iterable[str],
    habilidades_requeridas: Iterable[str],
    habilidades_deseables: Iterable[str] = (),
) -> ResultadoDeterminista:
    """Puntaje 0–100: 80 % por requeridas cubiertas + 20 % por deseables cubiertas.

    Si la vacante no tiene deseables, las requeridas valen el 100 % (y viceversa).
    Si no tiene ninguna habilidad, el puntaje es 0 (no hay con qué comparar).
    """
    perfil = set(normalizar_lista(habilidades_perfil))
    requeridas = _sin_duplicados(habilidades_requeridas)
    claves_requeridas = set(normalizar_lista(requeridas))
    # Si una habilidad aparece en ambas listas, cuenta solo como requerida.
    deseables = [h for h in _sin_duplicados(habilidades_deseables) if normalizar(h) not in claves_requeridas]

    req_cubiertas = [h for h in requeridas if normalizar(h) in perfil]
    des_cubiertas = [h for h in deseables if normalizar(h) in perfil]

    if requeridas and deseables:
        fraccion = PESO_REQUERIDAS * len(req_cubiertas) / len(requeridas) + PESO_DESEABLES * len(des_cubiertas) / len(deseables)
    elif requeridas:
        fraccion = len(req_cubiertas) / len(requeridas)
    elif deseables:
        fraccion = len(des_cubiertas) / len(deseables)
    else:
        fraccion = 0.0

    return ResultadoDeterminista(
        puntaje=round(100 * fraccion, 1),
        coincidentes=req_cubiertas + des_cubiertas,
        faltantes_requeridas=[h for h in requeridas if h not in req_cubiertas],
        faltantes_deseables=[h for h in deseables if h not in des_cubiertas],
    )


def combinar_puntajes(determinista: float, llm: float, peso_determinista: float) -> float:
    """Puntaje final = peso · determinista + (1 − peso) · llm, redondeado a 1 decimal.

    Lo calcula el código (no el LLM) para que el modelo no pueda inflar la parte objetiva.
    """
    if not 0 <= peso_determinista <= 1:
        raise ValueError(f"El peso determinista debe estar entre 0 y 1 (recibido: {peso_determinista}).")
    det = min(max(determinista, 0.0), 100.0)
    eval_llm = min(max(llm, 0.0), 100.0)
    return round(peso_determinista * det + (1 - peso_determinista) * eval_llm, 1)
