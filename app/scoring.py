"""Règles de correction et de calcul des points (pures, faciles à tester)."""
from __future__ import annotations

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


def is_correct(question: dict, value) -> bool:
    """question : dict avec kind, correct, accepted. value : index (qcm/vf) ou texte (libre)."""
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
    try:
        return question["choices"][int(value)]
    except (TypeError, ValueError, IndexError):
        return ""


def correct_text(question: dict) -> str:
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
