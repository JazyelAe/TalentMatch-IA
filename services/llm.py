"""Capa intercambiable de proveedor de LLM.

El resto del sistema (perfil, agente) solo conoce estos tipos neutrales y la interfaz ProveedorLLM.
Nunca importa el SDK de un proveedor. Cambiar de proveedor = escribir otra clase que implemente
ProveedorLLM y elegirla con la variable de entorno LLM_PROVEEDOR.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal, TypeVar

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pydantic import BaseModel

M = TypeVar("M", bound=BaseModel)

# --- Tipos neutrales --------------------------------------------------------------------------


@dataclass(frozen=True)
class Herramienta:
    """Definición de una herramienta que el LLM puede llamar."""

    nombre: str
    descripcion: str
    esquema: dict[str, Any]  # JSON Schema de los argumentos


@dataclass(frozen=True)
class LlamadaHerramienta:
    """Una llamada a herramienta que pidió el LLM."""

    id: str
    nombre: str
    argumentos: dict[str, Any]


RazonFin = Literal["fin", "herramientas", "limite_tokens"]


@dataclass
class RespuestaLLM:
    """Respuesta de un turno de chat, en formato neutral.

    `contenido_original` guarda la respuesta tal como la dio el proveedor, para reenviarla sin cambios
    en el siguiente turno (algunos modelos exigen recibir de vuelta sus bloques internos).
    """

    texto: str = ""
    llamadas: list[LlamadaHerramienta] = field(default_factory=list)
    razon_fin: RazonFin = "fin"
    contenido_original: Any = None


@dataclass(frozen=True)
class ResultadoHerramienta:
    """Lo que devolvió nuestra herramienta, para enviárselo al LLM."""

    llamada_id: str
    contenido: str  # normalmente JSON serializado
    es_error: bool = False


@dataclass(frozen=True)
class MensajeUsuario:
    texto: str


@dataclass(frozen=True)
class MensajeAsistente:
    respuesta: RespuestaLLM


@dataclass(frozen=True)
class MensajeResultados:
    resultados: list[ResultadoHerramienta]


Mensaje = MensajeUsuario | MensajeAsistente | MensajeResultados

# --- Errores ----------------------------------------------------------------------------------


class ErrorLLM(Exception):
    """Error base de la capa de LLM. `mensaje_usuario` está listo para mostrarse en la interfaz."""

    mensaje_usuario = "Ocurrió un problema al consultar la IA. Intenta de nuevo en unos minutos."

    def __init__(self, detalle: str = "", mensaje_usuario: str | None = None):
        super().__init__(detalle or self.mensaje_usuario)
        if mensaje_usuario:
            self.mensaje_usuario = mensaje_usuario


class ApiKeyInvalidaError(ErrorLLM):
    mensaje_usuario = "La API key del proveedor de IA no es válida. Revisa ANTHROPIC_API_KEY en tu archivo .env."


class LimiteApiError(ErrorLLM):
    mensaje_usuario = "Se alcanzó el límite de uso de la API de IA. Espera unos minutos e inténtalo de nuevo."


class ConexionLLMError(ErrorLLM):
    mensaje_usuario = "No pudimos conectar con el servicio de IA (o está saturado). Revisa tu conexión e inténtalo de nuevo."


class RechazoModeloError(ErrorLLM):
    mensaje_usuario = "El modelo de IA no pudo procesar este contenido. Revisa el texto e inténtalo de nuevo."


class RespuestaInvalidaError(ErrorLLM):
    mensaje_usuario = "La IA devolvió una respuesta con un formato inesperado. Inténtalo de nuevo."


# --- Interfaz ---------------------------------------------------------------------------------


class ProveedorLLM(ABC):
    """Contrato que cumple cada proveedor (Anthropic, demo, falso en pruebas)."""

    nombre: str = "base"
    modelo: str = ""
    es_demo: bool = False

    @abstractmethod
    def generar_estructurado(self, sistema: str, mensaje: str, esquema: type[M]) -> M:
        """Una sola llamada cuya salida debe validar contra `esquema` (modelo Pydantic).

        Lanza RespuestaInvalidaError si la salida no cumple el esquema.
        """

    @abstractmethod
    def chat_con_herramientas(self, sistema: str, mensajes: list[Mensaje], herramientas: list[Herramienta]) -> RespuestaLLM:
        """Un turno de conversación en el que el LLM puede pedir llamadas a herramientas."""


# --- Fábrica ----------------------------------------------------------------------------------

PROVEEDORES_VALIDOS = ("anthropic", "demo")


def obtener_proveedor() -> ProveedorLLM:
    """Elige el proveedor según la configuración. Sin API key se usa el modo demo automáticamente."""
    # Importaciones aquí para evitar ciclos: los proveedores importan los tipos de este módulo.
    from services.proveedores.proveedor_anthropic import ProveedorAnthropic
    from services.proveedores.proveedor_demo import ProveedorDemo

    nombre = settings.LLM_PROVEEDOR
    if nombre not in PROVEEDORES_VALIDOS:
        raise ImproperlyConfigured(f"LLM_PROVEEDOR={nombre!r} no es válido. Opciones: {', '.join(PROVEEDORES_VALIDOS)}.")
    if nombre == "demo" or not settings.ANTHROPIC_API_KEY:
        return ProveedorDemo()
    return ProveedorAnthropic(api_key=settings.ANTHROPIC_API_KEY, modelo=settings.LLM_MODELO)


def modo_demo_activo() -> bool:
    """True si la app está usando respuestas simuladas (para mostrar el aviso en la interfaz)."""
    return settings.LLM_PROVEEDOR == "demo" or not settings.ANTHROPIC_API_KEY
