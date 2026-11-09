"""Requêtes de lecture : classement final, revue des réponses, export Excel."""
from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import db
from .config import LIBRARY_WEEKLY
from .schemas import TEAMS
from .scoring import correct_text, rank_of


def get_session(s: Session, code: str) -> db.GameSession | None:
    return s.scalar(select(db.GameSession).where(db.GameSession.code == code))


def results(s: Session, gs: db.GameSession) -> dict:
    total = len(gs.quiz.questions)
    scores = [p.score for p in gs.players]
    rows = []
    for p in gs.players:
        good = sum(1 for a in p.answers if a.correct)
        rows.append({"name": p.name, "score": p.score, "correct": good, "total": total,
                     "pct": round(100 * good / total) if total else 0, "answered": len(p.answers),
                     "rank": rank_of(p.score, scores), "team": p.team})
    rows.sort(key=lambda r: (r["rank"], r["name"].lower()))
    teams = []
    for key, label in TEAMS.items():
        members = [r["score"] for r in rows if r["team"] == key]
        if members:
            teams.append({"team": key, "label": label, "players": len(members), "total": sum(members),
                          "avg": round(sum(members) / len(members))})
    teams.sort(key=lambda t: -t["avg"])
    return {"code": gs.code, "title": gs.quiz.title, "mode": gs.mode, "status": gs.status, "library": gs.host_key == "library", "weekly": gs.host_key == "library" and LIBRARY_WEEKLY,
            "date": gs.created_at.isoformat(), "total_questions": total, "players": rows, "teams": teams}


def review(s: Session, gs: db.GameSession) -> dict:
    names = {p.id: p.name for p in gs.players}
    by_q: dict[int, list[db.Answer]] = {}
    for p in gs.players:
        for a in p.answers:
            by_q.setdefault(a.question_id, []).append(a)
    out = []
    total = len(gs.quiz.questions)
    for i, q in enumerate(gs.quiz.questions):
        d = q.to_dict()
        answers = sorted(by_q.get(q.id, []), key=lambda a: (-a.points, a.elapsed_ms))
        pts = [a.points for a in answers]
        out.append({"index": i, "total": total, "kind": q.kind, "text": q.text,
                    "media_type": q.media_type, "media_url": q.media_url,
                    "correct_text": correct_text(d), "explanation": q.explanation,
                    "answers": [{"name": names[a.player_id], "given": a.value, "correct": a.correct,
                                 "points": a.points, "rank": rank_of(a.points, pts)} for a in answers]})
    return {"code": gs.code, "title": gs.quiz.title, "questions": out}


def history(s: Session) -> list[dict]:
    rows = []
    for gs in s.scalars(select(db.GameSession).order_by(db.GameSession.created_at.desc()).limit(100)):
        best = max(gs.players, key=lambda p: p.score, default=None)
        rows.append({"code": gs.code, "title": gs.quiz.title, "mode": gs.mode, "status": gs.status,
                     "date": gs.created_at.isoformat(), "players": len(gs.players),
                     "winner": best.name if best and gs.status == "finished" else None,
                     "top_score": best.score if best else 0})
    return rows


def export_xlsx(s: Session, gs: db.GameSession) -> bytes:
    res, rev = results(s, gs), review(s, gs)
    wb = Workbook()
    head_font, head_fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="6C4CF5")

    def sheet(ws, header, rows, widths):
        ws.append(header)
        for c in ws[1]:
            c.font, c.fill = head_font, head_fill
        for r in rows:
            ws.append(r)
        for col, w in zip("ABCDEF", widths):
            ws.column_dimensions[col].width = w

    ws = wb.active
    ws.title = "Classement"
    sheet(ws, ["Rang", "Joueur", "Points", "Bonnes réponses", "Questions", "% de réussite"],
          [[r["rank"], r["name"], r["score"], r["correct"], r["total"], r["pct"] / 100] for r in res["players"]],
          [8, 24, 10, 16, 12, 14])
    for row in ws.iter_rows(min_row=2, min_col=6, max_col=6):
        row[0].number_format = "0%"
    sheet(wb.create_sheet("Détail"), ["N°", "Question", "Joueur", "Réponse donnée", "Bonne réponse", "Juste ?"],
          [[q["index"] + 1, q["text"], a["name"], a["given"] or "(pas de réponse)", q["correct_text"],
            "Oui" if a["correct"] else "Non"] for q in rev["questions"] for a in q["answers"]],
          [6, 50, 20, 28, 28, 10])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
