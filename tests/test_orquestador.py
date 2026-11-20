"""Pruebas del orquestador del análisis completo (T19)."""

import pytest
from django.core.management import call_command

from analisis.models import Analisis, ResultadoMatch
from services.herramientas import HERRAMIENTA_FINAL
from services.llm import ConexionLLMError, LlamadaHerramienta, RespuestaLLM
from services.orquestador import CatalogoVacioError, analizar_cv
from services.proveedores.proveedor_demo import ProveedorDemo
from tests.archivos_cv import TEXTO_CV
from tests.datos import perfil_valido, recomendaciones_validas
from tests.falsos import ProveedorFalso
from vacantes.models import Vacante

pytestmark = pytest.mark.django_db

TEXTO_VACANTE = "Backend Python Jr\nRequisitos: Python, Django y FastAPI. Modalidad remota.\nDeseable: Docker."
VACANTE_LLM = {
    "titulo": "Backend Python Jr", "empresa": "", "nivel": "jr", "modalidad": "remoto",
    "habilidades_requeridas": ["Python", "Django", "FastAPI"], "habilidades_deseables": ["Docker"], "descripcion": "",
}


@pytest.fixture
def ids():
    call_command("cargar_vacantes_ejemplo")
    backend = Vacante.objects.get(titulo="Desarrollador Backend Python Jr").id
    movil = Vacante.objects.get(titulo="Desarrollador Móvil Flutter Jr").id
    return backend, movil


def entrega(datos) -> RespuestaLLM:
    return RespuestaLLM(llamadas=[LlamadaHerramienta("t1", HERRAMIENTA_FINAL, datos)], razon_fin="herramientas")


def test_flujo_completo_con_proveedor_falso(settings, ids):
    settings.MATCH_PESO_DETERMINISTA = 0.6
    backend, movil = ids
    datos = recomendaciones_validas(ids=(movil, backend))  # el LLM los da en otro orden
    datos["top_vacantes"][0]["puntaje_llm"] = 40  # móvil
    datos["top_vacantes"][1]["puntaje_llm"] = 90  # backend
    falso = ProveedorFalso(estructuradas=[perfil_valido()], chats=[entrega(datos)])

    analisis = analizar_cv(TEXTO_CV, "pdf", proveedor=falso)

    assert analisis.proveedor == "falso" and analisis.modelo == "modelo-falso"
    assert analisis.origen_cv == "pdf"
    assert analisis.resultado_parcial is False
    assert analisis.iteraciones_agente == 1
    assert set(analisis.recomendaciones) == {"brechas", "sugerencias_cv", "palabras_clave_ats"}
    resultados = list(analisis.resultados_catalogo())
    assert [r.vacante_id for r in resultados] == [backend, movil]  # ordenados por puntaje final

    mejor = resultados[0]
    # Perfil: Python, Django, SQL, Git… → backend jr: 4/5 requeridas, 0/3 deseables = 64
    assert mejor.puntaje_determinista == 64.0
    assert mejor.puntaje_llm == 90
    assert mejor.puntaje_final == round(0.6 * 64 + 0.4 * 90, 1)
    assert mejor.habilidades_faltantes[0] == "APIs REST"


def test_no_guarda_el_texto_del_cv(ids):
    falso = ProveedorFalso(estructuradas=[perfil_valido()], chats=[entrega(recomendaciones_validas(ids=ids))])
    analisis = analizar_cv(TEXTO_CV, "texto", proveedor=falso)
    guardado = str(Analisis.objects.filter(pk=analisis.pk).values().first())
    assert "logistica" not in guardado.lower()  # frase del CV que no está en el perfil


def test_vacante_externa(ids):
    externa = {"puntaje_llm": 80, "explicacion": "Te falta FastAPI."}
    datos = {**recomendaciones_validas(ids=ids), "vacante_externa": externa}
    falso = ProveedorFalso(estructuradas=[perfil_valido(), VACANTE_LLM], chats=[entrega(datos)])

    analisis = analizar_cv(TEXTO_CV, "pdf", texto_vacante=TEXTO_VACANTE, proveedor=falso)

    resultado = analisis.resultado_externo()
    assert resultado.vacante is None and resultado.es_externa
    assert resultado.titulo == "Backend Python Jr"
    # Python y Django de 3 requeridas (0.8·2/3) + 0 de 1 deseable → 53.3
    assert resultado.puntaje_determinista == 53.3
    assert resultado.habilidades_faltantes == ["FastAPI", "Docker"]
    assert analisis.vacante_externa["titulo"] == "Backend Python Jr"
    assert Vacante.objects.count() == 20  # no se agregó al catálogo


def test_respaldo_si_el_agente_no_entrega(settings, ids):
    settings.AGENTE_MAX_ITERACIONES = 2
    sin_entrega = RespuestaLLM(texto="No sé.")
    falso = ProveedorFalso(estructuradas=[perfil_valido()], chats=[sin_entrega, sin_entrega])
    analisis = analizar_cv(TEXTO_CV, "pdf", proveedor=falso)
    assert analisis.resultado_parcial is True
    assert analisis.resultados_catalogo().count() == 5
    # Sin evaluación del LLM, el puntaje final coincide con el determinista.
    assert all(r.puntaje_final == pytest.approx(r.puntaje_determinista, abs=0.5) for r in analisis.resultados.all())


def test_un_fallo_del_llm_a_medias_no_guarda_nada(ids):
    falso = ProveedorFalso(estructuradas=[perfil_valido()], chats=[ConexionLLMError("caída")])
    with pytest.raises(ConexionLLMError):
        analizar_cv(TEXTO_CV, "pdf", proveedor=falso)
    assert Analisis.objects.count() == 0 and ResultadoMatch.objects.count() == 0


def test_catalogo_vacio():
    with pytest.raises(CatalogoVacioError):
        analizar_cv(TEXTO_CV, "pdf", proveedor=ProveedorFalso())


def test_modo_demo_de_punta_a_punta(ids):
    analisis = analizar_cv(TEXTO_CV, "texto", texto_vacante=TEXTO_VACANTE, proveedor=ProveedorDemo())
    assert analisis.es_demo
    assert 1 <= analisis.resultados_catalogo().count() <= 5
    assert analisis.resultado_externo() is not None
    assert analisis.recomendaciones["brechas"]


def test_usa_el_proveedor_configurado_si_no_se_pasa_uno(settings, ids):
    settings.ANTHROPIC_API_KEY = ""  # sin key → demo
    assert analizar_cv(TEXTO_CV, "texto").proveedor == "demo"
