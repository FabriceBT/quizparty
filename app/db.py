"""Modèles SQLAlchemy et accès base de données."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import (Boolean, DateTime, ForeignKey, Integer, String, Text,
                        UniqueConstraint, create_engine, event)
from sqlalchemy.orm import (DeclarativeBase, Mapped, mapped_column,
                            relationship, sessionmaker)

from .config import DB_URL


def now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Quiz(Base):
    __tablename__ = "quizzes"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    questions: Mapped[list["Question"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan", order_by="Question.position")
    sessions: Mapped[list["GameSession"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(String(10))          # qcm | vf | libre
    text: Mapped[str] = mapped_column(String(300))
    media_type: Mapped[str] = mapped_column(String(10), default="none")  # none|image|video|audio
    media_url: Mapped[str] = mapped_column(String(500), default="")
    choices_json: Mapped[str] = mapped_column(Text, default="[]")
    correct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accepted_json: Mapped[str] = mapped_column(Text, default="[]")
    time_limit: Mapped[int] = mapped_column(Integer, default=20)
    explanation: Mapped[str] = mapped_column(String(500), default="")
    quiz: Mapped[Quiz] = relationship(back_populates="questions")

    @property
    def choices(self) -> list[str]:
        return json.loads(self.choices_json)

    @property
    def accepted(self) -> list[str]:
        return json.loads(self.accepted_json)

    def to_dict(self, with_answer: bool = True) -> dict:
        d = {"id": self.id, "kind": self.kind, "text": self.text,
             "media_type": self.media_type, "media_url": self.media_url,
             "choices": self.choices, "time_limit": self.time_limit}
        if with_answer:
            d.update(correct=self.correct, accepted=self.accepted, explanation=self.explanation)
        return d


class GameSession(Base):
    """Une partie jouée (en direct sur plusieurs téléphones, ou sur un seul)."""
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"))
    mode: Mapped[str] = mapped_column(String(10))           # multi | solo | open (chacun joue quand il veut)
    status: Mapped[str] = mapped_column(String(10), default="lobby")  # lobby|running|finished
    host_key: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quiz: Mapped[Quiz] = relationship(back_populates="sessions")
    players: Mapped[list["Player"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Player.id")


class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(20))
    token: Mapped[str] = mapped_column(String(40), default="")
    score: Mapped[int] = mapped_column(Integer, default=0)
    session: Mapped[GameSession] = relationship(back_populates="players")
    answers: Mapped[list["Answer"]] = relationship(cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("player_id", "question_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    value: Mapped[str] = mapped_column(String(200), default="")   # texte de la réponse donnée
    correct: Mapped[bool] = mapped_column(Boolean, default=False)
    points: Mapped[int] = mapped_column(Integer, default=0)
    elapsed_ms: Mapped[int] = mapped_column(Integer, default=0)


_engine = None
SessionLocal = sessionmaker(autoflush=False, expire_on_commit=False)


def init_db(url: str = DB_URL):
    """Crée le moteur et les tables (idempotent)."""
    global _engine
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    _engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def _fk(dbapi_conn, _):  # clés étrangères actives sous SQLite
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(_engine)
    SessionLocal.configure(bind=_engine)
    return _engine
