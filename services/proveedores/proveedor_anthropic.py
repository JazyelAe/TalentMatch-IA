"""Proveedor de LLM basado en la API de Anthropic (se implementa en T11)."""

from services.llm import ProveedorLLM


class ProveedorAnthropic(ProveedorLLM):
    nombre = "anthropic"

    def __init__(self, api_key: str, modelo: str):
        self.modelo = modelo
        self._api_key = api_key

    def generar_estructurado(self, sistema, mensaje, esquema):
        raise NotImplementedError

    def chat_con_herramientas(self, sistema, mensajes, herramientas):
        raise NotImplementedError
