"""Mode « quand on veut » : chaque joueur fait le quiz à son rythme, sans organisateur ni partie synchronisée.

Tout est enregistré en base (la partie survit à un redémarrage). Le serveur reste la seule source de vérité :
c'est lui qui chronomètre chaque question (le téléphone ne fait qu'afficher le compte à rebours).
Seule exception : l'instant d'affichage de la question en cours est gardé en mémoire ; après un redémarrage
du serveur, la question en cours repart simplement avec un chrono neuf.
"""
from __future__ import annotations

import secrets
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from . import db
from .game import GRACE_S
from .scoring import compute_points, correct_text, given_text, is_correct, rank_of

OPEN_MAX_PLAYERS = 1000

router = APIRouter(prefix="/api/open")

# player_id -> (index de la question affichée, time.monotonic() de son affichage)
_started: dict[int, tuple[int, float]] = {}


def get_db():
    with db.SessionLocal() as s:
        yield s


class JoinIn(BaseModel):
    name: str


class AnswerIn(BaseModel):
    token: str
    question_index: int
    value: int | str | None = None


def open_session(s, code: str) -> db.GameSession:
    gs = s.scalar(select(db.GameSession).where(db.GameSession.code == code.strip()))
    if not gs or gs.mode != "open":
        raise HTTPException(404, "Code inconnu.")
    return gs


def find_player(s, gs: db.GameSession, token: str) -> db.Player:
    p = s.scalar(select(db.Player).where(db.Player.session_id == gs.id, db.Player.token == token)) if token else None
    if not p:
        raise HTTPException(401, "Joueur inconnu : rejoignez la partie.")
    return p


def _record(s, player: db.Player, q: db.Question, value, correct: bool, points: int, elapsed: int):
    s.add(db.Answer(player_id=player.id, question_id=q.id, value=value, correct=correct,
                    points=points, elapsed_ms=elapsed))
    player.score += points


def next_question(s, gs: db.GameSession, player: db.Player) -> tuple[int, db.Question | None]:
    """Première question sans réponse. Une question restée sans réponse après son délai est comptée 0 point."""
    qs = list(gs.quiz.questions)
    answered = {a.question_id for a in player.answers}
    for idx, q in enumerate(qs):
        if q.id in answered:
            continue
        started = _started.get(player.id)
        if started and started[0] == idx and time.monotonic() > started[1] + q.time_limit + GRACE_S:
            _record(s, player, q, "", False, 0, q.time_limit * 1000)   # onglet fermé / temps écoulé
            s.commit()
            continue
        return idx, q
    return len(qs), None


@router.get("/{code}/info")
def info(code: str, s=Depends(get_db)):
    gs = open_session(s, code)
    return {"title": gs.quiz.title, "status": gs.status, "questions": len(gs.quiz.questions)}


@router.post("/{code}/join")
def join(code: str, data: JoinIn, s=Depends(get_db)):
    gs = open_session(s, code)
    if gs.status == "finished":
        raise HTTPException(400, "Ce quiz est clôturé.")
    name = " ".join(data.name.split())[:20]
    if not name:
        raise HTTPException(400, "Entrez un prénom.")
    if len(gs.players) >= OPEN_MAX_PLAYERS:
        raise HTTPException(400, "Le quiz est complet.")
    if gs.host_key != "library" and any(p.name.lower() == name.lower() for p in gs.players):   # bibliothèque : plusieurs essais possibles
        raise HTTPException(400, "Ce prénom est déjà pris, ajoutez une initiale.")
    token = secrets.token_urlsafe(16)
    s.add(db.Player(session_id=gs.id, name=name, token=token))
    s.commit()
    return {"token": token, "name": name}


@router.get("/{code}/question")
def question(code: str, token: str = "", s=Depends(get_db)):
    gs = open_session(s, code)
    player = find_player(s, gs, token)
    total = len(gs.quiz.questions)
    idx, q = next_question(s, gs, player)
    base = {"title": gs.quiz.title, "name": player.name, "score": player.score, "total": total}
    if q is None:
        return {**base, "state": "done"}
    if gs.status == "finished":
        return {**base, "state": "closed"}
    started = _started.get(player.id)
    if not started or started[0] != idx:           # première fois qu'on affiche cette question
        started = _started[player.id] = (idx, time.monotonic())
    remaining = max(int((started[1] + q.time_limit - time.monotonic()) * 1000), 0)
    return {**base, "state": "question", "remaining_ms": remaining,
            "question": {**q.to_dict(with_answer=False), "index": idx, "total": total}}


@router.post("/{code}/answer")
def answer(code: str, data: AnswerIn, s=Depends(get_db)):
    gs = open_session(s, code)
    player = find_player(s, gs, data.token)
    if gs.status == "finished":
        raise HTTPException(400, "Ce quiz est clôturé.")
    idx, q = next_question(s, gs, player)
    if q is None or idx != data.question_index:
        raise HTTPException(409, "Cette question n'est plus en cours.")
    started = _started.get(player.id)
    if not started or started[0] != idx:
        raise HTTPException(409, "Question non affichée.")
    d, value = q.to_dict(), data.value
    elapsed_ms = int((time.monotonic() - started[1]) * 1000)
    full = d["time_limit"] * 1000
    if elapsed_ms > full + GRACE_S * 1000:
        value = None                                 # réponse reçue après la fin du chrono
    if d["kind"] == "libre":
        value = value.strip()[:100] if isinstance(value, str) and value.strip() else None
    elif not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < len(d["choices"]):
        value = None
    ok = is_correct(d, value)
    elapsed = min(max(elapsed_ms, 0), full) if value is not None else full
    pts = compute_points(ok, d["time_limit"], elapsed)
    try:
        _record(s, player, q, given_text(d, value), ok, pts, elapsed)
        s.commit()
    except IntegrityError:
        s.rollback()
        raise HTTPException(409, "Déjà répondu.")
    scores = [p.score for p in gs.players]
    return {"correct": ok, "points": pts, "score": player.score, "correct_text": correct_text(d),
            "correct_index": d["correct"], "explanation": d["explanation"], "timed_out": value is None,
            "finished": idx + 1 >= len(gs.quiz.questions),
            "rank": rank_of(player.score, scores), "of": len(scores)}
