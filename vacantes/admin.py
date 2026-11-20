"""Administración de vacantes en el admin de Django (CRUD)."""

from django.contrib import admin

from vacantes.models import Vacante


@admin.register(Vacante)
class VacanteAdmin(admin.ModelAdmin):
    list_display = ["titulo", "empresa", "nivel", "modalidad", "ubicacion", "activa"]
    list_filter = ["nivel", "modalidad", "activa"]
    search_fields = ["titulo", "empresa"]
    list_editable = ["activa"]
    readonly_fields = ["creada"]
    fieldsets = [
        (None, {"fields": ["titulo", "empresa", "ubicacion", "modalidad", "nivel", "activa"]}),
        ("Habilidades", {"fields": ["habilidades_requeridas", "habilidades_deseables"]}),
        ("Detalle", {"fields": ["descripcion", "creada"]}),
    ]
