"""Pruebas de las herramientas del agente y su despachador (T14)."""

import json

import pytest
from django.core.management import call_command

from services.esquemas import PerfilCV
from services.herramientas import (
    HERRAMIENTA_FINAL,
    HERRAMIENTAS_AGENTE,
    ContextoAgente,
    ejecutar_herramienta,
    habilidades_del_perfil,
)
from services.llm import LlamadaHerramienta
from tests.datos import perfil_valido
from vacantes.models import Vacante


@pytest.fixture
def contexto():
    return ContextoAgente(perfil=PerfilCV.model_validate(perfil_valido()))


@pytest.fixture
def vacantes(db):
    call_command("cargar_vacantes_ejemplo")
    return Vacante.objects.all()


def ejecutar(contexto, nombre, **argumentos):
    resultado = ejecutar_herramienta(LlamadaHerramienta("t1", nombre, argumentos), contexto)
    return resultado, json.loads(resultado.contenido)


def buscar(contexto, **cambios):
    argumentos = {"nivel": None, "modalidad": None, "habilidades": [], "limite": 10, **cambios}
    return ejecutar(contexto, "buscar_vacantes", **argumentos)


class TestBuscarVacantes:
    def test_respeta_el_limite(self, contexto, vacantes):
        resultado, datos = buscar(contexto, limite=3)
        assert not resultado.es_error
        assert datos["total_encontradas"] == 20
        assert len(datos["vacantes"]) == 3

    def test_filtra_por_nivel_y_modalidad(self, contexto, vacantes):
        _, datos = buscar(contexto, nivel="trainee", modalidad="presencial")
        assert datos["vacantes"]
        assert all(v["nivel"] == "trainee" and v["modalidad"] == "presencial" for v in datos["vacantes"])

    def test_ordena_por_habilidades_buscadas(self, contexto, vacantes):
        _, datos = buscar(contexto, habilidades=["Python", "Django"], limite=5)
        coincidencias = [v["coincidencias"] for v in datos["vacantes"]]
        assert coincidencias == sorted(coincidencias, reverse=True)
        assert coincidencias[0] == 2

    def test_no_incluye_vacantes_inactivas(self, contexto, vacantes):
        Vacante.objects.update(activa=False)
        _, datos = buscar(contexto)
        assert datos == {"total_encontradas": 0, "vacantes": []}

    @pytest.mark.parametrize("limite", [0, 11])
    def test_limite_fuera_de_rango_es_error(self, contexto, vacantes, limite):
        resultado, datos = buscar(contexto, limite=limite)
        assert resultado.es_error
        assert "limite" in datos["error"]

    def test_nivel_invalido_es_error(self, contexto, vacantes):
        resultado, _ = buscar(contexto, nivel="senior")
        assert resultado.es_error


class TestObtenerVacante:
    def test_devuelve_el_detalle(self, contexto, vacantes):
        vacante = vacantes.first()
        resultado, datos = ejecutar(contexto, "obtener_vacante", vacante_id=vacante.id)
        assert not resultado.es_error
        assert datos["titulo"] == vacante.titulo
        assert "habilidades_deseables" in datos and "descripcion" in datos

    def test_id_inexistente_es_error_manejable(self, contexto, vacantes):
        resultado, datos = ejecutar(contexto, "obtener_vacante", vacante_id=99999)
        assert resultado.es_error
        assert "99999" in datos["error"]


class TestCalcularMatch:
    def test_calcula_con_el_perfil_del_contexto(self, contexto, vacantes):
        vacante = Vacante.objects.get(titulo="Desarrollador Backend Python Jr")
        resultado, datos = ejecutar(contexto, "calcular_match", vacante_id=vacante.id)
        assert not resultado.es_error
        # El perfil tiene Python, Django, SQL y Git, pero no "APIs REST" → 4/5 requeridas, 0/3 deseables
        assert datos["puntaje_determinista"] == 64.0
        assert datos["faltantes_requeridas"] == ["APIs REST"]

    def test_las_habilidades_blandas_e_idiomas_cuentan(self, contexto):
        assert "Comunicación" in habilidades_del_perfil(contexto.perfil)
        assert "Inglés" in habilidades_del_perfil(contexto.perfil)

    def test_argumento_de_tipo_incorrecto(self, contexto, vacantes):
        resultado, datos = ejecutar(contexto, "calcular_match", vacante_id="uno")
        assert resultado.es_error and "vacante_id" in datos["error"]


class TestDespachador:
    def test_herramienta_desconocida(self, contexto):
        resultado, datos = ejecutar(contexto, "borrar_vacantes")
        assert resultado.es_error and "no existe" in datos["error"]

    def test_conserva_el_id_de_la_llamada(self, contexto, vacantes):
        resultado = ejecutar_herramienta(LlamadaHerramienta("toolu_abc", "obtener_vacante", {"vacante_id": 1}), contexto)
        assert resultado.llamada_id == "toolu_abc"

    def test_fallo_inesperado_no_se_propaga(self, contexto, monkeypatch):
        from services import herramientas

        def explota(*_):
            raise RuntimeError("bug")

        monkeypatch.setitem(herramientas.REGISTRO, "obtener_vacante", herramientas._Registro(herramientas.ArgsVacanteId, explota))
        resultado, datos = ejecutar(contexto, "obtener_vacante", vacante_id=1)
        assert resultado.es_error and datos["error"] == "Error interno al ejecutar la herramienta."

    def test_resultados_en_json_con_acentos_legibles(self, contexto, vacantes):
        resultado, _ = ejecutar(contexto, "obtener_vacante", vacante_id=Vacante.objects.get(titulo="Analista de Datos Trainee").id)
        assert "Estadística" in resultado.contenido


def test_definiciones_de_herramientas():
    nombres = [h.nombre for h in HERRAMIENTAS_AGENTE]
    assert nombres == ["buscar_vacantes", "obtener_vacante", "calcular_match", HERRAMIENTA_FINAL]
    for herramienta in HERRAMIENTAS_AGENTE:
        assert herramienta.esquema["type"] == "object"
        assert herramienta.esquema["additionalProperties"] is False
        assert herramienta.descripcion
