"""Recomendaciones deterministas, sin LLM.

Se usan en dos casos:
1. Respaldo: si el agente no entrega un resultado válido (límite de iteraciones o JSON inválido dos
   veces), el usuario igual recibe un top 5 útil, marcado como "resultado parcial".
2. Modo demo: el guion del agente demo arma su entrega con estas mismas funciones.
"""

from collections import Counter
from collections.abc import Iterable

from services.esquemas import Brecha, EvaluacionExterna, EvaluacionVacante, PerfilCV, Recomendaciones
from services.habilidades import normalizar
from services.herramientas import habilidades_del_perfil
from services.matching import ResultadoDeterminista, calcular_match_determinista
from vacantes.models import Vacante

TOP = 5
MAX_BRECHAS = 5


def explicacion_determinista(coincidentes: list[str], faltantes_requeridas: list[str]) -> str:
    """Explicación en segunda persona basada solo en habilidades."""
    if not coincidentes:
        return "Aún no cubres las habilidades principales de esta vacante; tómala como meta a mediano plazo."
    texto = f"Coincides en {len(coincidentes)} habilidades clave ({', '.join(coincidentes[:4])})."
    if faltantes_requeridas:
        texto += f" Para encajar mejor te falta: {', '.join(faltantes_requeridas[:3])}."
    else:
        texto += " Cubres todas las habilidades requeridas."
    return texto


def construir_brechas(faltantes_por_vacante: Iterable[list[str]], perfil: PerfilCV) -> list[Brecha]:
    """Brechas priorizadas por cuántas vacantes del top piden cada habilidad que falta."""
    conteo: Counter[str] = Counter()
    nombres: dict[str, str] = {}
    for faltantes in faltantes_por_vacante:
        for habilidad in dict.fromkeys(normalizar(h) for h in faltantes):  # una vez por vacante
            conteo[habilidad] += 1
        for h in faltantes:
            nombres.setdefault(normalizar(h), h)

    brechas = []
    for clave, veces in conteo.most_common(MAX_BRECHAS):
        nombre = nombres[clave]
        brechas.append(
            Brecha(
                habilidad=nombre,
                prioridad="alta" if veces >= 3 else "media" if veces == 2 else "baja",
                motivo=f"La pide{'n' if veces > 1 else ''} {veces} de tus vacantes recomendadas.",
                pasos=[
                    f"Estudia los fundamentos de {nombre} con su documentación oficial o un curso introductorio.",
                    f"Construye un proyecto pequeño que use {nombre} junto con lo que ya dominas.",
                    "Publica el proyecto en GitHub y menciónalo en tu CV.",
                ],
                tiempo_estimado="2 a 4 semanas",
            )
        )
    if not brechas:  # el perfil ya cubre todo: se sugiere profundizar en su habilidad principal
        principal = (perfil.habilidades_tecnicas or ["tu stack principal"])[0]
        brechas.append(
            Brecha(
                habilidad=f"{principal} (nivel avanzado)",
                prioridad="baja",
                motivo="Ya cubres las habilidades de tus vacantes; profundizar te acerca al siguiente nivel.",
                pasos=[f"Estudia temas avanzados de {principal}.", "Contribuye a un proyecto open source que lo use."],
                tiempo_estimado="1 a 2 meses",
            )
        )
    return brechas


def sugerencias_cv(perfil: PerfilCV, palabras_faltantes: list[str]) -> list[str]:
    """Sugerencias generales y accionables para el CV (3 a 6)."""
    sugerencias = []
    if palabras_faltantes:
        sugerencias.append(
            f"Si tienes experiencia con {', '.join(palabras_faltantes[:3])}, menciónalo explícitamente: "
            "los filtros ATS buscan esas palabras exactas."
        )
    if len(perfil.habilidades_tecnicas) < 6:
        sugerencias.append("Agrega una sección de habilidades técnicas con las tecnologías que usas, agrupadas por tipo.")
    sugerencias += [
        "Describe cada experiencia con logros medibles (por ejemplo: 'reduje el tiempo de respuesta un 30 %').",
        "Incluye enlaces a tu GitHub o portafolio con 2 o 3 proyectos destacados.",
        "Adapta el resumen inicial del CV al puesto al que te postulas.",
    ]
    return sugerencias[:6]


def palabras_clave_ats(faltantes_por_vacante: Iterable[list[str]], limite: int = 10) -> list[str]:
    vistas: dict[str, str] = {}
    for faltantes in faltantes_por_vacante:
        for h in faltantes:
            vistas.setdefault(normalizar(h), h)
    return list(vistas.values())[:limite]


def recomendaciones_de_respaldo(
    perfil: PerfilCV,
    match_externo: ResultadoDeterminista | None = None,
) -> Recomendaciones:
    """Top 5 por puntaje determinista sobre TODAS las vacantes activas, sin LLM."""
    habilidades = habilidades_del_perfil(perfil)
    resultados = []
    for vacante in Vacante.objects.filter(activa=True).order_by("id"):
        r = calcular_match_determinista(habilidades, vacante.habilidades_requeridas, vacante.habilidades_deseables)
        resultados.append((vacante, r))
    resultados.sort(key=lambda par: par[1].puntaje, reverse=True)  # estable: empata por id
    top = resultados[:TOP]
    if not top:
        raise ValueError("No hay vacantes activas en el catálogo para recomendar.")

    # Requeridas y deseables cuentan para las brechas: un perfil que ya cubre lo obligatorio
    # igual puede crecer con lo deseable.
    faltantes = [r.faltantes for _, r in top]
    palabras = palabras_clave_ats(faltantes)
    return Recomendaciones(
        top_vacantes=[
            EvaluacionVacante(
                vacante_id=v.id,
                puntaje_llm=round(r.puntaje),  # sin LLM, la "evaluación" coincide con el determinista
                explicacion=explicacion_determinista(r.coincidentes, r.faltantes_requeridas),
            )
            for v, r in top
        ],
        vacante_externa=(
            EvaluacionExterna(
                puntaje_llm=round(match_externo.puntaje),
                explicacion=explicacion_determinista(match_externo.coincidentes, match_externo.faltantes_requeridas),
            )
            if match_externo is not None
            else None
        ),
        brechas=construir_brechas(faltantes, perfil),
        sugerencias_cv=sugerencias_cv(perfil, palabras),
        palabras_clave_ats=palabras,
    )
