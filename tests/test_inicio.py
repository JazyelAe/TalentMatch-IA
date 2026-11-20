"""Pruebas de la página de inicio y la plantilla base (T02)."""

from pathlib import Path

from django.conf import settings
from django.urls import reverse


def test_inicio_responde_200(client):
    respuesta = client.get(reverse("analisis:inicio"))
    assert respuesta.status_code == 200


def test_inicio_usa_la_plantilla_base(client):
    respuesta = client.get(reverse("analisis:inicio"))
    nombres = [t.name for t in respuesta.templates]
    assert "analisis/inicio.html" in nombres
    assert "base.html" in nombres


def test_inicio_enlaza_el_css_compilado(client):
    respuesta = client.get(reverse("analisis:inicio"))
    assert 'href="/static/css/app.css"' in respuesta.content.decode()


def test_inicio_esta_en_espanol_y_es_responsiva(client):
    html = client.get(reverse("analisis:inicio")).content.decode()
    assert '<html lang="es">' in html
    assert 'name="viewport"' in html
    assert "¿Cómo funciona?" in html


def test_css_compilado_existe_en_el_repo():
    """El CSS se versiona para que nadie necesite Node solo para correr la app."""
    css = Path(settings.BASE_DIR) / "static" / "css" / "app.css"
    assert css.exists(), "Corre `npm run css:build` para generar static/css/app.css"
    contenido = css.read_text(encoding="utf-8")
    assert "tailwindcss" in contenido  # el CLI incluye su cabecera de licencia
    assert ".bg-marca-600" in contenido  # la clase de marca usada en la plantilla se generó
