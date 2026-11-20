"""Pruebas del modelo Vacante y su admin (T04)."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse

from vacantes.models import Vacante, validar_lista_de_habilidades


def crear_vacante(**cambios) -> Vacante:
    datos = {
        "titulo": "Desarrollador Python Jr",
        "empresa": "Nubeterna Labs (ficticia)",
        "ubicacion": "Guadalajara, Jal.",
        "modalidad": Vacante.Modalidad.HIBRIDO,
        "nivel": Vacante.Nivel.JR,
        "habilidades_requeridas": ["Python", "Django", "SQL"],
        "habilidades_deseables": ["Docker"],
        "descripcion": "Vacante de ejemplo (ficticia).",
    }
    datos.update(cambios)
    return Vacante.objects.create(**datos)


@pytest.mark.django_db
class TestModeloVacante:
    def test_crear_vacante(self):
        vacante = crear_vacante()
        assert vacante.pk is not None
        assert vacante.activa is True
        assert vacante.creada is not None

    def test_str_muestra_titulo_y_empresa(self):
        assert str(crear_vacante()) == "Desarrollador Python Jr · Nubeterna Labs (ficticia)"

    def test_deseables_por_defecto_es_lista_vacia(self):
        vacante = Vacante.objects.create(
            titulo="Otra", empresa="Otra (ficticia)", ubicacion="CDMX", modalidad="remoto",
            nivel="trainee", habilidades_requeridas=["HTML"], descripcion="x",
        )
        assert vacante.habilidades_deseables == []

    def test_titulo_y_empresa_no_se_repiten(self):
        crear_vacante()
        with pytest.raises(IntegrityError):
            crear_vacante()

    def test_full_clean_rechaza_nivel_invalido(self):
        vacante = Vacante(
            titulo="X", empresa="Y", ubicacion="Z", modalidad="remoto", nivel="senior",
            habilidades_requeridas=["Python"], descripcion="d",
        )
        with pytest.raises(ValidationError) as error:
            vacante.full_clean()
        assert "nivel" in error.value.message_dict


class TestValidarListaDeHabilidades:
    def test_acepta_lista_de_textos(self):
        validar_lista_de_habilidades(["Python", "C#"])  # no lanza

    def test_acepta_lista_vacia(self):
        validar_lista_de_habilidades([])

    @pytest.mark.parametrize("valor", ["Python, Django", {"a": 1}, None, 5])
    def test_rechaza_lo_que_no_es_lista(self, valor):
        with pytest.raises(ValidationError, match="lista"):
            validar_lista_de_habilidades(valor)

    @pytest.mark.parametrize("valor", [["Python", ""], ["Python", "   "], ["Python", 3]])
    def test_rechaza_elementos_vacios_o_no_texto(self, valor):
        with pytest.raises(ValidationError, match="texto no vacío"):
            validar_lista_de_habilidades(valor)


@pytest.mark.django_db
class TestAdminVacante:
    def test_lista_del_admin_carga(self, admin_client):
        crear_vacante()
        respuesta = admin_client.get(reverse("admin:vacantes_vacante_changelist"))
        assert respuesta.status_code == 200
        assert "Desarrollador Python Jr" in respuesta.content.decode()

    def test_busqueda_y_filtros(self, admin_client):
        crear_vacante()
        crear_vacante(titulo="Frontend Trainee", empresa="Pixelia (ficticia)", nivel="trainee")
        url = reverse("admin:vacantes_vacante_changelist")
        html = admin_client.get(url, {"q": "Pixelia"}).content.decode()
        assert "Frontend Trainee" in html and "Desarrollador Python Jr" not in html
        html = admin_client.get(url, {"nivel__exact": "jr"}).content.decode()
        assert "Desarrollador Python Jr" in html and "Frontend Trainee" not in html

    def test_crear_desde_el_admin(self, admin_client):
        respuesta = admin_client.post(
            reverse("admin:vacantes_vacante_add"),
            {
                "titulo": "QA Jr", "empresa": "Testeo (ficticia)", "ubicacion": "Remoto",
                "modalidad": "remoto", "nivel": "jr", "activa": "on",
                "habilidades_requeridas": '["Pytest", "Selenium"]', "habilidades_deseables": "[]",
                "descripcion": "Vacante de ejemplo (ficticia).",
            },
        )
        assert respuesta.status_code == 302  # redirige tras guardar
        assert Vacante.objects.get(titulo="QA Jr").habilidades_requeridas == ["Pytest", "Selenium"]

    def test_admin_rechaza_habilidades_que_no_son_lista(self, admin_client):
        respuesta = admin_client.post(
            reverse("admin:vacantes_vacante_add"),
            {
                "titulo": "QA Jr", "empresa": "Testeo (ficticia)", "ubicacion": "Remoto",
                "modalidad": "remoto", "nivel": "jr", "habilidades_requeridas": '"Pytest, Selenium"',
                "habilidades_deseables": "[]", "descripcion": "d",
            },
        )
        assert respuesta.status_code == 200  # vuelve a mostrar el formulario con el error
        assert not Vacante.objects.filter(titulo="QA Jr").exists()

    def test_editar_y_borrar_desde_el_admin(self, admin_client):
        vacante = crear_vacante()
        admin_client.post(
            reverse("admin:vacantes_vacante_change", args=[vacante.pk]),
            {
                "titulo": vacante.titulo, "empresa": vacante.empresa, "ubicacion": "Monterrey, N.L.",
                "modalidad": vacante.modalidad, "nivel": vacante.nivel, "activa": "on",
                "habilidades_requeridas": '["Python"]', "habilidades_deseables": "[]",
                "descripcion": vacante.descripcion,
            },
        )
        vacante.refresh_from_db()
        assert vacante.ubicacion == "Monterrey, N.L."
        admin_client.post(reverse("admin:vacantes_vacante_delete", args=[vacante.pk]), {"post": "yes"})
        assert not Vacante.objects.filter(pk=vacante.pk).exists()
