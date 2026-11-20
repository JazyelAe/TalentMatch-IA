"""Pruebas de la configuración leída desde variables de entorno (T01)."""

import importlib

import pytest
from django.core.exceptions import ImproperlyConfigured

from config import entorno

VARIABLES_PROYECTO = [
    "DJANGO_SECRET_KEY",
    "DJANGO_DEBUG",
    "LLM_PROVEEDOR",
    "LLM_MODELO",
    "ANTHROPIC_API_KEY",
    "AGENTE_MAX_ITERACIONES",
    "MATCH_PESO_DETERMINISTA",
]


@pytest.fixture
def settings_limpios(monkeypatch):
    """Recarga config.settings sin variables del proyecto y sin leer el .env local."""
    for nombre in VARIABLES_PROYECTO:
        monkeypatch.delenv(nombre, raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)

    import config.settings as modulo

    def recargar():
        return importlib.reload(modulo)

    yield recargar
    monkeypatch.undo()
    importlib.reload(modulo)  # deja la configuración como estaba para las demás pruebas


class TestObtenerSecretKey:
    def test_usa_la_clave_del_entorno(self):
        assert entorno.obtener_secret_key("mi-clave", debug=False) == "mi-clave"

    def test_sin_clave_en_debug_usa_la_de_desarrollo(self):
        assert entorno.obtener_secret_key("", debug=True) == entorno.SECRET_KEY_DESARROLLO

    def test_sin_clave_fuera_de_debug_falla(self):
        with pytest.raises(ImproperlyConfigured, match="DJANGO_SECRET_KEY"):
            entorno.obtener_secret_key("", debug=False)


class TestLectores:
    @pytest.mark.parametrize("valor", ["true", "True", "1", "sí", "si", "yes", "on"])
    def test_bool_verdadero(self, monkeypatch, valor):
        monkeypatch.setenv("X_BOOL", valor)
        assert entorno.leer_bool("X_BOOL") is True

    @pytest.mark.parametrize("valor", ["false", "0", "no", "off"])
    def test_bool_falso(self, monkeypatch, valor):
        monkeypatch.setenv("X_BOOL", valor)
        assert entorno.leer_bool("X_BOOL", por_defecto=True) is False

    def test_bool_vacio_usa_por_defecto(self, monkeypatch):
        monkeypatch.setenv("X_BOOL", "")
        assert entorno.leer_bool("X_BOOL", por_defecto=True) is True

    def test_int_invalido_explica_la_variable(self, monkeypatch):
        monkeypatch.setenv("X_INT", "ocho")
        with pytest.raises(ImproperlyConfigured, match="X_INT"):
            entorno.leer_int("X_INT", 8)

    def test_float_valido(self, monkeypatch):
        monkeypatch.setenv("X_FLOAT", "0.75")
        assert entorno.leer_float("X_FLOAT", 0.6) == 0.75


class TestValoresPorDefecto:
    def test_modelo_y_proveedor_por_defecto(self, settings_limpios):
        s = settings_limpios()
        assert s.LLM_MODELO == "claude-haiku-5-5"
        assert s.LLM_PROVEEDOR == "anthropic"
        assert s.ANTHROPIC_API_KEY == ""

    def test_parametros_del_agente_por_defecto(self, settings_limpios):
        s = settings_limpios()
        assert s.AGENTE_MAX_ITERACIONES == 8
        assert s.MATCH_PESO_DETERMINISTA == 0.6

    def test_arranca_sin_env_en_modo_debug(self, settings_limpios):
        s = settings_limpios()
        assert s.DEBUG is True
        assert s.SECRET_KEY == entorno.SECRET_KEY_DESARROLLO

    def test_idioma_espanol(self, settings_limpios):
        s = settings_limpios()
        assert s.LANGUAGE_CODE == "es-mx"
