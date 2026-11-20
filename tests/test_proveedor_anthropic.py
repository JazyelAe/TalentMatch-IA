"""Pruebas del ProveedorAnthropic con el cliente del SDK simulado (T11). Nunca se llama a la API real."""

import json
from unittest.mock import MagicMock

import anthropic
import httpx2
import pytest
from anthropic.types import Message, TextBlock, ToolUseBlock, Usage

from services.esquemas import PerfilCV
from services.llm import (
    ApiKeyInvalidaError,
    ConexionLLMError,
    ErrorLLM,
    Herramienta,
    LimiteApiError,
    LlamadaHerramienta,
    MensajeAsistente,
    MensajeResultados,
    MensajeUsuario,
    RechazoModeloError,
    RespuestaInvalidaError,
    RespuestaLLM,
    ResultadoHerramienta,
)
from services.proveedores.proveedor_anthropic import ProveedorAnthropic
from tests.datos import perfil_valido

PETICION = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
HERRAMIENTA = Herramienta("buscar_vacantes", "Busca vacantes", {"type": "object", "properties": {}, "additionalProperties": False})


def mensaje_api(contenido, stop_reason="end_turn", **extra) -> Message:
    return Message(
        id="msg_1", type="message", role="assistant", model="claude-haiku-5-5", content=contenido,
        stop_reason=stop_reason, stop_sequence=None, usage=Usage(input_tokens=10, output_tokens=10), **extra,
    )


def error_http(clase, codigo: int):
    return clase(f"error {codigo}", response=httpx2.Response(codigo, request=PETICION), body=None)


@pytest.fixture
def cliente():
    return MagicMock()


@pytest.fixture
def proveedor(cliente):
    return ProveedorAnthropic(api_key="sk-ant-prueba", modelo="claude-haiku-5-5", cliente=cliente)


class TestGenerarEstructurado:
    def test_devuelve_el_modelo_validado(self, proveedor, cliente):
        cliente.messages.create.return_value = mensaje_api([TextBlock(type="text", text=json.dumps(perfil_valido()))])
        perfil = proveedor.generar_estructurado("sistema", "texto del cv", PerfilCV)
        assert isinstance(perfil, PerfilCV)

    def test_envia_modelo_sistema_y_esquema_estricto(self, proveedor, cliente):
        cliente.messages.create.return_value = mensaje_api([TextBlock(type="text", text=json.dumps(perfil_valido()))])
        proveedor.generar_estructurado("sistema X", "texto del cv", PerfilCV)
        kwargs = cliente.messages.create.call_args.kwargs
        assert kwargs["model"] == "claude-haiku-5-5"
        assert kwargs["system"] == "sistema X"
        assert kwargs["messages"] == [{"role": "user", "content": "texto del cv"}]
        formato = kwargs["output_config"]["format"]
        assert formato["type"] == "json_schema"
        assert formato["schema"]["additionalProperties"] is False

    def test_json_mal_formado(self, proveedor, cliente):
        cliente.messages.create.return_value = mensaje_api([TextBlock(type="text", text='{"resumen": "incompleto"')])
        with pytest.raises(RespuestaInvalidaError):
            proveedor.generar_estructurado("s", "m", PerfilCV)

    def test_json_que_no_cumple_el_esquema(self, proveedor, cliente):
        cliente.messages.create.return_value = mensaje_api(
            [TextBlock(type="text", text=json.dumps(perfil_valido(nivel_estimado="senior")))]
        )
        with pytest.raises(RespuestaInvalidaError, match="PerfilCV"):
            proveedor.generar_estructurado("s", "m", PerfilCV)

    def test_respuesta_cortada_por_max_tokens(self, proveedor, cliente):
        cliente.messages.create.return_value = mensaje_api([TextBlock(type="text", text="{")], stop_reason="max_tokens")
        with pytest.raises(RespuestaInvalidaError, match="max_tokens"):
            proveedor.generar_estructurado("s", "m", PerfilCV)

    def test_rechazo_del_modelo(self, proveedor, cliente):
        cliente.messages.create.return_value = mensaje_api([], stop_reason="refusal")
        with pytest.raises(RechazoModeloError):
            proveedor.generar_estructurado("s", "m", PerfilCV)


class TestChatConHerramientas:
    def test_traduce_llamadas_a_herramientas(self, proveedor, cliente):
        contenido = [
            TextBlock(type="text", text="Voy a buscar vacantes."),
            ToolUseBlock(type="tool_use", id="toolu_1", name="buscar_vacantes", input={"nivel": "jr"}),
        ]
        cliente.messages.create.return_value = mensaje_api(contenido, stop_reason="tool_use")
        respuesta = proveedor.chat_con_herramientas("s", [MensajeUsuario("hola")], [HERRAMIENTA])
        assert respuesta.razon_fin == "herramientas"
        assert respuesta.texto == "Voy a buscar vacantes."
        assert respuesta.llamadas == [LlamadaHerramienta("toolu_1", "buscar_vacantes", {"nivel": "jr"})]
        assert respuesta.contenido_original == contenido

    def test_fin_sin_herramientas(self, proveedor, cliente):
        cliente.messages.create.return_value = mensaje_api([TextBlock(type="text", text="Listo")])
        respuesta = proveedor.chat_con_herramientas("s", [MensajeUsuario("hola")], [HERRAMIENTA])
        assert respuesta.razon_fin == "fin" and respuesta.llamadas == []

    def test_max_tokens_descarta_llamadas_incompletas(self, proveedor, cliente):
        contenido = [ToolUseBlock(type="tool_use", id="t", name="buscar_vacantes", input={})]
        cliente.messages.create.return_value = mensaje_api(contenido, stop_reason="max_tokens")
        respuesta = proveedor.chat_con_herramientas("s", [MensajeUsuario("hola")], [HERRAMIENTA])
        assert respuesta.razon_fin == "limite_tokens" and respuesta.llamadas == []

    def test_envia_herramientas_estrictas_y_tool_choice_auto(self, proveedor, cliente):
        cliente.messages.create.return_value = mensaje_api([TextBlock(type="text", text="ok")])
        proveedor.chat_con_herramientas("s", [MensajeUsuario("hola")], [HERRAMIENTA])
        kwargs = cliente.messages.create.call_args.kwargs
        assert kwargs["tools"] == [
            {"name": "buscar_vacantes", "description": "Busca vacantes", "input_schema": HERRAMIENTA.esquema, "strict": True}
        ]
        assert kwargs["tool_choice"] == {"type": "auto"}

    def test_traduce_el_historial_de_mensajes(self, proveedor, cliente):
        cliente.messages.create.return_value = mensaje_api([TextBlock(type="text", text="ok")])
        original = [ToolUseBlock(type="tool_use", id="t1", name="buscar_vacantes", input={})]
        historial = [
            MensajeUsuario("Analiza mi perfil"),
            MensajeAsistente(RespuestaLLM(llamadas=[LlamadaHerramienta("t1", "buscar_vacantes", {})], contenido_original=original)),
            MensajeResultados([ResultadoHerramienta("t1", '{"vacantes": []}', es_error=False)]),
        ]
        proveedor.chat_con_herramientas("s", historial, [HERRAMIENTA])
        enviados = cliente.messages.create.call_args.kwargs["messages"]
        assert enviados[0] == {"role": "user", "content": "Analiza mi perfil"}
        assert enviados[1] == {"role": "assistant", "content": original}  # se reenvía sin cambios
        assert enviados[2] == {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t1", "content": '{"vacantes": []}', "is_error": False}],
        }

    def test_asistente_sin_contenido_original_se_reconstruye(self):
        mensaje = ProveedorAnthropic._a_mensaje_api(
            MensajeAsistente(RespuestaLLM(texto="Busco", llamadas=[LlamadaHerramienta("t1", "obtener_vacante", {"id": 3})]))
        )
        assert mensaje == {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Busco"},
                {"type": "tool_use", "id": "t1", "name": "obtener_vacante", "input": {"id": 3}},
            ],
        }


class TestErrores:
    @pytest.mark.parametrize(
        "excepcion, esperado",
        [
            (error_http(anthropic.AuthenticationError, 401), ApiKeyInvalidaError),
            (error_http(anthropic.PermissionDeniedError, 403), ApiKeyInvalidaError),
            (error_http(anthropic.RateLimitError, 429), LimiteApiError),
            (error_http(anthropic.InternalServerError, 500), ConexionLLMError),
            (error_http(anthropic.InternalServerError, 529), ConexionLLMError),
            (anthropic.APIConnectionError(request=PETICION), ConexionLLMError),
            (anthropic.APITimeoutError(request=PETICION), ConexionLLMError),
            (error_http(anthropic.BadRequestError, 400), ErrorLLM),
        ],
    )
    def test_mapea_excepciones_del_sdk(self, proveedor, cliente, excepcion, esperado):
        cliente.messages.create.side_effect = excepcion
        with pytest.raises(esperado) as info:
            proveedor.chat_con_herramientas("s", [MensajeUsuario("hola")], [])
        assert type(info.value) is esperado

    def test_modelo_inexistente_explica_la_variable(self, proveedor, cliente):
        cliente.messages.create.side_effect = error_http(anthropic.NotFoundError, 404)
        with pytest.raises(ErrorLLM) as info:
            proveedor.generar_estructurado("s", "m", PerfilCV)
        assert "LLM_MODELO" in info.value.mensaje_usuario

    def test_rechazo_en_chat(self, proveedor, cliente):
        cliente.messages.create.return_value = mensaje_api([], stop_reason="refusal")
        with pytest.raises(RechazoModeloError):
            proveedor.chat_con_herramientas("s", [MensajeUsuario("hola")], [])


def test_crea_cliente_real_sin_conectarse():
    """Construir el proveedor no hace peticiones (la red está bloqueada en las pruebas)."""
    proveedor = ProveedorAnthropic(api_key="sk-ant-prueba", modelo="claude-haiku-5-5")
    assert proveedor.modelo == "claude-haiku-5-5"
