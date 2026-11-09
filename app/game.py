"""Moteur de partie en direct (multi-téléphones) : état en mémoire + WebSockets.

Phases : lobby -> question -> reveal -> question -> ... -> finished
Le serveur est la seule source de vérité (chrono compris) : les clients reçoivent
un « instantané » complet à chaque changement, ce qui rend les reconnexions triviales.
"""
from __future__ import annotations

import asyncio
import secrets
import time

from fastapi import WebSocket

from . import db
from .config import MAX_PLAYERS
from .schemas import TEAMS
from .scoring import (JOKER_FACTOR, clean_value, compute_points, correct_text,
                      given_text, is_correct, joker_hidden, rank_of, reveal_extra, shown_choices, streak_bonus)

GRACE_S = 0.4   # tolérance réseau après la fin du chrono
AUTO_DELAY_MIN, AUTO_DELAY_MAX, AUTO_DELAY_DEFAULT = 1, 60, 8   # pause (s) entre la révélation et la question suivante
AUTO_START_MAX, AUTO_START_DEFAULT = 3600, 30   # mode automatique : le quiz démarre N s après l'arrivée du 1er joueur (0 = manuel)


def clamp_start(value) -> int:
    try:
        return max(0, min(AUTO_START_MAX, int(value)))
    except (TypeError, ValueError):
        return AUTO_START_DEFAULT


def clamp_delay(value) -> int:
    try:
        return max(AUTO_DELAY_MIN, min(AUTO_DELAY_MAX, int(value)))
    except (TypeError, ValueError):
        return AUTO_DELAY_DEFAULT


class GameError(Exception):
    """Erreur affichable à l'utilisateur (message en français)."""


class Game:
    def __init__(self, session_id: int, code: str, host_key: str, title: str, questions: list[dict],
                 auto: bool = False, auto_delay: int = AUTO_DELAY_DEFAULT, auto_start: int = AUTO_START_DEFAULT):
        self.session_id, self.code, self.host_key = session_id, code, host_key
        self.title, self.questions = title, questions
        # Mode automatique : après chaque révélation, la question suivante (ou le podium) arrive
        # toute seule, même si l'organisateur est déconnecté.
        self.auto = auto
        self.auto_delay = clamp_delay(auto_delay)
        self.auto_timer: asyncio.Task | None = None
        self.next_at = 0.0                     # échéance (monotonic) du prochain enchaînement automatique
        # Démarrage automatique : le compte à rebours part à l'arrivée du premier joueur (0 = l'organisateur lance).
        self.auto_start = clamp_start(auto_start)
        self.start_timer: asyncio.Task | None = None
        self.start_at = 0.0
        self.phase = "lobby"
        self.q_index = -1
        self.deadline = 0.0
        self.players: dict[int, dict] = {}     # pid -> {name, token, score, team, streak}
        self.current: dict[int, dict] = {}     # réponses de la question en cours
        self.joker_used: set[int] = set()      # joueurs ayant déjà utilisé leur joker 50/50 (un seul par partie)
        self.hidden: dict[int, list[int]] = {} # joueur -> réponses masquées par le joker sur la question en cours
        self.hosts: set[WebSocket] = set()
        self.sockets: dict[int, set[WebSocket]] = {}
        self.timer: asyncio.Task | None = None
        self.finished_at = 0.0

    # ------------------------------------------------------------ joueurs
    def add_player(self, name: str, team: str = "") -> tuple[int, str]:
        name = " ".join(name.split())[:20]
        if not name:
            raise GameError("Entrez un prénom.")
        if self.phase == "finished":
            raise GameError("Cette partie est terminée.")
        if len(self.players) >= MAX_PLAYERS:
            raise GameError("La partie est complète.")
        if any(p["name"].lower() == name.lower() for p in self.players.values()):
            raise GameError("Ce prénom est déjà pris, ajoutez une initiale.")
        team = team if team in TEAMS else ""
        token = secrets.token_urlsafe(16)
        with db.SessionLocal() as s:
            pl = db.Player(session_id=self.session_id, name=name, token=token, team=team)
            s.add(pl)
            s.commit()
            pid = pl.id
        self.players[pid] = {"name": name, "token": token, "score": 0, "team": team, "streak": 0}
        self._maybe_schedule_start()
        return pid, token

    # ------------------------------------------------ démarrage automatique
    def _maybe_schedule_start(self):
        """Lance le compte à rebours de démarrage dès qu'il y a un joueur (mode automatique, salle d'attente)."""
        if self.auto and self.auto_start and self.phase == "lobby" and self.players and not self.start_timer:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:                 # hors boucle asyncio (ex. appel synchrone) : l'organisateur lancera
                return
            self.start_at = time.monotonic() + self.auto_start
            self.start_timer = loop.create_task(self._auto_start(self.auto_start))

    def _cancel_start_timer(self):
        if self.start_timer and self.start_timer is not asyncio.current_task():
            self.start_timer.cancel()
        self.start_timer, self.start_at = None, 0.0

    async def _auto_start(self, delay: float):
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
        if self.auto and self.phase == "lobby" and self.players:
            await self._next_question()

    def player_by_token(self, token: str) -> int | None:
        for pid, p in self.players.items():
            if secrets.compare_digest(p["token"], token or ""):
                return pid
        return None

    # --------------------------------------------------------- connexions
    async def _send(self, ws: WebSocket, data: dict) -> bool:
        try:
            await ws.send_json(data)
            return True
        except Exception:
            return False

    async def connect_host(self, ws: WebSocket):
        self.hosts.add(ws)
        await self._send(ws, self.snapshot("host"))

    async def connect_player(self, ws: WebSocket, pid: int):
        self.sockets.setdefault(pid, set()).add(ws)
        await self._send(ws, self.snapshot("player", pid))
        await self.broadcast(only_hosts=True)   # le compteur de joueurs change

    def disconnect(self, ws: WebSocket):
        self.hosts.discard(ws)
        for conns in self.sockets.values():
            conns.discard(ws)

    async def broadcast(self, only_hosts: bool = False):
        for ws in list(self.hosts):
            if not await self._send(ws, self.snapshot("host")):
                self.hosts.discard(ws)
        if only_hosts:
            return
        for pid, conns in list(self.sockets.items()):
            for ws in list(conns):
                if not await self._send(ws, self.snapshot("player", pid)):
                    conns.discard(ws)

    # ------------------------------------------------------------ actions
    async def on_host(self, msg: dict):
        t = msg.get("type")
        if t == "start" and self.phase == "lobby":
            if not self.players:
                for ws in list(self.hosts):
                    await self._send(ws, {"type": "error", "message": "Attendez au moins un joueur."})
                return
            await self._next_question()
        elif t == "next" and self.phase == "reveal":
            await self._next_question()
        elif t == "skip" and self.phase == "question":
            await self._reveal()
        elif t == "auto" and self.phase != "finished":
            await self._set_auto(bool(msg.get("value")), msg.get("delay", self.auto_delay),
                                 msg.get("start_delay", self.auto_start))

    async def _set_auto(self, enabled: bool, delay, start_delay):
        """Active / règle / coupe le mode automatique, y compris en pleine partie."""
        self.auto, self.auto_delay, self.auto_start = enabled, clamp_delay(delay), clamp_start(start_delay)
        self._cancel_auto_timer()
        if self.auto and self.phase == "reveal":
            self._schedule_auto_next()
        self._cancel_start_timer()               # le compte à rebours repart avec les nouveaux réglages
        self._maybe_schedule_start()
        await self.broadcast()

    def _cancel_auto_timer(self):
        if self.auto_timer and self.auto_timer is not asyncio.current_task():
            self.auto_timer.cancel()
        self.auto_timer, self.next_at = None, 0.0

    def _schedule_auto_next(self):
        self.next_at = time.monotonic() + self.auto_delay
        self.auto_timer = asyncio.create_task(self._auto_next(self.q_index, self.auto_delay))

    async def _auto_next(self, idx: int, delay: float):
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
        if self.auto and self.phase == "reveal" and self.q_index == idx:
            await self._next_question()

    async def on_answer(self, pid: int, msg: dict):
        if self.phase != "question" or pid in self.current:
            return
        now = time.monotonic()
        if now > self.deadline + GRACE_S:
            return
        q = self.questions[self.q_index]
        value = clean_value(q, msg.get("value"))
        if value is None or (isinstance(value, int) and value in self.hidden.get(pid, ())):
            return
        elapsed_ms = int((q["time_limit"] - max(self.deadline - now, 0)) * 1000)
        ok = is_correct(q, value)
        base = compute_points(ok, q["time_limit"], elapsed_ms)
        if ok and pid in self.hidden:                      # joker utilisé : la bonne réponse vaut moitié moins
            base = round(base * JOKER_FACTOR)
        streak = self.players[pid]["streak"] + 1 if ok else 0
        bonus = streak_bonus(streak) if ok else 0
        self.current[pid] = {"value": value, "text": given_text(q, value), "correct": ok,
                             "points": base + bonus, "bonus": bonus, "streak": streak, "elapsed": elapsed_ms}
        if len(self.current) >= len(self.players):
            await self._reveal()
        else:
            await self.broadcast(only_hosts=True)
            await self._send_to_player(pid)

    async def on_joker(self, pid: int):
        """Joker 50/50 : masque la moitié des mauvaises réponses d'un QCM. Un seul par joueur et par partie."""
        if self.phase != "question" or pid in self.current or pid in self.joker_used:
            return
        hidden = joker_hidden(self.questions[self.q_index], pid)
        if not hidden:
            return
        self.joker_used.add(pid)
        self.hidden[pid] = hidden
        await self._send_to_player(pid)

    async def _send_to_player(self, pid: int):
        for ws in list(self.sockets.get(pid, ())):
            await self._send(ws, self.snapshot("player", pid))

    # ------------------------------------------------------ enchaînement
    async def _next_question(self):
        self._cancel_auto_timer()
        self._cancel_start_timer()
        self.q_index += 1
        if self.q_index >= len(self.questions):
            await self._finish()
            return
        q = self.questions[self.q_index]
        self.phase = "question"
        self.current = {}
        self.hidden = {}
        self.deadline = time.monotonic() + q["time_limit"]
        with db.SessionLocal() as s:
            gs = s.get(db.GameSession, self.session_id)
            gs.status = "running"
            s.commit()
        self.timer = asyncio.create_task(self._timeout(self.q_index, q["time_limit"] + GRACE_S))
        await self.broadcast()

    async def _timeout(self, idx: int, delay: float):
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
        if self.phase == "question" and self.q_index == idx:
            await self._reveal()

    async def _reveal(self):
        if self.phase != "question":
            return
        self.phase = "reveal"
        if self.timer and self.timer is not asyncio.current_task():
            self.timer.cancel()
        q = self.questions[self.q_index]
        with db.SessionLocal() as s:
            for pid, p in self.players.items():
                a = self.current.setdefault(pid, {"value": None, "text": "", "correct": False, "points": 0,
                                                  "bonus": 0, "streak": 0, "elapsed": q["time_limit"] * 1000})
                p["score"] += a["points"]
                p["streak"] = a["streak"]
                s.add(db.Answer(player_id=pid, question_id=q["id"], value=a["text"],
                                correct=a["correct"], points=a["points"], elapsed_ms=a["elapsed"]))
                s.get(db.Player, pid).score = p["score"]
            s.commit()
        if self.auto:
            self._schedule_auto_next()
        await self.broadcast()

    async def _finish(self):
        self._cancel_auto_timer()
        self.phase = "finished"
        self.finished_at = time.time()
        with db.SessionLocal() as s:
            gs = s.get(db.GameSession, self.session_id)
            gs.status = "finished"
            gs.finished_at = db.now()
            s.commit()
        await self.broadcast()

    # ---------------------------------------------------------- instantané
    def _leaderboard(self) -> list[dict]:
        scores = [p["score"] for p in self.players.values()]
        rows = [{"pid": pid, "name": p["name"], "score": p["score"], "team": p["team"],
                 "rank": rank_of(p["score"], scores),
                 "gained": self.current.get(pid, {}).get("points", 0) if self.phase == "reveal" else 0}
                for pid, p in self.players.items()]
        rows.sort(key=lambda r: (r["rank"], r["name"].lower()))
        return rows

    def teams_board(self) -> list[dict]:
        """Classement des équipes : moyenne de points par joueur (équitable si les équipes sont inégales)."""
        out = []
        for key, label in TEAMS.items():
            members = [p["score"] for p in self.players.values() if p["team"] == key]
            if members:
                out.append({"team": key, "label": label, "players": len(members), "total": sum(members),
                            "avg": round(sum(members) / len(members))})
        out.sort(key=lambda t: -t["avg"])
        return out

    def snapshot(self, role: str, pid: int | None = None) -> dict:
        snap = {"type": "state", "phase": self.phase, "code": self.code, "title": self.title,
                "player_count": len(self.players),
                "players": [p["name"] for p in self.players.values()],
                "auto": self.auto, "auto_delay": self.auto_delay, "auto_start": self.auto_start,
                "teams": self.teams_board()}
        if self.phase == "lobby" and self.auto and self.start_at:
            snap["start_in_ms"] = max(int((self.start_at - time.monotonic()) * 1000), 0)
        if self.phase in ("question", "reveal"):
            q = self.questions[self.q_index]
            snap["question"] = {"index": self.q_index, "total": len(self.questions),
                                "kind": q["kind"], "text": q["text"], "media_type": q["media_type"],
                                "media_url": q["media_url"], "choices": shown_choices(q),
                                "time_limit": q["time_limit"]}
        if self.phase == "question":
            snap["remaining_ms"] = max(int((self.deadline - time.monotonic()) * 1000), 0)
            snap["answered"] = len(self.current)
            if role == "player":
                snap["has_answered"] = pid in self.current
                if pid in self.current:
                    snap["my_value"] = self.current[pid]["value"]
                snap["streak"] = self.players[pid]["streak"] if pid in self.players else 0
                snap["hidden"] = self.hidden.get(pid, [])
                snap["joker_available"] = (pid not in self.joker_used and not snap["has_answered"]
                                           and bool(joker_hidden(q, pid)))
        if self.phase == "reveal":
            q = self.questions[self.q_index]
            dist = None
            if q["kind"] in ("qcm", "vf"):
                dist = [0] * len(q["choices"])
                for a in self.current.values():
                    if isinstance(a["value"], int):
                        dist[a["value"]] += 1
            board = self._leaderboard()
            extra = reveal_extra(q)
            snap["reveal"] = {**extra, "correct_index": q["correct"], "correct_text": correct_text(q),
                              "explanation": q["explanation"], "distribution": dist,
                              "right_count": sum(1 for a in self.current.values() if a["correct"]),
                              "is_last": self.q_index == len(self.questions) - 1,
                              "next_in_ms": (max(int((self.next_at - time.monotonic()) * 1000), 0)
                                             if self.auto and self.next_at else None)}
            snap["leaderboard"] = [{k: r[k] for k in ("name", "score", "rank", "gained", "team")} for r in board[:5]]
            if role == "player" and pid in self.players:
                a = self.current.get(pid, {"correct": False, "points": 0, "text": "", "value": None})   # arrivé pendant la révélation
                me = next(r for r in board if r["pid"] == pid)
                snap["me"] = {"correct": a["correct"], "points": a["points"], "given": a["text"],
                              "value": a.get("value"), "bonus": a.get("bonus", 0), "streak": a.get("streak", 0),
                              "score": me["score"], "rank": me["rank"], "of": len(board)}
        if self.phase == "finished":
            snap["results_url"] = f"/results/{self.code}"
        return snap


class GameManager:
    def __init__(self):
        self.games: dict[str, Game] = {}

    def get(self, code: str) -> Game | None:
        return self.games.get(code)

    def register(self, game: Game):
        # Ménage : on oublie les parties terminées depuis plus de 6 h.
        for c, g in list(self.games.items()):
            if g.phase == "finished" and time.time() - g.finished_at > 6 * 3600:
                del self.games[c]
        self.games[game.code] = game


manager = GameManager()
