"""Pruebas de los modelos Analisis y ResultadoMatch (T18)."""

import pytest
from django.urls import reverse

from analisis.models import Analisis, ResultadoMatch
from tests.datos import perfil_valido, recomendaciones_validas
from vacantes.models import Vacante

pytestmark = pytest.mark.django_db


def crear_vacante(titulo="Backend Jr") -> Vacante:
    return Vacante.objects.create(
        titulo=titulo, empresa="Nubeterna (ficticia)", ubicacion="GDL", modalidad="remoto", nivel="jr",
        habilidades_requeridas=["Python"], descripcion="(ficticia)",
    )


def crear_analisis(**cambios) -> Analisis:
    datos = {
        "origen_cv": "pdf", "perfil": perfil_valido(), "recomendaciones": recomendaciones_validas(),
        "proveedor": "anthropic", "modelo": "claude-haiku-5-5",
    }
    return Analisis.objects.create(**{**datos, **cambios})


def crear_resultado(analisis, posicion, vacante=None, **cambios) -> ResultadoMatch:
    datos = {
        "analisis": analisis, "vacante": vacante, "posicion": posicion,
        "titulo": vacante.titulo if vacante else "Externa", "empresa": vacante.empresa if vacante else "",
        "puntaje_determinista": 60, "puntaje_llm": 70, "puntaje_final": 64, "explicacion": "ok",
    }
    return ResultadoMatch.objects.create(**{**datos, **cambios})


def test_crear_analisis_con_valores_por_defecto():
    analisis = crear_analisis()
    assert analisis.creado is not None
    assert analisis.resultado_parcial is False
    assert analisis.vacante_externa is None
    assert analisis.nivel == "jr"
    assert not analisis.es_demo


def test_resultados_ordenados_por_posicion_y_externa_al_final():
    analisis = crear_analisis()
    crear_resultado(analisis, 2, crear_vacante("B"))
    crear_resultado(analisis, 1, None, es_externa=True)
    crear_resultado(analisis, 1, crear_vacante("A"))
    assert [r.titulo for r in analisis.resultados.all()] == ["A", "B", "Externa"]
    assert [r.titulo for r in analisis.resultados_catalogo()] == ["A", "B"]
    assert analisis.resultado_externo().titulo == "Externa"
    assert analisis.mejor_resultado().titulo == "A"


def test_borrar_la_vacante_conserva_el_resultado():
    analisis = crear_analisis()
    vacante = crear_vacante()
    resultado = crear_resultado(analisis, 1, vacante)
    vacante.delete()
    resultado.refresh_from_db()
    assert resultado.vacante is None
    assert resultado.titulo == "Backend Jr"


def test_borrar_el_analisis_borra_sus_resultados():
    analisis = crear_analisis()
    crear_resultado(analisis, 1, crear_vacante())
    analisis.delete()
    assert ResultadoMatch.objects.count() == 0


def test_historial_del_mas_reciente_al_mas_antiguo():
    primero, segundo = crear_analisis(), crear_analisis()
    assert list(Analisis.objects.all()) == [segundo, primero]


def test_str():
    analisis = crear_analisis(proveedor="demo")
    assert str(analisis).startswith(f"Análisis #{analisis.pk} · jr")
    assert analisis.es_demo


class TestAdmin:
    def test_lista_y_detalle_de_solo_lectura(self, admin_client):
        analisis = crear_analisis()
        crear_resultado(analisis, 1, crear_vacante())
        assert admin_client.get(reverse("admin:analisis_analisis_changelist")).status_code == 200
        detalle = admin_client.get(reverse("admin:analisis_analisis_change", args=[analisis.pk]))
        assert detalle.status_code == 200
        assert 'name="proveedor"' not in detalle.content.decode()  # sin campos editables

    def test_no_se_pueden_crear_desde_el_admin(self, admin_client):
        assert admin_client.get(reverse("admin:analisis_analisis_add")).status_code == 403
