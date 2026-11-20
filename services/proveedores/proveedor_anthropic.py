"""Proveedor de LLM basado en la API de Anthropic (SDK oficial `anthropic`).

Este es el ÚNICO archivo del proyecto que importa el SDK. Su trabajo es traducir:
- de nuestros tipos neutrales (services/llm.py) al formato de la API, y
- de las respuestas y excepciones de la API a nuestros tipos y errores.
"""

import logging
from typing import Any

import anthropic
from pydantic import ValidationError

from services.esquemas import esquema_json_estricto
from services.llm import (
    ApiKeyInvalidaError,
    ConexionLLMError,
    ErrorLLM,
    Herramienta,
    LimiteApiError,
    LlamadaHerramienta,
    Mensaje,
    MensajeAsistente,
    MensajeResultados,
    MensajeUsuario,
    ProveedorLLM,
    RechazoModeloError,
    RespuestaInvalidaError,
    RespuestaLLM,
)

logger = logging.getLogger(__name__)

MAX_TOKENS = 16_000  # sin streaming conviene quedarse por debajo de ~16k para no tocar los timeouts HTTP
TIMEOUT_SEGUNDOS = 120.0
REINTENTOS = 2  # el SDK reintenta solo 408/409/429/5xx y errores de conexión, con espera exponencial


class ProveedorAnthropic(ProveedorLLM):
    """Implementación de ProveedorLLM con la Messages API de Anthropic."""

    nombre = "anthropic"

    def __init__(self, api_key: str, modelo: str, cliente: Any = None):
        self.modelo = modelo
        # `cliente` permite inyectar un doble en las pruebas; en la app se crea el cliente real.
        self._cliente = cliente or anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_SEGUNDOS, max_retries=REINTENTOS)

    # --- Interfaz pública -------------------------------------------------------------------

    def generar_estructurado(self, sistema, mensaje, esquema):
        """Pide una salida JSON que cumpla el esquema y la valida con Pydantic."""
        respuesta = self._llamar(
            system=sistema,
            messages=[{"role": "user", "content": mensaje}],
            output_config={"format": {"type": "json_schema", "schema": esquema_json_estricto(esquema)}},
        )
        self._revisar_rechazo(respuesta)
        if respuesta.stop_reason == "max_tokens":
            raise RespuestaInvalidaError("La salida estructurada se cortó por max_tokens.")

        texto = "".join(b.text for b in respuesta.content if b.type == "text")
        try:
            return esquema.model_validate_json(texto)
        except ValidationError as error:
            raise RespuestaInvalidaError(f"La salida no cumple {esquema.__name__}: {error.error_count()} errores.") from error

    def chat_con_herramientas(self, sistema, mensajes, herramientas):
        """Un turno del ciclo del agente: el modelo responde con texto y/o llamadas a herramientas."""
        respuesta = self._llamar(
            system=sistema,
            messages=[self._a_mensaje_api(m) for m in mensajes],
            tools=[self._a_herramienta_api(h) for h in herramientas],
            tool_choice={"type": "auto"},  # forzar una herramienta no es compatible con todos los modelos
        )
        self._revisar_rechazo(respuesta)

        llamadas = [
            LlamadaHerramienta(id=b.id, nombre=b.name, argumentos=dict(b.input or {}))
            for b in respuesta.content
            if b.type == "tool_use"
        ]
        if respuesta.stop_reason == "max_tokens":
            razon = "limite_tokens"  # una llamada cortada podría traer argumentos incompletos: no se ejecuta
            llamadas = []
        elif llamadas:
            razon = "herramientas"
        else:
            razon = "fin"

        return RespuestaLLM(
            texto="".join(b.text for b in respuesta.content if b.type == "text"),
            llamadas=llamadas,
            razon_fin=razon,
            contenido_original=respuesta.content,
        )

    # --- Traducción -------------------------------------------------------------------------

    @staticmethod
    def _a_herramienta_api(herramienta: Herramienta) -> dict:
        return {
            "name": herramienta.nombre,
            "description": herramienta.descripcion,
            "input_schema": herramienta.esquema,
            "strict": True,  # garantiza argumentos que cumplen el esquema
        }

    @staticmethod
    def _a_mensaje_api(mensaje: Mensaje) -> dict:
        if isinstance(mensaje, MensajeUsuario):
            return {"role": "user", "content": mensaje.texto}
        if isinstance(mensaje, MensajeAsistente):
            respuesta = mensaje.respuesta
            if respuesta.contenido_original is not None:
                # Se reenvía tal cual (incluye bloques internos que el modelo necesita ver de vuelta).
                return {"role": "assistant", "content": respuesta.contenido_original}
            bloques: list[dict] = [{"type": "text", "text": respuesta.texto}] if respuesta.texto else []
            bloques += [{"type": "tool_use", "id": ll.id, "name": ll.nombre, "input": ll.argumentos} for ll in respuesta.llamadas]
            return {"role": "assistant", "content": bloques}
        if isinstance(mensaje, MensajeResultados):
            return {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": r.llamada_id, "content": r.contenido, "is_error": r.es_error}
                    for r in mensaje.resultados
                ],
            }
        raise TypeError(f"Tipo de mensaje no soportado: {type(mensaje).__name__}")

    # --- Llamada y errores ------------------------------------------------------------------

    def _llamar(self, **parametros):
        """Llama a la API y convierte cada excepción del SDK en nuestro error correspondiente.

        Se capturan de la más específica a la más general: así un 401 no se confunde con un 500.
        """
        try:
            return self._cliente.messages.create(model=self.modelo, max_tokens=MAX_TOKENS, **parametros)
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as error:
            logger.error("Anthropic rechazó las credenciales: %s", error.status_code)
            raise ApiKeyInvalidaError(str(error)) from error
        except anthropic.RateLimitError as error:
            logger.warning("Anthropic: límite de uso alcanzado (429).")
            raise LimiteApiError(str(error)) from error
        except anthropic.NotFoundError as error:
            logger.error("Anthropic: modelo o recurso no encontrado (%s).", self.modelo)
            raise ErrorLLM(
                str(error),
                mensaje_usuario=f"El modelo configurado ({self.modelo}) no existe o no está disponible. Revisa LLM_MODELO.",
            ) from error
        except anthropic.InternalServerError as error:
            logger.warning("Anthropic: error del servidor (%s).", error.status_code)
            raise ConexionLLMError(str(error)) from error
        except anthropic.APIConnectionError as error:  # incluye APITimeoutError
            logger.warning("Anthropic: error de conexión o tiempo de espera agotado.")
            raise ConexionLLMError(str(error)) from error
        except anthropic.APIStatusError as error:
            logger.error("Anthropic: error HTTP inesperado %s.", error.status_code)
            raise ErrorLLM(str(error)) from error

    @staticmethod
    def _revisar_rechazo(respuesta) -> None:
        if respuesta.stop_reason == "refusal":
            categoria = getattr(getattr(respuesta, "stop_details", None), "category", None)
            logger.warning("Anthropic: el modelo rechazó la petición (categoría: %s).", categoria)
            raise RechazoModeloError(f"refusal ({categoria})")
