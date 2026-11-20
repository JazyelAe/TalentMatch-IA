"""Pruebas del servicio de extracción de perfil (T13)."""

import pytest

from services.esquemas import PerfilCV
from services.llm import LimiteApiError, RespuestaInvalidaError
from services.perfil import SISTEMA_PERFIL, extraer_perfil
from services.proveedores.proveedor_demo import ProveedorDemo
from tests.archivos_cv import TEXTO_CV
from tests.datos import perfil_valido
from tests.falsos import ProveedorFalso


def test_devuelve_el_perfil_validado():
    falso = ProveedorFalso(estructuradas=[perfil_valido()])
    perfil = extraer_perfil(TEXTO_CV, falso)
    assert isinstance(perfil, PerfilCV)
    assert len(falso.llamadas) == 1


def test_envia_el_cv_delimitado_como_dato():
    falso = ProveedorFalso(estructuradas=[perfil_valido()])
    extraer_perfil(TEXTO_CV, falso)
    llamada = falso.llamadas[0]
    assert llamada["sistema"] == SISTEMA_PERFIL
    assert llamada["esquema"] is PerfilCV
    assert f"<cv>\n{TEXTO_CV}\n</cv>" in llamada["mensaje"]


def test_reintenta_una_vez_si_la_salida_es_invalida():
    falso = ProveedorFalso(estructuradas=[{"resumen": "incompleto"}, perfil_valido()])
    assert extraer_perfil(TEXTO_CV, falso).nivel_estimado == "jr"
    assert len(falso.llamadas) == 2


def test_falla_tras_dos_salidas_invalidas(caplog):
    falso = ProveedorFalso(estructuradas=[{"x": 1}, perfil_valido(nivel_estimado="senior")])
    with pytest.raises(RespuestaInvalidaError):
        extraer_perfil(TEXTO_CV, falso)
    assert len(falso.llamadas) == 2
    assert "intento 2 de 2" in caplog.text
    assert "Django" not in caplog.text  # el log no incluye el contenido del CV


def test_otros_errores_no_se_reintentan():
    falso = ProveedorFalso(estructuradas=[LimiteApiError("429")])
    with pytest.raises(LimiteApiError):
        extraer_perfil(TEXTO_CV, falso)
    assert len(falso.llamadas) == 1


def test_funciona_con_el_proveedor_demo():
    perfil = extraer_perfil(TEXTO_CV, ProveedorDemo())
    assert "Django" in perfil.habilidades_tecnicas


def test_el_prompt_prohibe_seguir_instrucciones_del_cv_y_datos_sensibles():
    assert "no instrucciones" in SISTEMA_PERFIL
    assert "datos personales" in SISTEMA_PERFIL
