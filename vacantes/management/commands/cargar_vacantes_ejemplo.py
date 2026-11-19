"""Comando: python manage.py cargar_vacantes_ejemplo

Carga (o actualiza) 20 vacantes de TI de EJEMPLO, con empresas inventadas.
Es idempotente: se puede correr varias veces sin duplicar vacantes, porque usa
(titulo, empresa) como identificador.
"""

import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from vacantes.models import Vacante

RUTA_DATOS = Path(__file__).resolve().parents[2] / "data" / "vacantes_ejemplo.json"
AVISO_FICTICIA = "Vacante de ejemplo (ficticia): la empresa y el puesto son inventados."


def leer_vacantes_ejemplo(ruta: Path = RUTA_DATOS) -> list[dict]:
    """Lee el JSON de vacantes de ejemplo."""
    with ruta.open(encoding="utf-8") as archivo:
        return json.load(archivo)


def con_aviso_ficticia(descripcion: str) -> str:
    """Antepone el aviso de vacante ficticia a la descripción."""
    return f"{AVISO_FICTICIA}\n\n{descripcion.strip()}"


class Command(BaseCommand):
    help = "Carga 20 vacantes de TI ficticias de ejemplo (idempotente)."

    def handle(self, *args, **opciones):
        try:
            datos = leer_vacantes_ejemplo()
        except (OSError, json.JSONDecodeError) as error:
            raise CommandError(f"No se pudo leer {RUTA_DATOS}: {error}") from error

        creadas = actualizadas = 0
        # Todo o nada: si una vacante es inválida, no se guarda ninguna.
        with transaction.atomic():
            for numero, item in enumerate(datos, start=1):
                campos = {**item, "descripcion": con_aviso_ficticia(item["descripcion"])}
                titulo, empresa = campos.pop("titulo"), campos.pop("empresa")

                vacante = Vacante.objects.filter(titulo=titulo, empresa=empresa).first()
                es_nueva = vacante is None
                if es_nueva:
                    vacante = Vacante(titulo=titulo, empresa=empresa)
                for campo, valor in campos.items():
                    setattr(vacante, campo, valor)

                try:
                    vacante.full_clean()
                except ValidationError as error:
                    raise CommandError(f"Vacante #{numero} ({titulo}) inválida: {error.message_dict}") from error

                vacante.save()
                creadas += es_nueva
                actualizadas += not es_nueva

        self.stdout.write(self.style.SUCCESS(f"Vacantes de ejemplo: {creadas} creadas, {actualizadas} actualizadas."))
