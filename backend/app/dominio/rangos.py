"""Escalafon de rangos y experiencia (XP) del leaderboard.

El README del proyecto fija el criterio: la plataforma no premia hacer mas, sino la calidad,
dificultad y verificacion de cada evidencia. Por eso el rango no se calcula contando PRs, como en la
tabla original de la propuesta, sino sumando XP por credencial vigente ponderada por:

- dificultad del reto (base),
- puntaje del Juez IA sobre el codigo entregado (multiplicador 0,6 a 1,0),
- defensa tecnica aprobada (bono igual a su puntaje).

Una credencial revocada deja de sumar en el acto: el XP se recalcula siempre, nunca se persiste.
"""

import math

BASE_XP = {"BASICO": 100, "INTERMEDIO": 180, "AVANZADO": 300}
BASE_SIN_DIFICULTAD = 150

RANGOS = [
    (0, "CACHIMBO", "Cachimbo", "Acceso a retos base"),
    (300, "JUNIOR_BUILDER", "Junior Builder", "Badge de Clean Code"),
    (800, "MID_ARCHITECT", "Mid Architect", "Badge de Concurrencia"),
    (1600, "SENIOR_SINNER", "Senior Sinner", "Recomendacion directa a empresas"),
    (3000, "ORACULO_TECH", "Oraculo Tech", "Fast-Track Hiring D1"),
]


def xp_credencial(dificultad: str | None, puntaje_revision: int | None, puntaje_defensa: int | None) -> int:
    base = BASE_XP.get(dificultad or "", BASE_SIN_DIFICULTAD)
    calidad = 0.6 + 0.4 * puntaje_revision / 100 if puntaje_revision is not None else 0.8
    bono = puntaje_defensa or 0
    return math.floor(base * calidad + bono)


def rango_para(xp: int) -> dict:
    nivel = 0
    for i, (umbral, *_resto) in enumerate(RANGOS):
        if xp >= umbral:
            nivel = i
    umbral, codigo, nombre, beneficio = RANGOS[nivel]
    siguiente = RANGOS[nivel + 1] if nivel + 1 < len(RANGOS) else None
    return {
        "codigo": codigo,
        "nombre": nombre,
        "nivel": nivel + 1,
        "beneficio": beneficio,
        "xp": xp,
        "xp_rango_actual": umbral,
        "siguiente": siguiente[2] if siguiente else None,
        "xp_siguiente": siguiente[0] if siguiente else None,
        "progreso_pct": (100 if siguiente is None else round(100 * (xp - umbral) / (siguiente[0] - umbral))),
    }


def tabla() -> list[dict]:
    return [{"umbral_xp": u, "codigo": c, "nombre": n, "beneficio": b} for u, c, n, b in RANGOS]
