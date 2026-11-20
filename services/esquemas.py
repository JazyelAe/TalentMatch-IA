"""Esquemas Pydantic de lo que produce el LLM.

Todo lo que devuelve el modelo se valida contra estos esquemas antes de usarse o guardarse.
Si el LLM inventa un nivel ("senior"), da un puntaje de 150 o devuelve listas vacías donde no
debe, la validación falla y el resto del sistema nunca ve ese dato.

`extra="forbid"` hace que el JSON Schema generado tenga `additionalProperties: false`, que la API
exige para la salida estructurada y las herramientas con `strict: true`.
"""

from copy import deepcopy
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from services.habilidades import normalizar

Nivel = Literal["trainee", "jr", "mid"]
Modalidad = Literal["remoto", "hibrido", "presencial", "desconocida"]
Prioridad = Literal["alta", "media", "baja"]
Texto = Annotated[str, StringConstraints(strip_whitespace=True)]
TextoNoVacio = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Puntaje = Annotated[int, Field(ge=0, le=100)]


def _limpiar_habilidades(valores: list[str]) -> list[str]:
    """Quita vacíos y duplicados (comparando la forma normalizada) y conserva el nombre original."""
    vistas: set[str] = set()
    resultado = []
    for valor in valores:
        clave = normalizar(valor)
        if clave and clave not in vistas:
            vistas.add(clave)
            resultado.append(valor.strip())
    return resultado


class Esquema(BaseModel):
    """Base común: no se aceptan campos que no estén definidos."""

    model_config = ConfigDict(extra="forbid")


# --- Perfil del CV ---------------------------------------------------------------------------


class Experiencia(Esquema):
    puesto: TextoNoVacio
    empresa: Texto = Field(description="Vacío si el CV no la menciona.")
    duracion: Texto = Field(description='Texto libre, por ejemplo "1 año" o "6 meses". Vacío si no se indica.')
    descripcion: Texto = Field(description="Una o dos frases con lo más relevante.")


class Educacion(Esquema):
    titulo: TextoNoVacio
    institucion: Texto
    anio: Texto = Field(description='Año de egreso o "en curso". Vacío si no se indica.')


class Idioma(Esquema):
    idioma: TextoNoVacio
    nivel: Texto = Field(description='Por ejemplo "nativo", "B2" o "intermedio".')


class PerfilCV(Esquema):
    """Perfil estructurado que el LLM extrae del texto del CV."""

    resumen: TextoNoVacio = Field(description="Una o dos frases que describen el perfil profesional.")
    habilidades_tecnicas: list[str]
    habilidades_blandas: list[str]
    experiencia: list[Experiencia]
    educacion: list[Educacion]
    idiomas: list[Idioma]
    anios_experiencia: Annotated[float, Field(ge=0, le=50)] = Field(description="Años de experiencia profesional en TI.")
    nivel_estimado: Nivel

    _limpiar = field_validator("habilidades_tecnicas", "habilidades_blandas")(_limpiar_habilidades)


# --- Vacante pegada por el usuario -----------------------------------------------------------


class VacanteEstructurada(Esquema):
    """Vacante real pegada como texto, convertida a la misma forma que el modelo Vacante."""

    titulo: TextoNoVacio
    empresa: Texto = Field(description="Vacío si el texto no la menciona.")
    nivel: Nivel
    modalidad: Modalidad
    habilidades_requeridas: Annotated[list[str], Field(min_length=1)]
    habilidades_deseables: list[str]
    descripcion: Texto = Field(description="Resumen de 1 a 3 frases.")

    _limpiar = field_validator("habilidades_requeridas", "habilidades_deseables")(_limpiar_habilidades)


# --- Resultado final del agente --------------------------------------------------------------


class EvaluacionVacante(Esquema):
    """Evaluación del LLM sobre una vacante del catálogo."""

    vacante_id: int
    puntaje_llm: Puntaje = Field(description="0 a 100: qué tan bien encaja el perfil, más allá de la lista de habilidades.")
    explicacion: TextoNoVacio = Field(description="De 1 a 3 frases, dirigidas a la persona.")


class EvaluacionExterna(Esquema):
    """Evaluación del LLM sobre la vacante pegada por el usuario."""

    puntaje_llm: Puntaje
    explicacion: TextoNoVacio


class Brecha(Esquema):
    """Habilidad que falta, con un mini plan para aprenderla."""

    habilidad: TextoNoVacio
    prioridad: Prioridad
    motivo: TextoNoVacio = Field(description="Por qué importa (por ejemplo, cuántas vacantes del top la piden).")
    pasos: Annotated[list[TextoNoVacio], Field(min_length=2, max_length=4)] = Field(description="De 2 a 4 pasos concretos.")
    tiempo_estimado: TextoNoVacio = Field(description='Por ejemplo "2 semanas".')


class Recomendaciones(Esquema):
    """Lo que entrega el agente al terminar (herramienta `entregar_recomendaciones`)."""

    top_vacantes: Annotated[list[EvaluacionVacante], Field(min_length=1, max_length=5)]
    vacante_externa: EvaluacionExterna | None = Field(description="Solo si el usuario pegó una vacante; si no, null.")
    # Se piden de 3 a 7 brechas en el prompt, pero se aceptan desde 1: un perfil que ya cubre casi
    # todo no debe obligar al modelo a inventar brechas.
    brechas: Annotated[list[Brecha], Field(min_length=1, max_length=7)]
    sugerencias_cv: Annotated[list[TextoNoVacio], Field(min_length=3, max_length=6)]
    palabras_clave_ats: list[str]

    @field_validator("top_vacantes")
    @classmethod
    def _sin_vacantes_repetidas(cls, valor: list[EvaluacionVacante]) -> list[EvaluacionVacante]:
        ids = [e.vacante_id for e in valor]
        if len(ids) != len(set(ids)):
            raise ValueError("top_vacantes no puede repetir una vacante.")
        return valor

    _limpiar = field_validator("palabras_clave_ats")(_limpiar_habilidades)


# --- JSON Schema para la API -----------------------------------------------------------------

# Restricciones que la salida estructurada de la API no admite: se quitan del esquema enviado
# y se siguen validando del lado del cliente con Pydantic.
_CLAVES_NO_SOPORTADAS = {
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    "minLength", "maxLength", "minItems", "maxItems", "default", "title",
}


def esquema_json_estricto(modelo: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema del modelo listo para `strict: true`: sin restricciones no soportadas y con
    todos los campos de cada objeto en `required`."""
    esquema = deepcopy(modelo.model_json_schema())

    def limpiar(nodo: Any) -> Any:
        if isinstance(nodo, dict):
            limpio = {k: limpiar(v) for k, v in nodo.items() if k not in _CLAVES_NO_SOPORTADAS}
            if limpio.get("type") == "object" and "properties" in limpio:
                limpio["required"] = list(limpio["properties"])
                limpio["additionalProperties"] = False
            return limpio
        if isinstance(nodo, list):
            return [limpiar(v) for v in nodo]
        return nodo

    return limpiar(esquema)
