"""Pruebas de la capa de proveedor de LLM: tipos, errores y fábrica (T10)."""

import pytest
from django.core.exceptions import ImproperlyConfigured

from services import llm
from services.esquemas import PerfilCV
from services.llm import (
    ApiKeyInvalidaError,
    ErrorLLM,
    LimiteApiError,
    ProveedorLLM,
    RespuestaInvalidaError,
    modo_demo_activo,
    obtener_proveedor,
)
from services.proveedores.proveedor_anthropic import ProveedorAnthropic
from services.proveedores.proveedor_demo import ProveedorDemo
from tests.datos import perfil_valido
from tests.falsos import ProveedorFalso


class TestFabrica:
    def test_sin_api_key_usa_demo(self, settings):
        settings.LLM_PROVEEDOR = "anthropic"
        settings.ANTHROPIC_API_KEY = ""
        proveedor = obtener_proveedor()
        assert isinstance(proveedor, ProveedorDemo)
        assert proveedor.es_demo
        assert modo_demo_activo()

    def test_con_api_key_usa_anthropic_con_el_modelo_configurado(self, settings):
        settings.LLM_PROVEEDOR = "anthropic"
        settings.ANTHROPIC_API_KEY = "sk-ant-prueba"
        settings.LLM_MODELO = "claude-haiku-5-5"
        proveedor = obtener_proveedor()
        assert isinstance(proveedor, ProveedorAnthropic)
        assert proveedor.modelo == "claude-haiku-5-5"
        assert not proveedor.es_demo
        assert not modo_demo_activo()

    def test_demo_forzado_aunque_haya_api_key(self, settings):
        settings.LLM_PROVEEDOR = "demo"
        settings.ANTHROPIC_API_KEY = "sk-ant-prueba"
        assert isinstance(obtener_proveedor(), ProveedorDemo)
        assert modo_demo_activo()

    def test_proveedor_desconocido(self, settings):
        settings.LLM_PROVEEDOR = "openai"
        with pytest.raises(ImproperlyConfigured, match="openai"):
            obtener_proveedor()


class TestErrores:
    def test_cada_error_tiene_un_mensaje_distinto_para_el_usuario(self):
        clases = [ErrorLLM, *ErrorLLM.__subclasses__()]
        mensajes = {clase.mensaje_usuario for clase in clases}
        assert len(mensajes) == len(clases)

    def test_mensaje_de_usuario_personalizable(self):
        error = LimiteApiError("429 de la API", mensaje_usuario="Espera 1 minuto.")
        assert error.mensaje_usuario == "Espera 1 minuto."
        assert "429" in str(error)

    def test_el_detalle_tecnico_no_reemplaza_el_mensaje_al_usuario(self):
        error = ApiKeyInvalidaError("401 invalid x-api-key")
        assert "ANTHROPIC_API_KEY" in error.mensaje_usuario
        assert "401" not in error.mensaje_usuario

    def test_todos_heredan_de_error_llm(self):
        assert all(issubclass(c, ErrorLLM) for c in ErrorLLM.__subclasses__())


class TestInterfaz:
    def test_no_se_puede_instanciar_la_clase_abstracta(self):
        with pytest.raises(TypeError):
            ProveedorLLM()

    def test_el_falso_cumple_la_interfaz_y_valida_esquemas(self):
        falso = ProveedorFalso(estructuradas=[perfil_valido(), {"invalido": True}])
        assert isinstance(falso, ProveedorLLM)
        assert isinstance(falso.generar_estructurado("s", "m", PerfilCV), PerfilCV)
        with pytest.raises(RespuestaInvalidaError):
            falso.generar_estructurado("s", "m", PerfilCV)

    def test_respuesta_llm_por_defecto(self):
        respuesta = llm.RespuestaLLM()
        assert respuesta.llamadas == [] and respuesta.razon_fin == "fin"
