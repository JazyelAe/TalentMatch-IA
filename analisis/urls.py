"""Rutas de la app de análisis."""

from django.urls import path

from analisis import views

app_name = "analisis"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("analizar/", views.analizar, name="analizar"),
    path("analisis/<int:pk>/", views.resultado, name="resultado"),
]
