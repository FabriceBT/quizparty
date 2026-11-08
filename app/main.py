"""Quiz Party – application FastAPI (pages, API REST, WebSockets)."""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import random
import secrets
import socket
import uuid
from contextlib import asynccontextmanager
from urllib.parse import quote

import qrcode
import qrcode.image.svg
from fastapi import (Depends, FastAPI, File, HTTPException, Request, UploadFile,
                     WebSocket, WebSocketDisconnect)
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from . import db, services
from .config import BASE_DIR, MAX_UPLOAD_MB, MEDIA_DIR
from .game import Game, GameError, manager
from .openmode import open_session, router as open_router
from .schemas import JoinIn, QuizIn, SessionIn
from .scoring import compute_points, correct_text, given_text, is_correct
from .seed import create_quiz, seed_demo_if_empty


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    with db.SessionLocal() as s:
        seed_demo_if_empty(s)
    yield


app = FastAPI(title="Quiz Party", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
app.include_router(open_router)


def get_db():
    with db.SessionLocal() as s:
        yield s


# ------------------------------------------------------------------ admin
class NeedLogin(Exception):
    pass


def _admin_token() -> str:
    pw = os.environ.get("QUIZ_ADMIN_PASSWORD", "")
    return hmac.new(pw.encode(), b"quizparty-admin", hashlib.sha256).hexdigest()


def admin_required(request: Request):
    """Si QUIZ_ADMIN_PASSWORD est défini, les pages d'organisation exigent une connexion."""
    if not os.environ.get("QUIZ_ADMIN_PASSWORD"):
        return
    if not hmac.compare_digest(request.cookies.get("qp_admin", ""), _admin_token()):
        raise NeedLogin()


@app.exception_handler(NeedLogin)
async def _need_login(request: Request, _: NeedLogin):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Connexion organisateur requise."}, status_code=401)
    return RedirectResponse(f"/login?next={quote(request.url.path)}", status_code=303)


@app.get("/login")
def login_page(request: Request, next: str = "/", error: int = 0):
    return templates.TemplateResponse(request, "login.html", {"next": next, "error": error})


@app.post("/login")
async def login(request: Request):
    form = await request.form()
    pw, nxt = str(form.get("password", "")), str(form.get("next", "/"))
    expected = os.environ.get("QUIZ_ADMIN_PASSWORD", "")
    if not nxt.startswith("/") or nxt.startswith("//"):
        nxt = "/"
    if expected and hmac.compare_digest(pw, expected):
        resp = RedirectResponse(nxt, status_code=303)
        resp.set_cookie("qp_admin", _admin_token(), httponly=True, samesite="lax", max_age=30 * 86400)
        return resp
    return RedirectResponse(f"/login?next={quote(nxt)}&error=1", status_code=303)


# ------------------------------------------------------------------ outils
def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk:
            sk.connect(("10.255.255.255", 1))
            return sk.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def codespace_url(request: Request) -> str | None:
    """Dans un GitHub Codespace, le serveur voit « localhost » : l'adresse publique se déduit de l'environnement."""
    name, domain = os.environ.get("CODESPACE_NAME"), os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN")
    if not (name and domain):
        return None
    return f"https://{name}-{request.url.port or 8000}.{domain}"


def is_local_only(request: Request) -> bool:
    """Vrai si les téléphones ne peuvent joindre l'application que par le Wi-Fi de l'ordinateur."""
    if os.environ.get("QUIZ_PUBLIC_URL") or codespace_url(request):
        return False
    return (request.url.hostname or "") in ("localhost", "127.0.0.1", "::1")


def public_base(request: Request) -> str:
    """URL que les téléphones doivent ouvrir (adresse réseau local si on est sur localhost)."""
    if os.environ.get("QUIZ_PUBLIC_URL"):
        return os.environ["QUIZ_PUBLIC_URL"].rstrip("/")
    codespace = codespace_url(request)
    if codespace:
        return codespace
    base = str(request.base_url).rstrip("/")
    host = request.url.hostname or ""
    if host in ("localhost", "127.0.0.1", "::1"):
        port = f":{request.url.port}" if request.url.port else ""
        return f"{request.url.scheme}://{lan_ip()}{port}"
    return base


def new_code(s) -> str:
    while True:
        code = f"{random.randint(0, 999999):06d}"
        if not s.scalar(select(db.GameSession.id).where(db.GameSession.code == code)):
            return code


def quiz_or_404(s, quiz_id: int) -> db.Quiz:
    quiz = s.get(db.Quiz, quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz introuvable.")
    return quiz


def session_or_404(s, code: str) -> db.GameSession:
    gs = services.get_session(s, code)
    if not gs:
        raise HTTPException(404, "Partie introuvable.")
    return gs


# ------------------------------------------------------------------ pages
def page(name: str):
    def view(request: Request):
        return templates.TemplateResponse(request, name, {})
    return view


app.get("/")(page("home.html"))
app.get("/play")(page("play_code.html"))


@app.get("/quizzes", dependencies=[Depends(admin_required)])
def quizzes_page(request: Request):
    return templates.TemplateResponse(request, "quizzes.html", {})


@app.get("/quizzes/new", dependencies=[Depends(admin_required)])
def quiz_new_page(request: Request):
    return templates.TemplateResponse(request, "editor.html", {"quiz_id": ""})


@app.get("/quizzes/{quiz_id}/edit", dependencies=[Depends(admin_required)])
def quiz_edit_page(request: Request, quiz_id: int):
    return templates.TemplateResponse(request, "editor.html", {"quiz_id": quiz_id})


@app.get("/history", dependencies=[Depends(admin_required)])
def history_page(request: Request):
    return templates.TemplateResponse(request, "history.html", {})


@app.get("/j/{code}")
def join_page(request: Request, code: str, s=Depends(get_db)):
    gs = services.get_session(s, code)
    # QR code unique pour les deux modes : « quand on veut » ouvre l'écran à son rythme, sinon partie en direct.
    return templates.TemplateResponse(request, "open.html" if gs and gs.mode == "open" else "play.html", {"code": code})


@app.get("/open/{code}", dependencies=[Depends(admin_required)])
def open_admin_page(request: Request, code: str, s=Depends(get_db)):
    open_session(s, code)
    base = public_base(request)
    local = is_local_only(request)
    return templates.TemplateResponse(request, "open_admin.html", {
        "code": code, "join_url": f"{base}/j/{code}", "join_short": base.split("://", 1)[-1] + "/play", "local_only": local})


@app.get("/host/{code}", dependencies=[Depends(admin_required)])
def host_page(request: Request, code: str):
    game = manager.get(code)
    if not game:
        return templates.TemplateResponse(request, "message.html", {
            "title": "Partie expirée",
            "text": "Cette partie n'est plus active (le serveur a peut-être redémarré). Lancez-en une nouvelle."},
            status_code=404)
    base = public_base(request)
    local = is_local_only(request)
    return templates.TemplateResponse(request, "host.html", {
        "code": code, "host_key": request.query_params.get("k", ""),
        "join_url": f"{base}/j/{code}", "join_short": base.split("://", 1)[-1] + "/play", "local_only": local})


@app.get("/solo/{code}")
def solo_page(request: Request, code: str):
    return templates.TemplateResponse(request, "solo.html", {"code": code})


@app.get("/results/{code}")
def results_page(request: Request, code: str):
    return templates.TemplateResponse(request, "results.html", {"code": code})


@app.get("/review/{code}")
def review_page(request: Request, code: str):
    return templates.TemplateResponse(request, "review.html", {"code": code})


@app.get("/qr/{code}.svg")
def qr_svg(request: Request, code: str):
    img = qrcode.make(f"{public_base(request)}/j/{code}", image_factory=qrcode.image.svg.SvgPathImage,
                      box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return Response(buf.getvalue(), media_type="image/svg+xml")


# ------------------------------------------------------------------ API quiz
def quiz_summary(q: db.Quiz) -> dict:
    return {"id": q.id, "title": q.title, "description": q.description,
            "questions": len(q.questions), "created_at": q.created_at.isoformat()}


@app.get("/api/quizzes", dependencies=[Depends(admin_required)])
def list_quizzes(s=Depends(get_db)):
    return [quiz_summary(q) for q in s.scalars(select(db.Quiz).order_by(db.Quiz.created_at.desc()))]


@app.get("/api/quizzes/{quiz_id}", dependencies=[Depends(admin_required)])
def get_quiz(quiz_id: int, s=Depends(get_db)):
    q = quiz_or_404(s, quiz_id)
    return {"id": q.id, "title": q.title, "description": q.description,
            "questions": [x.to_dict() for x in q.questions]}


@app.post("/api/quizzes", dependencies=[Depends(admin_required)])
def post_quiz(data: QuizIn, s=Depends(get_db)):
    return {"id": create_quiz(s, data).id}


@app.put("/api/quizzes/{quiz_id}", dependencies=[Depends(admin_required)])
def put_quiz(quiz_id: int, data: QuizIn, s=Depends(get_db)):
    quiz = quiz_or_404(s, quiz_id)
    quiz.title, quiz.description = data.title, data.description
    # Les questions sont recréées ; les anciennes parties gardent leur historique
    # uniquement tant que le quiz n'est pas modifié : on conserve donc les ids existants.
    old = list(quiz.questions)
    for i, q in enumerate(data.questions):
        row = old[i] if i < len(old) else db.Question(quiz_id=quiz.id)
        row.position, row.kind, row.text = i, q.kind, q.text
        row.media_type, row.media_url = q.media_type, q.media_url
        row.choices_json = json.dumps(q.choices, ensure_ascii=False)
        row.correct = q.correct
        row.accepted_json = json.dumps(q.accepted, ensure_ascii=False)
        row.time_limit, row.explanation = q.time_limit, q.explanation
        if i >= len(old):
            quiz.questions.append(row)
    for extra in old[len(data.questions):]:
        quiz.questions.remove(extra)
    s.commit()
    return {"id": quiz.id}


@app.post("/api/quizzes/{quiz_id}/duplicate", dependencies=[Depends(admin_required)])
def duplicate_quiz(quiz_id: int, s=Depends(get_db)):
    src = quiz_or_404(s, quiz_id)
    data = QuizIn(title=f"{src.title} (copie)"[:80], description=src.description,
                  questions=[x.to_dict() for x in src.questions])
    return {"id": create_quiz(s, data).id}


@app.delete("/api/quizzes/{quiz_id}", dependencies=[Depends(admin_required)])
def delete_quiz(quiz_id: int, s=Depends(get_db)):
    s.delete(quiz_or_404(s, quiz_id))
    s.commit()
    return {"ok": True}


ALLOWED_UPLOADS = {
    "image": {".png", ".jpg", ".jpeg", ".gif", ".webp"},
    "video": {".mp4", ".webm"},
    "audio": {".mp3", ".ogg", ".wav", ".m4a"},
}


@app.post("/api/upload", dependencies=[Depends(admin_required)])
async def upload(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    kind = next((k for k, exts in ALLOWED_UPLOADS.items() if ext in exts), None)
    if not kind:
        raise HTTPException(400, "Format non accepté (images png/jpg/gif/webp, vidéos mp4/webm, sons mp3/ogg/wav/m4a).")
    name = f"{uuid.uuid4().hex}{ext}"
    size, limit = 0, MAX_UPLOAD_MB * 1024 * 1024
    with open(MEDIA_DIR / name, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                out.close()
                (MEDIA_DIR / name).unlink(missing_ok=True)
                raise HTTPException(413, f"Fichier trop volumineux (maximum {MAX_UPLOAD_MB} Mo).")
            out.write(chunk)
    return {"url": f"/media/{name}", "media_type": kind}


# ------------------------------------------------------------------ API parties
@app.post("/api/sessions", dependencies=[Depends(admin_required)])
def create_session(data: SessionIn, s=Depends(get_db)):
    quiz = quiz_or_404(s, data.quiz_id)
    if not quiz.questions:
        raise HTTPException(400, "Ce quiz n'a aucune question.")
    code = new_code(s)
    gs = db.GameSession(code=code, quiz_id=quiz.id, mode=data.mode,
                        host_key=secrets.token_urlsafe(12),
                        status="lobby" if data.mode == "multi" else "running")
    s.add(gs)
    s.flush()
    if data.mode == "solo":
        names = [" ".join(n.split())[:20] for n in data.names if n.strip()]
        if not names:
            raise HTTPException(400, "Saisissez au moins un prénom.")
        if len({n.lower() for n in names}) != len(names):
            raise HTTPException(400, "Deux joueurs ont le même prénom.")
        for n in names:
            s.add(db.Player(session_id=gs.id, name=n))
        s.commit()
        return {"code": code, "url": f"/solo/{code}"}
    s.commit()
    if data.mode == "open":
        return {"code": code, "url": f"/open/{code}"}
    manager.register(Game(gs.id, code, gs.host_key, quiz.title, [q.to_dict() for q in quiz.questions],
                          auto=data.auto, auto_delay=data.auto_delay))
    return {"code": code, "url": f"/host/{code}?k={gs.host_key}"}


@app.get("/api/sessions/{code}/exists")
def session_exists(code: str, s=Depends(get_db)):
    game = manager.get(code)
    if not game:
        gs = services.get_session(s, code.strip())
        if gs and gs.mode == "open" and gs.status != "finished":
            return {"title": gs.quiz.title, "phase": "open"}
        raise HTTPException(404, "Code inconnu ou partie expirée.")
    return {"title": game.title, "phase": game.phase}


@app.post("/api/join")
async def join(data: JoinIn):
    game = manager.get(data.code.strip())
    if not game:
        raise HTTPException(404, "Code inconnu ou partie expirée.")
    try:
        pid, token = game.add_player(data.name)
    except GameError as e:
        raise HTTPException(400, str(e))
    await game.broadcast(only_hosts=True)
    return {"token": token, "name": game.players[pid]["name"]}


@app.get("/api/sessions/{code}/results")
def get_results(code: str, s=Depends(get_db)):
    return services.results(s, session_or_404(s, code))


@app.get("/api/sessions/{code}/review")
def get_review(code: str, s=Depends(get_db)):
    gs = session_or_404(s, code)
    if gs.mode == "open" and gs.status != "finished":     # sinon les premiers à finir souffleraient les réponses aux autres
        raise HTTPException(403, "Les réponses seront visibles quand l'organisateur clôturera le quiz.")
    return services.review(s, gs)


@app.get("/api/history", dependencies=[Depends(admin_required)])
def get_history(s=Depends(get_db)):
    return services.history(s)


@app.get("/api/sessions/{code}/export.xlsx", dependencies=[Depends(admin_required)])
def export_xlsx(code: str, s=Depends(get_db)):
    gs = session_or_404(s, code)
    return Response(services.export_xlsx(s, gs),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="resultats-{code}.xlsx"'})


@app.post("/api/open/{code}/close", dependencies=[Depends(admin_required)])
def close_open_session(code: str, s=Depends(get_db)):
    gs = open_session(s, code)
    if gs.status != "finished":
        gs.status, gs.finished_at = "finished", db.now()
        s.commit()
    return {"ok": True}


@app.delete("/api/sessions/{code}", dependencies=[Depends(admin_required)])
def delete_session(code: str, s=Depends(get_db)):
    s.delete(session_or_404(s, code))
    s.commit()
    manager.games.pop(code, None)
    return {"ok": True}


# ------------------------------------------------------------------ mode « un seul téléphone »
@app.get("/api/solo/{code}")
def solo_info(code: str, s=Depends(get_db)):
    gs = session_or_404(s, code)
    if gs.mode != "solo":
        raise HTTPException(404, "Partie introuvable.")
    qindex = {q.id: i for i, q in enumerate(gs.quiz.questions)}
    return {"title": gs.quiz.title, "status": gs.status,
            "players": [{"id": p.id, "name": p.name, "score": p.score,
                         "done": sorted(qindex[a.question_id] for a in p.answers)} for p in gs.players],
            "questions": [q.to_dict(with_answer=False) for q in gs.quiz.questions]}


@app.post("/api/solo/{code}/answer")
async def solo_answer(code: str, request: Request, s=Depends(get_db)):
    gs = session_or_404(s, code)
    body = await request.json()
    player = next((p for p in gs.players if p.id == body.get("player_id")), None)
    qs = gs.quiz.questions
    idx = body.get("question_index")
    if gs.mode != "solo" or gs.status == "finished" or not player or not isinstance(idx, int) or not 0 <= idx < len(qs):
        raise HTTPException(400, "Réponse invalide.")
    q = qs[idx]
    if any(a.question_id == q.id for a in player.answers):
        raise HTTPException(409, "Déjà répondu.")
    d, value = q.to_dict(), body.get("value")
    if d["kind"] != "libre" and (not isinstance(value, int) or not 0 <= value < len(d["choices"])):
        value = None
    ok = is_correct(d, value)
    full = d["time_limit"] * 1000
    raw = body.get("elapsed_ms")
    elapsed = min(max(int(raw), 0), full) if value is not None and isinstance(raw, (int, float)) else full
    pts = compute_points(ok, d["time_limit"], elapsed)
    s.add(db.Answer(player_id=player.id, question_id=q.id, value=given_text(d, value), correct=ok,
                    points=pts, elapsed_ms=elapsed))
    player.score += pts
    s.commit()
    return {"correct": ok, "points": pts, "score": player.score, "correct_text": correct_text(d),
            "correct_index": d["correct"], "explanation": d["explanation"]}


@app.post("/api/solo/{code}/finish")
def solo_finish(code: str, s=Depends(get_db)):
    gs = session_or_404(s, code)
    if gs.mode == "solo" and gs.status != "finished":
        gs.status, gs.finished_at = "finished", db.now()
        s.commit()
    return {"ok": True}


# ------------------------------------------------------------------ WebSockets
@app.websocket("/ws/host/{code}")
async def ws_host(ws: WebSocket, code: str, k: str = ""):
    game = manager.get(code)
    if not game or not secrets.compare_digest(k, game.host_key):
        await ws.close(code=4404)
        return
    await ws.accept()
    await game.connect_host(ws)
    try:
        while True:
            await game.on_host(await ws.receive_json())
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        game.disconnect(ws)


@app.websocket("/ws/play/{code}")
async def ws_play(ws: WebSocket, code: str, token: str = ""):
    game = manager.get(code)
    pid = game.player_by_token(token) if game else None
    if not game or pid is None:
        await ws.close(code=4404)
        return
    await ws.accept()
    await game.connect_player(ws, pid)
    try:
        while True:
            msg = await ws.receive_json()
            if isinstance(msg, dict) and msg.get("type") == "answer":
                await game.on_answer(pid, msg)
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        game.disconnect(ws)
