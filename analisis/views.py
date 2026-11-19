"""Vistas de la app de análisis de CV."""

from django.shortcuts import render

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
