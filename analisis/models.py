"""Modelos del historial de análisis (SPEC §6).

Se guarda el PERFIL estructurado y los resultados, nunca el archivo ni el texto completo del CV.
"""

from django.db import models
from django.urls import reverse

from vacantes.models import Vacante


class Analisis(models.Model):
    """Un análisis de CV: perfil extraído, recomendaciones y metadatos de cómo se generó."""

    class Origen(models.TextChoices):
        PDF = "pdf", "PDF"
        DOCX = "docx", "DOCX"
        TEXTO = "texto", "Texto pegado"

    creado = models.DateTimeField(auto_now_add=True)
    origen_cv = models.CharField("origen del CV", max_length=10, choices=Origen.choices)
    perfil = models.JSONField(help_text="PerfilCV validado.")
    recomendaciones = models.JSONField(help_text="Brechas, sugerencias para el CV y palabras clave ATS.")
    vacante_externa = models.JSONField(null=True, blank=True, help_text="Vacante pegada ya estructurada (opcional).")
    proveedor = models.CharField(max_length=30)
    modelo = models.CharField(max_length=60)
    resultado_parcial = models.BooleanField(default=False, help_text="True si se usó el respaldo determinista.")
    iteraciones_agente = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-creado", "-id"]
        verbose_name = "análisis"
        verbose_name_plural = "análisis"

    def __str__(self) -> str:
        return f"Análisis #{self.pk} · {self.nivel} · {self.creado:%Y-%m-%d %H:%M}"

    def get_absolute_url(self) -> str:
        return reverse("analisis:resultado", args=[self.pk])

    @property
    def nivel(self) -> str:
        return self.perfil.get("nivel_estimado", "")

    @property
    def es_demo(self) -> bool:
        return self.proveedor == "demo"

    def resultados_catalogo(self):
        return self.resultados.filter(es_externa=False).order_by("posicion")

    def resultado_externo(self):
        return self.resultados.filter(es_externa=True).first()

    def mejor_resultado(self):
        return self.resultados_catalogo().first()


class ResultadoMatch(models.Model):
    """Puntaje de una vacante dentro de un análisis."""

    analisis = models.ForeignKey(Analisis, on_delete=models.CASCADE, related_name="resultados")
    # SET_NULL + copia de título/empresa: borrar una vacante no rompe el historial.
    vacante = models.ForeignKey(Vacante, on_delete=models.SET_NULL, null=True, blank=True, related_name="resultados")
    es_externa = models.BooleanField(default=False)
    posicion = models.PositiveSmallIntegerField()
    titulo = models.CharField("título", max_length=150)
    empresa = models.CharField(max_length=120, blank=True)
    puntaje_determinista = models.FloatField()
    puntaje_llm = models.FloatField()
    puntaje_final = models.FloatField()
    habilidades_coincidentes = models.JSONField(default=list)
    habilidades_faltantes = models.JSONField(default=list)
    explicacion = models.TextField()

    class Meta:
        ordering = ["es_externa", "posicion"]
        verbose_name = "resultado de match"
        verbose_name_plural = "resultados de match"

    def __str__(self) -> str:
        return f"{self.titulo} · {self.puntaje_final:g}"
