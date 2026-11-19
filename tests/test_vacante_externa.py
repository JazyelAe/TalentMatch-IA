"""Pruebas de la vacante pegada por el usuario (T17)."""

import pytest

from services.esquemas import PerfilCV, VacanteEstructurada
from services.llm import RespuestaInvalidaError
from services.proveedores.proveedor_demo import ProveedorDemo, vacante_heuristica
from services.vacante_externa import (
    SISTEMA_VACANTE,
    VacanteExternaInvalidaError,
    estructurar_vacante,
    match_vacante_externa,
)
from tests.datos import perfil_valido
from tests.falsos import ProveedorFalso
from vacantes.models import Vacante

TEXTO_VACANTE = """Desarrollador Backend Python Jr
Empresa: Logística Real S.A. — Modalidad híbrida en Monterrey.
Requisitos: 1 a 2 años de experiencia con Python, Django y PostgreSQL. Uso de Git.
Deseable: Docker y AWS.
"""

VACANTE_LLM = {
    "titulo": "Desarrollador Backend Python Jr", "empresa": "Logística Real S.A.", "nivel": "jr",
    "modalidad": "hibrido", "habilidades_requeridas": ["Python", "Django", "PostgreSQL", "Git"],
    "habilidades_deseables": ["Docker", "AWS"], "descripcion": "Backend para logística.",
}


class TestEstructurarVacante:
    def test_con_el_llm(self):
        falso = ProveedorFalso(estructuradas=[VACANTE_LLM])
        vacante = estructurar_vacante(TEXTO_VACANTE, falso)
        assert vacante.empresa == "Logística Real S.A."
        assert falso.llamadas[0]["sistema"] == SISTEMA_VACANTE
        assert "<vacante>" in falso.llamadas[0]["mensaje"]

    def test_reintenta_una_vez(self):
        falso = ProveedorFalso(estructuradas=[{"titulo": "x"}, VACANTE_LLM])
        assert estructurar_vacante(TEXTO_VACANTE, falso).nivel == "jr"

    def test_dos_respuestas_invalidas(self):
        falso = ProveedorFalso(estructuradas=[{"x": 1}, {"y": 2}])
        with pytest.raises(RespuestaInvalidaError):
            estructurar_vacante(TEXTO_VACANTE, falso)

    @pytest.mark.parametrize("texto", ["", "   ", "Python Django"])
    def test_texto_muy_corto(self, texto):
        with pytest.raises(VacanteExternaInvalidaError, match="muy corto"):
            estructurar_vacante(texto, ProveedorFalso())

    def test_texto_muy_largo(self):
        with pytest.raises(VacanteExternaInvalidaError, match="supera"):
            estructurar_vacante("a" * 15_001, ProveedorFalso())

    @pytest.mark.django_db
    def test_no_se_agrega_al_catalogo(self):
        antes = Vacante.objects.count()
        estructurar_vacante(TEXTO_VACANTE, ProveedorDemo())
        assert Vacante.objects.count() == antes


class TestHeuristicaDemo:
    def test_estructura_la_vacante(self):
        vacante = vacante_heuristica(TEXTO_VACANTE)
        assert isinstance(vacante, VacanteEstructurada)
        assert vacante.titulo == "Desarrollador Backend Python Jr"
        assert vacante.nivel == "jr"
        assert vacante.modalidad == "hibrido"
        assert vacante.habilidades_requeridas == ["Python", "Django", "PostgreSQL", "Git"]
        assert vacante.habilidades_deseables == ["Docker", "AWS"]

    @pytest.mark.parametrize(
        "texto, nivel, modalidad",
        [
            ("Practicante de desarrollo, Python, 100% remoto", "trainee", "remoto"),
            ("Senior Java developer, presencial", "mid", "presencial"),
            ("Ingeniero de datos con 4 años de experiencia en SQL", "mid", "desconocida"),
        ],
    )
    def test_nivel_y_modalidad(self, texto, nivel, modalidad):
        vacante = vacante_heuristica(texto)
        assert (vacante.nivel, vacante.modalidad) == (nivel, modalidad)

    def test_sin_habilidades_reconocibles(self):
        with pytest.raises(RespuestaInvalidaError) as info:
            vacante_heuristica("Buscamos a alguien con muchas ganas de aprender y buena actitud.")
        assert "No reconocimos" in info.value.mensaje_usuario


def test_match_usa_el_mismo_puntaje_que_el_catalogo():
    perfil = PerfilCV.model_validate(perfil_valido())
    vacante = VacanteEstructurada.model_validate(VACANTE_LLM)
    resultado = match_vacante_externa(perfil, vacante)
    # Python, Django y Git de 4 requeridas (sin PostgreSQL) = 0.75·0.8; 0 de 2 deseables → 60
    assert resultado.puntaje == 60.0
    assert resultado.faltantes_requeridas == ["PostgreSQL"]
