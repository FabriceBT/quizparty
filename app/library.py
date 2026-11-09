"""Bibliothèque de quiz en libre-service : les joueurs choisissent un quiz sur leur téléphone et jouent
à tout moment, sans que l'organisateur ait à lancer quoi que ce soit.

Chaque quiz publié a en permanence une partie « quand on veut » ouverte (mode open, host_key = "library"),
créée automatiquement à la première visite. Son classement est permanent ; l'organisateur peut le remettre
à zéro (la partie est alors archivée dans l'historique et une nouvelle démarre à la visite suivante).
"""
from __future__ import annotations

import io
import random
from datetime import datetime, timedelta, timezone

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import func, select

from . import db
from .config import BASE_DIR, LIBRARY_WEEKLY, ASSET_VERSION
from .openmode import OPEN_MAX_PLAYERS

router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.globals["asset_v"] = ASSET_VERSION
LIBRARY = "library"          # valeur de host_key qui marque une partie de bibliothèque


def get_db():
    with db.SessionLocal() as s:
        yield s


def _admin(request: Request):
    from .main import admin_required       # import tardif : main importe ce module
    return admin_required(request)


def _new_code(s) -> str:
    while True:
        code = f"{random.randint(0, 999999):06d}"
        if not s.scalar(select(db.GameSession.id).where(db.GameSession.code == code)):
            return code


def week_start() -> datetime:
    """Lundi 00:00 (UTC) de la semaine en cours."""
    n = datetime.now(timezone.utc)
    return (n - timedelta(days=n.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def _fresh(gs: db.GameSession) -> bool:
    """La partie de bibliothèque appartient-elle à la semaine en cours ? (toujours vrai si la remise à zéro hebdomadaire est coupée)"""
    if not LIBRARY_WEEKLY:
        return True
    created = gs.created_at if gs.created_at.tzinfo else gs.created_at.replace(tzinfo=timezone.utc)
    return created >= week_start()


def _latest_running(s, quiz_id: int) -> db.GameSession | None:
    return s.scalar(select(db.GameSession).where(
        db.GameSession.quiz_id == quiz_id, db.GameSession.mode == "open", db.GameSession.host_key == LIBRARY,
        db.GameSession.status == "running").order_by(db.GameSession.id.desc()))


def running_session(s, quiz_id: int) -> db.GameSession | None:
    gs = _latest_running(s, quiz_id)
    return gs if gs and _fresh(gs) else None


def library_session(s, quiz: db.Quiz) -> db.GameSession:
    """Partie permanente du quiz (créée au besoin). Archivée et recréée quand elle est pleine ou quand une nouvelle semaine commence."""
    gs = _latest_running(s, quiz.id)
    if gs and (len(gs.players) >= OPEN_MAX_PLAYERS or not _fresh(gs)):
        gs.status, gs.finished_at = "finished", db.now()
        gs = None
    if not gs:
        gs = db.GameSession(code=_new_code(s), quiz_id=quiz.id, mode="open", host_key=LIBRARY, status="running")
        s.add(gs)
    s.commit()
    return gs


def _player_count(s, quiz_id: int) -> int:
    gs = running_session(s, quiz_id)
    return s.scalar(select(func.count(db.Player.id)).where(db.Player.session_id == gs.id)) if gs else 0


# ------------------------------------------------------------------ côté joueurs (public)
@router.get("/api/library")
def list_library(s=Depends(get_db)):
    quizzes = [q for q in s.scalars(select(db.Quiz).where(db.Quiz.published.is_(True)).order_by(db.Quiz.created_at.desc()))
               if q.questions]
    # Quiz du jour : un quiz différent chaque jour, le même pour tout le monde (rotation sur les quiz publiés).
    daily = sorted(quizzes, key=lambda q: q.id)[datetime.now(timezone.utc).date().toordinal() % len(quizzes)].id if quizzes else None
    return [{"id": q.id, "title": q.title, "description": q.description, "category": q.category,
             "questions": len(q.questions), "players": _player_count(s, q.id), "daily": q.id == daily}
            for q in quizzes]


@router.get("/q/{quiz_id}")
def play_quiz(quiz_id: int, s=Depends(get_db)):
    quiz = s.get(db.Quiz, quiz_id)
    if not quiz or not quiz.published or not quiz.questions:
        raise HTTPException(404, "Ce quiz n'est pas disponible.")
    return RedirectResponse(f"/j/{library_session(s, quiz).code}", status_code=303)


@router.get("/qr-play.svg")
def qr_play(request: Request):
    from .main import public_base
    img = qrcode.make(f"{public_base(request)}/play", image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return Response(buf.getvalue(), media_type="image/svg+xml")


# ------------------------------------------------------------------ côté organisateur
@router.get("/library", dependencies=[Depends(_admin)])
def library_page(request: Request):
    from .main import is_local_only, public_base
    base = public_base(request)
    return templates.TemplateResponse(request, "library_admin.html", {
        "join_url": f"{base}/play", "join_short": base.split("://", 1)[-1] + "/play", "local_only": is_local_only(request)})


@router.get("/api/library/admin", dependencies=[Depends(_admin)])
def library_admin(s=Depends(get_db)):
    out = []
    for q in s.scalars(select(db.Quiz).order_by(db.Quiz.created_at.desc())):
        gs = running_session(s, q.id)
        out.append({"id": q.id, "title": q.title, "questions": len(q.questions), "published": q.published,
                    "code": gs.code if gs else None, "players": _player_count(s, q.id)})
    return out


class PublishIn(BaseModel):
    published: bool


@router.post("/api/library/{quiz_id}/publish", dependencies=[Depends(_admin)])
def set_published(quiz_id: int, data: PublishIn, s=Depends(get_db)):
    quiz = s.get(db.Quiz, quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz introuvable.")
    quiz.published = data.published
    s.commit()
    return {"ok": True}


@router.post("/api/library/{quiz_id}/reset", dependencies=[Depends(_admin)])
def reset_ranking(quiz_id: int, s=Depends(get_db)):
    """Remet le classement à zéro : la partie en cours est archivée, une nouvelle démarre à la prochaine visite."""
    gs = _latest_running(s, quiz_id)
    if gs:
        gs.status, gs.finished_at = "finished", db.now()
        s.commit()
    return {"ok": True}
