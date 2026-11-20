"""Variables disponibles en todas las plantillas."""

from services.llm import modo_demo_activo


def modo_demo(request):
    """Indica si la app está en modo demo, para mostrar el aviso en todas las páginas."""
    return {"modo_demo": modo_demo_activo()}
