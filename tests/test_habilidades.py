"""Pruebas de la normalización de habilidades (T06)."""

import pytest

from services.habilidades import SINONIMOS, normalizar, normalizar_lista
from vacantes.management.commands.cargar_vacantes_ejemplo import leer_vacantes_ejemplo


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        # Variantes del mismo framework
        ("React", "react"),
        ("React.js", "react"),
        ("ReactJS", "react"),
        ("react js", "react"),
        ("Node.js", "node.js"),
        ("NodeJS", "node.js"),
        ("node", "node.js"),
        ("Vue.js", "vue.js"),
        ("Next.js", "next.js"),
        # Abreviaturas
        ("JS", "javascript"),
        ("TS", "typescript"),
        ("Postgres", "postgresql"),
        ("PostgreSQL", "postgresql"),
        ("DRF", "django rest framework"),
        ("Django REST Framework", "django rest framework"),
        ("K8s", "kubernetes"),
        ("CI/CD", "ci/cd"),
        ("CI-CD", "ci/cd"),
        ("ML", "machine learning"),
        ("sklearn", "scikit-learn"),
        ("Scikit-learn", "scikit-learn"),
        ("API REST", "apis rest"),
        ("APIs RESTful", "apis rest"),
        ("Tailwind", "tailwind css"),
        ("HTML5", "html"),
        # Símbolos con significado: no se pierden
        ("C#", "c#"),
        ("C++", "c++"),
        ("c sharp", "c#"),
        (".NET", ".net"),
        ("dotnet", ".net"),
        # Acentos, mayúsculas, espacios y puntuación sobrante
        ("Programación", "programacion"),
        ("Estadística", "estadistica"),
        ("  Trabajo   en  EQUIPO ", "trabajo en equipo"),
        ("Python,", "python"),
        ("• Git", "git"),
        ("(Docker)", "docker"),
        # Sin sinónimo: se queda en su forma base
        ("Flutter", "flutter"),
        ("Spring Boot", "spring boot"),
    ],
)
def test_normalizar(entrada, esperado):
    assert normalizar(entrada) == esperado


@pytest.mark.parametrize("entrada", ["", "   ", "...", "•", None, 42])
def test_entradas_vacias_o_invalidas_dan_texto_vacio(entrada):
    assert normalizar(entrada) == ""


def test_c_sharp_y_c_plus_plus_son_distintos_de_c():
    assert len({normalizar("C"), normalizar("C#"), normalizar("C++")}) == 3


@pytest.mark.parametrize("canonica", sorted(set(SINONIMOS.values())))
def test_formas_canonicas_son_idempotentes(canonica):
    """Normalizar dos veces da lo mismo: así no importa si un dato ya venía normalizado."""
    assert normalizar(canonica) == canonica


def test_habilidades_de_las_vacantes_de_ejemplo_son_idempotentes():
    for vacante in leer_vacantes_ejemplo():
        for habilidad in vacante["habilidades_requeridas"] + vacante["habilidades_deseables"]:
            una_vez = normalizar(habilidad)
            assert una_vez, f"{habilidad!r} quedó vacía"
            assert normalizar(una_vez) == una_vez


class TestNormalizarLista:
    def test_quita_duplicados_tras_normalizar_y_conserva_el_orden(self):
        assert normalizar_lista(["Python", "React.js", "python3", "ReactJS", "SQL"]) == ["python", "react", "sql"]

    def test_quita_vacios(self):
        assert normalizar_lista(["", "  ", "Git"]) == ["git"]

    def test_lista_vacia(self):
        assert normalizar_lista([]) == []

    def test_acepta_cualquier_iterable(self):
        assert normalizar_lista(h for h in ["JS", "TS"]) == ["javascript", "typescript"]
