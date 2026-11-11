"""Sauvegarde / restauration : un fichier ZIP contenant tous les quiz (quizzes.json) et leurs médias importés.

Utile sur les hébergements gratuits dont le disque est effacé à chaque redémarrage : on télécharge la sauvegarde,
et on la remet en un clic après un redéploiement.
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import zipfile
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import select

from . import db
from pathlib import Path

from .config import BASE_DIR, MAX_UPLOAD_MB, MEDIA_DIR
from .schemas import QuizIn
from .seed import create_quiz

router = APIRouter()
log = logging.getLogger("uvicorn.error")
SEED_DIR = Path(os.environ.get("QUIZ_SEED_DIR", BASE_DIR / "seed"))
MEDIA_NAME = re.compile(r"^[0-9a-f]{32}\.[a-z0-9]{2,5}$")        # noms générés par l'import de médias
MAX_ZIP = max(MAX_UPLOAD_MB, 20) * 8 * 1024 * 1024               # taille décompressée maximale


def get_db():
    with db.SessionLocal() as s:
        yield s


def _admin(request: Request):
    from .main import admin_required
    return admin_required(request)


@router.get("/api/backup", dependencies=[Depends(_admin)])
def backup(s=Depends(get_db)):
    quizzes, media = [], set()
    for q in s.scalars(select(db.Quiz).order_by(db.Quiz.id)):
        quizzes.append({"title": q.title, "description": q.description, "category": q.category, "published": q.published,
                        "questions": [{k: v for k, v in x.to_dict().items() if k != "id"} for x in q.questions]})
        media.update(x.media_url.rsplit("/", 1)[-1] for x in q.questions if x.media_url.startswith("/media/"))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("quizzes.json", json.dumps({"app": "quizparty", "version": 1, "quizzes": quizzes}, ensure_ascii=False, indent=1))
        for name in sorted(media):
            f = MEDIA_DIR / name
            if MEDIA_NAME.match(name) and f.is_file():
                z.write(f, f"media/{name}")
    return Response(buf.getvalue(), media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="quizparty-sauvegarde-{date.today().isoformat()}.zip"'})


def import_backup(raw: bytes, s) -> dict:
    """Importe un ZIP de sauvegarde (quiz + médias) sans dupliquer les quiz déjà présents. Lève ValueError si le fichier est invalide."""
    if len(raw) > MAX_ZIP:
        raise ValueError("Fichier trop volumineux.")
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
        if sum(i.file_size for i in z.infolist()) > MAX_ZIP:
            raise ValueError("Fichier trop volumineux une fois décompressé.")
        items = json.loads(z.read("quizzes.json"))["quizzes"]
    except ValueError:
        raise
    except Exception:
        raise ValueError("Ce fichier n'est pas une sauvegarde Quiz Party valide.")
    for info in z.infolist():                                   # médias : uniquement des noms attendus, jamais de chemin
        name = info.filename.removeprefix("media/")
        if info.filename.startswith("media/") and MEDIA_NAME.match(name) and not (MEDIA_DIR / name).exists():
            (MEDIA_DIR / name).write_bytes(z.read(info))
    existing = {(q.title, len(q.questions), q.questions[0].text if q.questions else "") for q in s.scalars(select(db.Quiz))}
    added = skipped = 0
    for it in items:
        try:
            quiz = QuizIn(**it)
        except Exception:
            skipped += 1
            continue
        key = (quiz.title, len(quiz.questions), quiz.questions[0].text)
        if key in existing:                                     # déjà présent : on ne le duplique pas
            skipped += 1
            continue
        row = create_quiz(s, quiz)
        row.published = bool(it.get("published", True))
        s.commit()
        existing.add(key)
        added += 1
    return {"added": added, "skipped": skipped}


@router.post("/api/restore", dependencies=[Depends(_admin)])
async def restore(file: UploadFile = File(...), s=Depends(get_db)):
    try:
        return import_backup(await file.read(MAX_ZIP + 1), s)
    except ValueError as e:
        raise HTTPException(400, str(e))


def load_seed_backups(s) -> None:
    """Au démarrage : importe les sauvegardes ZIP déposées dans le dossier « seed » du dépôt (QUIZ_SEED_DIR).
    Sur un hébergement gratuit dont le disque est effacé à chaque redémarrage, c'est ce qui remet les quiz en place."""
    folder = SEED_DIR
    for f in sorted(folder.glob("*.zip")) if folder.is_dir() else []:
        try:
            res = import_backup(f.read_bytes(), s)
            log.info("Sauvegarde %s : %s quiz ajoutés, %s déjà présents", f.name, res["added"], res["skipped"])
        except Exception as e:                                  # un fichier abîmé ne doit pas empêcher le démarrage
            log.warning("Sauvegarde %s ignorée : %s", f.name, e)
