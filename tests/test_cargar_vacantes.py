"""Pruebas del comando cargar_vacantes_ejemplo y de sus datos (T05)."""

import json
from collections import Counter

import pytest
from django.core.management import CommandError, call_command

from vacantes.management.commands import cargar_vacantes_ejemplo as comando
from vacantes.models import Vacante

DATOS = comando.leer_vacantes_ejemplo()


class TestDatosDeEjemplo:
    def test_son_20_vacantes(self):
        assert len(DATOS) == 20

    def test_no_hay_titulo_y_empresa_repetidos(self):
        claves = Counter((v["titulo"], v["empresa"]) for v in DATOS)
        assert [clave for clave, veces in claves.items() if veces > 1] == []

    def test_niveles_y_modalidades_validos(self):
        assert {v["nivel"] for v in DATOS} <= set(Vacante.Nivel.values)
        assert {v["modalidad"] for v in DATOS} <= set(Vacante.Modalidad.values)

    def test_hay_mezcla_de_niveles_y_modalidades(self):
        """El catálogo debe servir para perfiles trainee, jr y mid, y para todas las modalidades."""
        assert {v["nivel"] for v in DATOS} == set(Vacante.Nivel.values)
        assert {v["modalidad"] for v in DATOS} == set(Vacante.Modalidad.values)

    def test_toda_vacante_pide_al_menos_tres_habilidades(self):
        assert all(len(v["habilidades_requeridas"]) >= 3 for v in DATOS)


@pytest.mark.django_db
class TestComando:
    def test_carga_20_vacantes(self, capsys):
        call_command("cargar_vacantes_ejemplo")
        assert Vacante.objects.count() == 20
        assert "20 creadas, 0 actualizadas" in capsys.readouterr().out

    def test_es_idempotente(self, capsys):
        call_command("cargar_vacantes_ejemplo")
        call_command("cargar_vacantes_ejemplo")
        assert Vacante.objects.count() == 20
        assert "0 creadas, 20 actualizadas" in capsys.readouterr().out

    def test_todas_dicen_ficticia(self):
        call_command("cargar_vacantes_ejemplo")
        assert all("(ficticia)" in d for d in Vacante.objects.values_list("descripcion", flat=True))

    def test_restaura_una_vacante_editada(self):
        """Volver a correrlo devuelve las vacantes de ejemplo a sus datos originales."""
        call_command("cargar_vacantes_ejemplo")
        vacante = Vacante.objects.get(titulo=DATOS[0]["titulo"], empresa=DATOS[0]["empresa"])
        vacante.ubicacion = "Cambiada"
        vacante.save()
        call_command("cargar_vacantes_ejemplo")
        vacante.refresh_from_db()
        assert vacante.ubicacion == DATOS[0]["ubicacion"]

    def test_no_toca_vacantes_creadas_a_mano(self):
        Vacante.objects.create(
            titulo="Vacante propia", empresa="Mi empresa", ubicacion="CDMX", modalidad="remoto",
            nivel="jr", habilidades_requeridas=["Python"], descripcion="Creada en el admin.",
        )
        call_command("cargar_vacantes_ejemplo")
        assert Vacante.objects.count() == 21

    def test_datos_invalidos_no_guardan_nada(self, monkeypatch):
        """Si una vacante del JSON es inválida, la carga se cancela completa (transacción)."""
        datos = json.loads(json.dumps(DATOS))  # copia profunda
        datos[5]["nivel"] = "senior"
        monkeypatch.setattr(comando, "leer_vacantes_ejemplo", lambda: datos)

        with pytest.raises(CommandError, match="#6"):
            call_command("cargar_vacantes_ejemplo")
        assert Vacante.objects.count() == 0
