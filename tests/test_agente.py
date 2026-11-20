"""Pruebas del ciclo del agente con un proveedor falso (T15)."""

import json

import pytest
from django.core.management import call_command

from services.agente import AgenteSinResultadoError, SISTEMA_AGENTE, construir_mensaje_inicial, ejecutar_agente
from services.esquemas import PerfilCV, VacanteEstructurada
from services.herramientas import HERRAMIENTA_FINAL
from services.llm import LimiteApiError, LlamadaHerramienta, MensajeAsistente, MensajeResultados, MensajeUsuario, RespuestaLLM
from services.matching import calcular_match_determinista
from tests.datos import perfil_valido, recomendaciones_validas
from tests.falsos import ProveedorFalso
from vacantes.models import Vacante

pytestmark = pytest.mark.django_db


@pytest.fixture
def perfil():
    return PerfilCV.model_validate(perfil_valido())


@pytest.fixture
def ids():
    call_command("cargar_vacantes_ejemplo")
    return list(Vacante.objects.order_by("id").values_list("id", flat=True)[:3])


def pide(*llamadas: tuple[str, dict]) -> RespuestaLLM:
    return RespuestaLLM(
        llamadas=[LlamadaHerramienta(f"t{i}", nombre, args) for i, (nombre, args) in enumerate(llamadas)],
        razon_fin="herramientas",
    )


def entrega(datos: dict) -> RespuestaLLM:
    return pide((HERRAMIENTA_FINAL, datos))


BUSCAR = ("buscar_vacantes", {"nivel": "jr", "modalidad": None, "habilidades": ["Python"], "limite": 5})


class TestCicloFeliz:
    def test_tres_iteraciones_hasta_entregar(self, perfil, ids):
        falso = ProveedorFalso(chats=[
            pide(BUSCAR),
            pide(("calcular_match", {"vacante_id": ids[0]}), ("calcular_match", {"vacante_id": ids[1]})),
            entrega(recomendaciones_validas(ids=(ids[0], ids[1]))),
        ])
        resultado = ejecutar_agente(perfil, falso)
        assert resultado.iteraciones == 3
        assert [e.vacante_id for e in resultado.recomendaciones.top_vacantes] == [ids[0], ids[1]]

    def test_envia_sistema_herramientas_y_perfil(self, perfil, ids):
        falso = ProveedorFalso(chats=[entrega(recomendaciones_validas(ids=(ids[0],)))])
        ejecutar_agente(perfil, falso)
        llamada = falso.llamadas[0]
        assert llamada["sistema"] == SISTEMA_AGENTE
        assert [h.nombre for h in llamada["herramientas"]][-1] == HERRAMIENTA_FINAL
        assert "<perfil>" in llamada["mensajes"][0].texto

    def test_varias_llamadas_en_un_turno_devuelven_todos_los_resultados_juntos(self, perfil, ids):
        falso = ProveedorFalso(chats=[
            pide(("calcular_match", {"vacante_id": ids[0]}), ("obtener_vacante", {"vacante_id": ids[1]})),
            entrega(recomendaciones_validas(ids=(ids[0],))),
        ])
        ejecutar_agente(perfil, falso)
        historial = falso.llamadas[1]["mensajes"]
        assert isinstance(historial[1], MensajeAsistente)
        assert isinstance(historial[2], MensajeResultados)
        assert [r.llamada_id for r in historial[2].resultados] == ["t0", "t1"]
        assert json.loads(historial[2].resultados[0].contenido)["vacante_id"] == ids[0]


class TestErroresYLimites:
    def test_herramienta_con_error_no_detiene_el_ciclo(self, perfil, ids):
        falso = ProveedorFalso(chats=[
            pide(("obtener_vacante", {"vacante_id": 99999})),
            entrega(recomendaciones_validas(ids=(ids[0],))),
        ])
        resultado = ejecutar_agente(perfil, falso)
        resultado_herramienta = falso.llamadas[1]["mensajes"][2].resultados[0]
        assert resultado_herramienta.es_error
        assert resultado.iteraciones == 2

    def test_limite_de_iteraciones(self, perfil, ids):
        falso = ProveedorFalso(chats=[pide(BUSCAR)] * 3)
        with pytest.raises(AgenteSinResultadoError, match="límite de 3"):
            ejecutar_agente(perfil, falso, max_iteraciones=3)
        assert len(falso.llamadas) == 3

    def test_entrega_invalida_se_corrige_una_vez(self, perfil, ids):
        invalida = recomendaciones_validas(ids=(ids[0],))
        invalida["top_vacantes"][0]["puntaje_llm"] = 150
        falso = ProveedorFalso(chats=[entrega(invalida), entrega(recomendaciones_validas(ids=(ids[0],)))])
        resultado = ejecutar_agente(perfil, falso)
        error = falso.llamadas[1]["mensajes"][2].resultados[0]
        assert error.es_error and "puntaje_llm" in error.contenido
        assert resultado.iteraciones == 2

    def test_dos_entregas_invalidas_lanzan_error(self, perfil, ids):
        invalida = recomendaciones_validas(ids=(ids[0],))
        invalida["sugerencias_cv"] = []
        falso = ProveedorFalso(chats=[entrega(invalida), entrega(invalida)])
        with pytest.raises(AgenteSinResultadoError, match="dos veces"):
            ejecutar_agente(perfil, falso)

    def test_ids_inexistentes_en_la_entrega_son_invalidos(self, perfil, ids):
        falso = ProveedorFalso(chats=[
            entrega(recomendaciones_validas(ids=(99999,))),
            entrega(recomendaciones_validas(ids=(ids[0],))),
        ])
        ejecutar_agente(perfil, falso)
        assert "99999" in falso.llamadas[1]["mensajes"][2].resultados[0].contenido

    def test_terminar_sin_entregar_recibe_un_recordatorio(self, perfil, ids):
        falso = ProveedorFalso(chats=[RespuestaLLM(texto="Listo, eso es todo."), entrega(recomendaciones_validas(ids=(ids[0],)))])
        ejecutar_agente(perfil, falso)
        recordatorio = falso.llamadas[1]["mensajes"][-1]
        assert isinstance(recordatorio, MensajeUsuario) and HERRAMIENTA_FINAL in recordatorio.texto

    def test_terminar_dos_veces_sin_entregar_lanza_error(self, perfil, ids):
        falso = ProveedorFalso(chats=[RespuestaLLM(texto="a"), RespuestaLLM(texto="b", razon_fin="limite_tokens")])
        with pytest.raises(AgenteSinResultadoError):
            ejecutar_agente(perfil, falso)

    def test_errores_del_llm_se_propagan(self, perfil, ids):
        with pytest.raises(LimiteApiError):
            ejecutar_agente(perfil, ProveedorFalso(chats=[LimiteApiError("429")]))


class TestVacanteExterna:
    @pytest.fixture
    def externa(self):
        return VacanteEstructurada(
            titulo="Backend Python", empresa="Real S.A.", nivel="jr", modalidad="remoto",
            habilidades_requeridas=["Python", "FastAPI"], habilidades_deseables=[], descripcion="",
        )

    def test_mensaje_inicial_incluye_la_vacante_y_su_match(self, perfil, externa):
        match = calcular_match_determinista(perfil.habilidades_tecnicas, externa.habilidades_requeridas)
        mensaje = construir_mensaje_inicial(perfil, externa, match)
        assert "<vacante_externa>" in mensaje
        assert '"puntaje_determinista": 50.0' in mensaje

    def test_exige_evaluar_la_vacante_externa(self, perfil, ids, externa):
        sin_externa = recomendaciones_validas(ids=(ids[0],))
        con_externa = {**sin_externa, "vacante_externa": {"puntaje_llm": 60, "explicacion": "Te falta FastAPI."}}
        falso = ProveedorFalso(chats=[entrega(sin_externa), entrega(con_externa)])
        resultado = ejecutar_agente(perfil, falso, vacante_externa=externa)
        assert resultado.recomendaciones.vacante_externa.puntaje_llm == 60

    def test_sin_vacante_externa_se_ignora_la_evaluacion_inventada(self, perfil, ids):
        datos = {**recomendaciones_validas(ids=(ids[0],)), "vacante_externa": {"puntaje_llm": 60, "explicacion": "x"}}
        resultado = ejecutar_agente(perfil, ProveedorFalso(chats=[entrega(datos)]))
        assert resultado.recomendaciones.vacante_externa is None
