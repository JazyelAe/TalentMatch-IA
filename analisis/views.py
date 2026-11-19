"""Vistas de la app de análisis de CV."""

import logging

from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render

from analisis.forms import AnalisisForm
from analisis.models import Analisis
from services.extraccion import ErrorExtraccion, extraer_texto
from services.llm import ErrorLLM
from services.orquestador import CatalogoVacioError, analizar_cv
from services.vacante_externa import VacanteExternaInvalidaError

logger = logging.getLogger(__name__)

PASOS_COMO_FUNCIONA = [
    {
        "titulo": "Sube tu CV",
        "descripcion": "En PDF o DOCX, o pega el texto. El archivo no se guarda: solo se lee su contenido.",
    },
    {
        "titulo": "El agente lo analiza",
        "descripcion": "La IA extrae tu perfil, busca vacantes y calcula qué tan bien encajas en cada una.",
    },
    {
        "titulo": "Recibe tu plan",
        "descripcion": "Tus 5 mejores vacantes, las habilidades que te faltan y cómo mejorar tu CV.",
    },
]


def inicio(request):
    """Página de inicio: explica qué hace TalentMatch IA."""
    return render(request, "analisis/inicio.html", {"pasos": PASOS_COMO_FUNCIONA})


def _peticion_demasiado_grande(request) -> bool:
    """Los archivos que superan FILE_UPLOAD_MAX_MEMORY_SIZE ni siquiera se reciben (no tocan el disco)."""
    try:
        return int(request.META.get("CONTENT_LENGTH") or 0) > settings.FILE_UPLOAD_MAX_MEMORY_SIZE
    except ValueError:
        return False


def analizar(request):
    """Formulario del CV. En POST: extrae el texto, corre el análisis y redirige a los resultados."""
    if request.method != "POST":
        return render(request, "analisis/analizar.html", {"form": AnalisisForm()})

    form = AnalisisForm(request.POST, request.FILES)
    if _peticion_demasiado_grande(request):
        form.is_valid()
        form.add_error("archivo_cv", "El archivo pesa más de 5 MB.")
    elif form.is_valid():
        archivo = form.cleaned_data["archivo_cv"]
        try:
            extraido = extraer_texto(archivo=archivo, texto=form.cleaned_data["texto_cv"])
            analisis = analizar_cv(extraido.texto, extraido.origen, form.cleaned_data["texto_vacante"])
            return redirect(analisis)
        except ErrorExtraccion as error:
            form.add_error("archivo_cv" if archivo else "texto_cv", str(error))
        except VacanteExternaInvalidaError as error:
            form.add_error("texto_vacante", str(error))
        except (ErrorLLM, CatalogoVacioError) as error:
            # Detalle técnico al log (sin datos del CV); mensaje claro al usuario.
            logger.error("Falló el análisis: %s: %s", type(error).__name__, error)
            form.add_error(None, error.mensaje_usuario)
    return render(request, "analisis/analizar.html", {"form": form}, status=400)


def resultado(request, pk: int):
    """Resultados de un análisis guardado."""
    analisis = get_object_or_404(Analisis, pk=pk)
    return render(request, "analisis/resultado.html", {"analisis": analisis})
