"""Dobles de prueba (fakes) reutilizables.

ProveedorFalso imita a un proveedor de LLM con respuestas programadas de antemano.
Así las pruebas son rápidas, gratis, deterministas y nunca tocan la red.
"""

from collections import deque
from typing import Any

from pydantic import BaseModel, ValidationError

from services.llm import ProveedorLLM, RespuestaInvalidaError


class RespuestasAgotadas(AssertionError):
    """El código bajo prueba llamó al LLM más veces de las que la prueba programó."""


class ProveedorFalso(ProveedorLLM):
    """Proveedor de LLM falso: devuelve, en orden, las respuestas que le programes.

    Ejemplo:
        falso = ProveedorFalso(estructuradas=[perfil_dict], chats=[respuesta_1, respuesta_2])

    - Si un elemento programado es una excepción, se lanza en lugar de devolverse
      (así se simulan fallos de la API: límite, conexión, etc.).
    - En `generar_estructurado`, si el elemento es un dict, se valida contra el esquema pedido,
      igual que haría un proveedor real; si no valida, lanza RespuestaInvalidaError.
    - Cada llamada se registra en `llamadas` para verificar qué se le pidió al LLM.
    """

    nombre = "falso"
    modelo = "modelo-falso"

    def __init__(self, estructuradas: list[Any] | None = None, chats: list[Any] | None = None):
        self._estructuradas = deque(estructuradas or [])
        self._chats = deque(chats or [])
        self.llamadas: list[dict[str, Any]] = []

    def generar_estructurado(self, sistema: str, mensaje: str, esquema: type) -> Any:
        """Devuelve la siguiente respuesta estructurada programada (validada si es un dict)."""
        self.llamadas.append({"metodo": "generar_estructurado", "sistema": sistema, "mensaje": mensaje, "esquema": esquema})
        respuesta = self._siguiente(self._estructuradas, "generar_estructurado")
        if isinstance(respuesta, dict) and isinstance(esquema, type) and issubclass(esquema, BaseModel):
            try:
                return esquema.model_validate(respuesta)
            except ValidationError as error:
                raise RespuestaInvalidaError(str(error)) from error
        return respuesta

    def chat_con_herramientas(self, sistema: str, mensajes: list, herramientas: list) -> Any:
        """Devuelve la siguiente respuesta de chat programada."""
        # Copiamos los mensajes: el agente los modifica después y queremos ver cómo estaban en esta llamada.
        self.llamadas.append(
            {"metodo": "chat_con_herramientas", "sistema": sistema, "mensajes": list(mensajes), "herramientas": herramientas}
        )
        return self._siguiente(self._chats, "chat_con_herramientas")

    @staticmethod
    def _siguiente(cola: deque, metodo: str) -> Any:
        if not cola:
            raise RespuestasAgotadas(f"ProveedorFalso.{metodo} se llamó más veces de las programadas.")
        respuesta = cola.popleft()
        if isinstance(respuesta, BaseException):
            raise respuesta
        return respuesta
