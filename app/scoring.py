"""Règles de correction et de calcul des points (pures, faciles à tester)."""
from __future__ import annotations

import random
import re
import unicodedata

MAX_POINTS = 1000
MIN_CORRECT_POINTS = 500   # une bonne réponse donnée à la dernière seconde vaut encore 500

_ARTICLES = re.compile(r"\b(le|la|les|l|un|une|des|du|de|d|the)\b")


def normalize(text: str) -> str:
    """Minuscules, sans accents ni ponctuation ni articles : « L'Océan Pacifique » -> « ocean pacifique »."""
    s = unicodedata.normalize("NFD", str(text).lower().strip())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = _ARTICLES.sub(" ", s)
    return " ".join(s.split())


KINDS_CHOICES = ("qcm", "vf")          # réponse = un index
STREAK_STEP, STREAK_MAX = 50, 250       # bonus de série : +50 par bonne réponse consécutive (dès la 2e), plafonné à +250
JOKER_FACTOR = 0.5                      # une bonne réponse donnée avec le joker 50/50 vaut moitié moins de points


def streak_bonus(streak: int) -> int:
    """streak = nombre de bonnes réponses d'affilée, la réponse qui vient d'être donnée comprise."""
    return min(STREAK_STEP * (streak - 1), STREAK_MAX) if streak >= 2 else 0


def streak_before(correct_flags: list[bool]) -> int:
    """Série en cours à partir des réponses précédentes (dans l'ordre des questions)."""
    n = 0
    for ok in reversed(correct_flags):
        if not ok:
            break
        n += 1
    return n


def order_perm(question_id: int, n: int) -> list[int]:
    """Ordre d'affichage d'une question « remettre dans l'ordre » : shown[i] = choices[perm[i]].
    Déterministe (même ordre pour tous, avant et après un rechargement) et jamais l'ordre correct."""
    ids = list(range(n))
    rng = random.Random(question_id * 7919 + n)
    for _ in range(20):
        rng.shuffle(ids)
        if ids != sorted(ids):
            break
    return ids


def shown_choices(question: dict) -> list[str]:
    """Choix tels qu'on les montre aux joueurs (mélangés pour « ordre », sinon inchangés)."""
    if question["kind"] == "ordre":
        return [question["choices"][i] for i in order_perm(question.get("id", 0), len(question["choices"]))]
    return question["choices"]


def correct_display_order(question: dict) -> list[int]:
    """Pour « ordre » : indices (dans l'affichage mélangé) à cliquer dans l'ordre pour réussir."""
    perm = order_perm(question.get("id", 0), len(question["choices"]))
    return [perm.index(k) for k in range(len(perm))]


def joker_hidden(question: dict, seed: int) -> list[int]:
    """Indices de mauvaises réponses à masquer avec le joker 50/50 (QCM de 3 ou 4 réponses), [] sinon."""
    n = len(question["choices"])
    if question["kind"] != "qcm" or n < 3:
        return []
    wrong = [i for i in range(n) if i != question["correct"]]
    random.Random(seed * 104729 + question.get("id", 0)).shuffle(wrong)
    return sorted(wrong[: n // 2])


def clean_value(question: dict, value):
    """Valide la réponse brute d'un joueur selon le type de question. Renvoie la valeur normalisée, ou None si invalide."""
    kind = question["kind"]
    if kind == "libre":
        return value.strip()[:100] if isinstance(value, str) and value.strip() else None
    if kind in KINDS_CHOICES:
        ok = isinstance(value, int) and not isinstance(value, bool) and 0 <= value < len(question["choices"])
        return value if ok else None
    if kind == "ordre":
        n = len(question["choices"])
        if isinstance(value, list) and len(value) == n and sorted(value) == list(range(n)) \
                and all(isinstance(v, int) and not isinstance(v, bool) for v in value):
            return list(value)
        return None
    if kind == "point":
        if isinstance(value, (list, tuple)) and len(value) == 2 and all(
                isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 100 for v in value):
            return [round(float(value[0]), 1), round(float(value[1]), 1)]
        return None
    return None


def point_target(question: dict) -> tuple[float, float, float]:
    x, y, r = (float(v) for v in question["accepted"][:3])
    return x, y, r


def reveal_extra(question: dict) -> dict:
    """Éléments de correction propres aux types « ordre » (ordre à cliquer) et « point » (zone cible)."""
    if question["kind"] == "ordre":
        return {"correct_order": correct_display_order(question)}
    if question["kind"] == "point":
        x, y, r = point_target(question)
        return {"target": {"x": x, "y": y, "r": r}}
    return {}


def is_correct(question: dict, value) -> bool:
    """question : dict avec kind, correct, accepted. value : valeur déjà nettoyée (voir clean_value)."""
    if question["kind"] == "ordre":
        if not isinstance(value, list):
            return False
        perm = order_perm(question.get("id", 0), len(question["choices"]))
        try:
            return [perm[i] for i in value] == list(range(len(perm)))
        except (TypeError, IndexError):
            return False
    if question["kind"] == "point":
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return False
        x, y, r = point_target(question)
        return (value[0] - x) ** 2 + (value[1] - y) ** 2 <= r ** 2
    if question["kind"] == "libre":
        if not isinstance(value, str) or not value.strip():
            return False
        answers = {normalize(a) for a in question["accepted"]}
        return normalize(value) in answers
    try:
        return int(value) == question["correct"]
    except (TypeError, ValueError):
        return False


def given_text(question: dict, value) -> str:
    """Texte lisible de la réponse donnée (stocké pour la revue des réponses)."""
    if value is None or value == "":
        return ""
    if question["kind"] == "libre":
        return str(value).strip()[:200]
    if question["kind"] == "ordre":
        shown = shown_choices(question)
        try:
            return " → ".join(shown[i] for i in value)[:200]
        except (TypeError, IndexError):
            return ""
    if question["kind"] == "point":
        return f"Clic à ({value[0]:g} %, {value[1]:g} %)" if isinstance(value, (list, tuple)) and len(value) == 2 else ""
    try:
        return question["choices"][int(value)]
    except (TypeError, ValueError, IndexError):
        return ""


def correct_text(question: dict) -> str:
    if question["kind"] == "ordre":
        return " → ".join(question["choices"])
    if question["kind"] == "point":
        return "La zone entourée sur l'image"
    if question["kind"] == "libre":
        return question["accepted"][0] if question["accepted"] else ""
    return question["choices"][question["correct"]]


def compute_points(correct: bool, time_limit_s: int, elapsed_ms: int) -> int:
    """0 si faux ; sinon entre 500 et 1000 selon la rapidité."""
    if not correct:
        return 0
    limit_ms = time_limit_s * 1000
    remaining = min(max(limit_ms - max(elapsed_ms, 0), 0), limit_ms)
    return MIN_CORRECT_POINTS + round((MAX_POINTS - MIN_CORRECT_POINTS) * remaining / limit_ms)


def rank_of(score: int, scores: list[int]) -> int:
    """Rang « à la olympique » : à égalité de points, même rang."""
    return 1 + sum(1 for s in scores if s > score)
