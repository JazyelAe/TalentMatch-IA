"""Pruebas de los esquemas Pydantic (T09)."""

import pytest
from pydantic import ValidationError

from services.esquemas import (
    Brecha,
    PerfilCV,
    Recomendaciones,
    VacanteEstructurada,
    esquema_json_estricto,
)
from tests.datos import perfil_valido, recomendaciones_validas


class TestPerfilCV:
    def test_acepta_un_perfil_valido(self):
        perfil = PerfilCV.model_validate(perfil_valido())
        assert perfil.nivel_estimado == "jr"

    def test_rechaza_nivel_fuera_de_rango(self):
        with pytest.raises(ValidationError, match="nivel_estimado"):
            PerfilCV.model_validate(perfil_valido(nivel_estimado="senior"))

    def test_rechaza_campos_extra(self):
        with pytest.raises(ValidationError, match="Extra inputs"):
            PerfilCV.model_validate({**perfil_valido(), "edad": 25})

    def test_rechaza_campos_faltantes(self):
        datos = perfil_valido()
        del datos["habilidades_tecnicas"]
        with pytest.raises(ValidationError, match="habilidades_tecnicas"):
            PerfilCV.model_validate(datos)

    def test_rechaza_anios_negativos(self):
        with pytest.raises(ValidationError):
            PerfilCV.model_validate(perfil_valido(anios_experiencia=-1))

    def test_limpia_habilidades_duplicadas_y_vacias(self):
        perfil = PerfilCV.model_validate(perfil_valido(habilidades_tecnicas=["Python", " python3 ", "", "React.js", "ReactJS"]))
        assert perfil.habilidades_tecnicas == ["Python", "React.js"]

    def test_resumen_no_puede_estar_vacio(self):
        with pytest.raises(ValidationError, match="resumen"):
            PerfilCV.model_validate(perfil_valido(resumen="   "))


class TestVacanteEstructurada:
    def datos(self, **cambios):
        base = {
            "titulo": "Backend Jr", "empresa": "", "nivel": "jr", "modalidad": "desconocida",
            "habilidades_requeridas": ["Python"], "habilidades_deseables": [], "descripcion": "",
        }
        return {**base, **cambios}

    def test_valida(self):
        assert VacanteEstructurada.model_validate(self.datos()).modalidad == "desconocida"

    def test_requiere_al_menos_una_habilidad(self):
        with pytest.raises(ValidationError, match="habilidades_requeridas"):
            VacanteEstructurada.model_validate(self.datos(habilidades_requeridas=[]))


class TestRecomendaciones:
    def test_acepta_recomendaciones_validas(self):
        r = Recomendaciones.model_validate(recomendaciones_validas())
        assert len(r.top_vacantes) == 2
        assert r.vacante_externa is None

    def test_rechaza_puntaje_mayor_a_100(self):
        datos = recomendaciones_validas()
        datos["top_vacantes"][0]["puntaje_llm"] = 150
        with pytest.raises(ValidationError, match="puntaje_llm"):
            Recomendaciones.model_validate(datos)

    def test_rechaza_mas_de_5_vacantes(self):
        datos = recomendaciones_validas()
        datos["top_vacantes"] = [{"vacante_id": i, "puntaje_llm": 50, "explicacion": "ok"} for i in range(6)]
        with pytest.raises(ValidationError, match="top_vacantes"):
            Recomendaciones.model_validate(datos)

    def test_rechaza_vacantes_repetidas(self):
        datos = recomendaciones_validas()
        datos["top_vacantes"][1]["vacante_id"] = datos["top_vacantes"][0]["vacante_id"]
        with pytest.raises(ValidationError, match="repetir"):
            Recomendaciones.model_validate(datos)

    @pytest.mark.parametrize("cantidad", [2, 7])
    def test_sugerencias_entre_3_y_6(self, cantidad):
        datos = recomendaciones_validas()
        datos["sugerencias_cv"] = [f"Sugerencia {i}" for i in range(cantidad)]
        with pytest.raises(ValidationError, match="sugerencias_cv"):
            Recomendaciones.model_validate(datos)

    def test_rechaza_mas_de_7_brechas(self):
        datos = recomendaciones_validas()
        datos["brechas"] = datos["brechas"] * 8
        with pytest.raises(ValidationError, match="brechas"):
            Recomendaciones.model_validate(datos)

    @pytest.mark.parametrize("pasos", [["solo uno"], ["1", "2", "3", "4", "5"]])
    def test_brecha_con_2_a_4_pasos(self, pasos):
        brecha = recomendaciones_validas()["brechas"][0]
        with pytest.raises(ValidationError, match="pasos"):
            Brecha.model_validate({**brecha, "pasos": pasos})

    def test_acepta_vacante_externa(self):
        datos = {**recomendaciones_validas(), "vacante_externa": {"puntaje_llm": 70, "explicacion": "Encajas bien."}}
        assert Recomendaciones.model_validate(datos).vacante_externa.puntaje_llm == 70


class TestEsquemaJsonEstricto:
    def recorrer(self, nodo):
        """Devuelve todos los diccionarios anidados del esquema."""
        if isinstance(nodo, dict):
            yield nodo
            for valor in nodo.values():
                yield from self.recorrer(valor)
        elif isinstance(nodo, list):
            for valor in nodo:
                yield from self.recorrer(valor)

    @pytest.mark.parametrize("modelo", [PerfilCV, VacanteEstructurada, Recomendaciones])
    def test_todos_los_objetos_son_estrictos(self, modelo):
        for nodo in self.recorrer(esquema_json_estricto(modelo)):
            if nodo.get("type") == "object" and "properties" in nodo:
                assert nodo["additionalProperties"] is False
                assert set(nodo["required"]) == set(nodo["properties"])

    @pytest.mark.parametrize("modelo", [PerfilCV, VacanteEstructurada, Recomendaciones])
    def test_quita_restricciones_no_soportadas(self, modelo):
        prohibidas = {"minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems"}
        for nodo in self.recorrer(esquema_json_estricto(modelo)):
            assert not prohibidas & set(nodo), nodo

    def test_conserva_los_enums(self):
        esquema = esquema_json_estricto(PerfilCV)
        assert esquema["properties"]["nivel_estimado"]["enum"] == ["trainee", "jr", "mid"]
