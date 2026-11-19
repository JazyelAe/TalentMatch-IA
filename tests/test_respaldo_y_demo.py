"""Pruebas del respaldo determinista y del agente en modo demo (T16)."""

import pytest
from django.core.management import call_command

from services.agente import ejecutar_agente
from services.esquemas import PerfilCV, Recomendaciones, VacanteEstructurada
from services.matching import calcular_match_determinista
from services.perfil import extraer_perfil
from services.proveedores.proveedor_demo import ProveedorDemo, puntaje_simulado
from services.respaldo import construir_brechas, recomendaciones_de_respaldo
from tests.archivos_cv import TEXTO_CV
from tests.datos import perfil_valido
from vacantes.models import Vacante

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalogo():
    call_command("cargar_vacantes_ejemplo")


@pytest.fixture
def perfil():
    return PerfilCV.model_validate(perfil_valido())


class TestRespaldo:
    def test_top_5_ordenado_por_puntaje_determinista(self, catalogo, perfil):
        r = recomendaciones_de_respaldo(perfil)
        assert isinstance(r, Recomendaciones)
        assert len(r.top_vacantes) == 5
        puntajes = [e.puntaje_llm for e in r.top_vacantes]
        assert puntajes == sorted(puntajes, reverse=True)
        mejor = Vacante.objects.get(pk=r.top_vacantes[0].vacante_id)
        assert "Python" in mejor.habilidades_requeridas

    def test_incluye_brechas_sugerencias_y_palabras_ats(self, catalogo, perfil):
        r = recomendaciones_de_respaldo(perfil)
        assert 1 <= len(r.brechas) <= 5
        assert 3 <= len(r.sugerencias_cv) <= 6
        assert r.palabras_clave_ats

    def test_evalua_la_vacante_externa_si_existe(self, catalogo, perfil):
        match = calcular_match_determinista(perfil.habilidades_tecnicas, ["Python", "FastAPI"])
        r = recomendaciones_de_respaldo(perfil, match_externo=match)
        assert r.vacante_externa.puntaje_llm == 50

    def test_sin_vacantes_activas_lanza_error(self, catalogo, perfil):
        Vacante.objects.update(activa=False)
        with pytest.raises(ValueError, match="No hay vacantes"):
            recomendaciones_de_respaldo(perfil)


class TestConstruirBrechas:
    def test_prioriza_por_frecuencia(self, perfil):
        brechas = construir_brechas([["Docker", "AWS"], ["Docker"], ["docker", "Redis"]], perfil)
        assert brechas[0].habilidad == "Docker"
        assert brechas[0].prioridad == "alta"
        assert {b.prioridad for b in brechas[1:]} == {"baja"}

    def test_perfil_sin_brechas_recibe_una_de_profundizacion(self, perfil):
        brechas = construir_brechas([[], []], perfil)
        assert len(brechas) == 1 and "avanzado" in brechas[0].habilidad


class TestPuntajeSimulado:
    @pytest.mark.parametrize(
        "det, perfil, vacante, esperado",
        [(60, "jr", "jr", 70), (60, "jr", "mid", 60), (60, "trainee", "mid", 45), (95, "mid", "mid", 100), (5, "trainee", "mid", 0)],
    )
    def test_ajusta_por_nivel(self, det, perfil, vacante, esperado):
        assert puntaje_simulado(det, perfil, vacante) == esperado


class TestAgenteDemo:
    def test_el_agente_demo_entrega_sin_red(self, catalogo):
        perfil = extraer_perfil(TEXTO_CV, ProveedorDemo())
        resultado = ejecutar_agente(perfil, ProveedorDemo())
        assert resultado.iteraciones == 3
        assert 1 <= len(resultado.recomendaciones.top_vacantes) <= 5
        assert all("modo demo" in e.explicacion for e in resultado.recomendaciones.top_vacantes)

    def test_el_agente_demo_evalua_la_vacante_externa(self, catalogo):
        perfil = extraer_perfil(TEXTO_CV, ProveedorDemo())
        externa = VacanteEstructurada(
            titulo="Backend", empresa="", nivel="jr", modalidad="remoto",
            habilidades_requeridas=["Python", "FastAPI"], habilidades_deseables=[], descripcion="",
        )
        match = calcular_match_determinista(perfil.habilidades_tecnicas, externa.habilidades_requeridas)
        resultado = ejecutar_agente(perfil, ProveedorDemo(), vacante_externa=externa, match_externo=match)
        assert "FastAPI" in resultado.recomendaciones.vacante_externa.explicacion
