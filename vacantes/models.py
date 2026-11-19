"""Modelo de vacantes de TI."""

from django.core.exceptions import ValidationError
from django.db import models


def validar_lista_de_habilidades(valor):
    """Las habilidades deben ser una lista de textos no vacíos, por ejemplo ["Python", "Django"]."""
    if not isinstance(valor, list):
        raise ValidationError('Debe ser una lista, por ejemplo: ["Python", "Django"].')
    for elemento in valor:
        if not isinstance(elemento, str) or not elemento.strip():
            raise ValidationError(f"Cada habilidad debe ser un texto no vacío (valor inválido: {elemento!r}).")


class Vacante(models.Model):
    """Una vacante de TI contra la que se compara el CV."""

    class Modalidad(models.TextChoices):
        REMOTO = "remoto", "Remoto"
        HIBRIDO = "hibrido", "Híbrido"
        PRESENCIAL = "presencial", "Presencial"

    class Nivel(models.TextChoices):
        TRAINEE = "trainee", "Trainee"
        JR = "jr", "Junior"
        MID = "mid", "Mid"

    titulo = models.CharField("título", max_length=150)
    empresa = models.CharField(max_length=120)
    ubicacion = models.CharField("ubicación", max_length=120)
    modalidad = models.CharField(max_length=20, choices=Modalidad.choices)
    nivel = models.CharField(max_length=20, choices=Nivel.choices)
    habilidades_requeridas = models.JSONField(
        default=list,
        validators=[validar_lista_de_habilidades],
        help_text='Lista JSON, por ejemplo: ["Python", "Django", "SQL"].',
    )
    habilidades_deseables = models.JSONField(
        default=list,
        blank=True,
        validators=[validar_lista_de_habilidades],
        help_text='Lista JSON; puede quedar vacía: [].',
    )
    descripcion = models.TextField("descripción")
    activa = models.BooleanField(default=True, help_text="Solo las vacantes activas se usan en los análisis.")
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["titulo", "empresa"]
        constraints = [
            # Permite que la carga de vacantes de ejemplo sea idempotente (T05).
            models.UniqueConstraint(fields=["titulo", "empresa"], name="vacante_unica_por_titulo_y_empresa"),
        ]

    def __str__(self) -> str:
        return f"{self.titulo} · {self.empresa}"
