"""Proveedor de demostración, sin red ni costo (se implementa en T12 y T16)."""

from services.llm import ProveedorLLM


class ProveedorDemo(ProveedorLLM):
    nombre = "demo"
    modelo = "demo-heuristico"
    es_demo = True

    def generar_estructurado(self, sistema, mensaje, esquema):
        raise NotImplementedError

    def chat_con_herramientas(self, sistema, mensajes, herramientas):
        raise NotImplementedError
