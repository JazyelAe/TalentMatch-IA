"""Admin del historial de análisis: solo lectura (se puede consultar y borrar, no editar)."""

from django.contrib import admin

from analisis.models import Analisis, ResultadoMatch


class ResultadoMatchInline(admin.TabularInline):
    model = ResultadoMatch
    extra = 0
    can_delete = False
    fields = ["posicion", "es_externa", "titulo", "empresa", "puntaje_determinista", "puntaje_llm", "puntaje_final"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Analisis)
class AnalisisAdmin(admin.ModelAdmin):
    list_display = ["id", "creado", "nivel", "origen_cv", "proveedor", "resultado_parcial"]
    list_filter = ["proveedor", "resultado_parcial", "origen_cv"]
    inlines = [ResultadoMatchInline]

    def get_readonly_fields(self, request, obj=None):
        return [campo.name for campo in self.model._meta.fields]

    def has_add_permission(self, request):
        return False
