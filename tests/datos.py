"""Datos de prueba reutilizables (diccionarios válidos que cada test puede modificar)."""


def perfil_valido(**cambios) -> dict:
    datos = {
        "resumen": "Desarrolladora backend con un año de experiencia en Python y Django.",
        "habilidades_tecnicas": ["Python", "Django", "SQL", "Git", "HTML", "CSS"],
        "habilidades_blandas": ["Trabajo en equipo", "Comunicación"],
        "experiencia": [
            {"puesto": "Desarrolladora backend", "empresa": "Startup X", "duracion": "1 año",
             "descripcion": "APIs REST con Django y PostgreSQL."},
        ],
        "educacion": [{"titulo": "Ingeniería en Sistemas", "institucion": "Tec Y", "anio": "2024"}],
        "idiomas": [{"idioma": "Español", "nivel": "nativo"}, {"idioma": "Inglés", "nivel": "B1"}],
        "anios_experiencia": 1,
        "nivel_estimado": "jr",
    }
    datos.update(cambios)
    return datos


def recomendaciones_validas(ids: tuple[int, ...] = (1, 2)) -> dict:
    return {
        "top_vacantes": [
            {"vacante_id": vacante_id, "puntaje_llm": 80 - i * 10, "explicacion": "Tu experiencia con Django encaja."}
            for i, vacante_id in enumerate(ids)
        ],
        "vacante_externa": None,
        "brechas": [
            {
                "habilidad": "Docker",
                "prioridad": "alta",
                "motivo": "La piden 3 de tus 5 mejores vacantes.",
                "pasos": ["Sigue el tutorial oficial", "Dockeriza un proyecto propio"],
                "tiempo_estimado": "2 semanas",
            }
        ],
        "sugerencias_cv": [
            "Cuantifica tus logros.",
            "Agrega enlaces a tu GitHub.",
            "Ordena la experiencia de la más reciente a la más antigua.",
        ],
        "palabras_clave_ats": ["Docker", "APIs REST"],
    }
