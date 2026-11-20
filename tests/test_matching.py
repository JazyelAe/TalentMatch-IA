"""Pruebas del puntaje determinista y de la combinación de puntajes (T07)."""

import pytest

from services.matching import calcular_match_determinista, combinar_puntajes

REQUERIDAS = ["Python", "Django", "SQL", "Git"]
DESEABLES = ["Docker", "PostgreSQL"]


class TestCalcularMatchDeterminista:
    def test_coincidencia_total(self):
        r = calcular_match_determinista(REQUERIDAS + DESEABLES, REQUERIDAS, DESEABLES)
        assert r.puntaje == 100.0
        assert r.faltantes == []

    def test_sin_coincidencias(self):
        r = calcular_match_determinista(["Java", "Spring Boot"], REQUERIDAS, DESEABLES)
        assert r.puntaje == 0.0
        assert r.coincidentes == []
        assert r.faltantes_requeridas == REQUERIDAS
        assert r.faltantes_deseables == DESEABLES

    def test_coincidencia_parcial_usa_la_formula_80_20(self):
        # 2 de 4 requeridas (0.5) y 1 de 2 deseables (0.5) → 100 × (0.8·0.5 + 0.2·0.5) = 50
        r = calcular_match_determinista(["Python", "SQL", "Docker"], REQUERIDAS, DESEABLES)
        assert r.puntaje == 50.0
        assert r.coincidentes == ["Python", "SQL", "Docker"]
        assert r.faltantes_requeridas == ["Django", "Git"]
        assert r.faltantes_deseables == ["PostgreSQL"]

    def test_solo_deseables_vale_maximo_20(self):
        r = calcular_match_determinista(["Docker", "PostgreSQL"], REQUERIDAS, DESEABLES)
        assert r.puntaje == 20.0

    def test_sin_deseables_las_requeridas_valen_100(self):
        r = calcular_match_determinista(["Python", "Django"], REQUERIDAS, [])
        assert r.puntaje == 50.0

    def test_sin_requeridas_las_deseables_valen_100(self):
        assert calcular_match_determinista(["Docker"], [], DESEABLES).puntaje == 50.0

    def test_vacante_sin_habilidades_da_cero(self):
        assert calcular_match_determinista(["Python"], [], []).puntaje == 0.0

    def test_usa_la_normalizacion(self):
        r = calcular_match_determinista(["python3", "django", "postgres", "git"], REQUERIDAS, DESEABLES)
        assert "PostgreSQL" in r.coincidentes
        assert r.faltantes_requeridas == ["SQL"]

    def test_conserva_los_nombres_de_la_vacante(self):
        r = calcular_match_determinista(["reactjs"], ["React.js"], [])
        assert r.coincidentes == ["React.js"]

    def test_duplicados_en_la_vacante_no_cuentan_doble(self):
        r = calcular_match_determinista(["Python"], ["Python", "python3", "SQL"], [])
        assert r.puntaje == 50.0

    def test_habilidad_en_ambas_listas_cuenta_como_requerida(self):
        r = calcular_match_determinista(["Python"], ["Python"], ["Python", "Docker"])
        assert r.faltantes_deseables == ["Docker"]
        assert r.puntaje == 80.0

    def test_mismo_input_mismo_output(self):
        """HU-03: el puntaje determinista es reproducible."""
        resultados = [calcular_match_determinista(["Git", "Python"], REQUERIDAS, DESEABLES) for _ in range(5)]
        assert all(r == resultados[0] for r in resultados)
        # El orden del perfil tampoco cambia el resultado.
        assert calcular_match_determinista(["Python", "Git"], REQUERIDAS, DESEABLES) == resultados[0]

    def test_redondea_a_un_decimal(self):
        # 1 de 3 requeridas, sin deseables → 33.333… → 33.3
        assert calcular_match_determinista(["Python"], ["Python", "Go", "Rust"], []).puntaje == 33.3


class TestCombinarPuntajes:
    def test_peso_por_defecto_60_40(self):
        assert combinar_puntajes(80, 50, 0.6) == 68.0

    @pytest.mark.parametrize("peso, esperado", [(1.0, 80.0), (0.0, 50.0), (0.5, 65.0)])
    def test_peso_configurable(self, peso, esperado):
        assert combinar_puntajes(80, 50, peso) == esperado

    def test_limita_valores_fuera_de_rango(self):
        assert combinar_puntajes(150, -20, 0.5) == 50.0

    @pytest.mark.parametrize("peso", [-0.1, 1.1])
    def test_peso_invalido(self, peso):
        with pytest.raises(ValueError, match="entre 0 y 1"):
            combinar_puntajes(50, 50, peso)
