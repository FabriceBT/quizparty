"""Schémas de validation des quiz envoyés par l'éditeur."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SAFE_PREFIXES = ("/media/", "/static/", "https://", "http://")


class QuestionIn(BaseModel):
    kind: Literal["qcm", "vf", "libre"]
    text: str = Field(min_length=1, max_length=300)
    media_type: Literal["none", "image", "video", "audio"] = "none"
    media_url: str = Field(default="", max_length=500)
    choices: list[str] = []
    correct: int | None = None
    accepted: list[str] = []
    time_limit: Literal[10, 15, 20, 30] = 20
    explanation: str = Field(default="", max_length=500)

    @field_validator("text", "explanation")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def _check(self):
        if self.media_type == "none":
            self.media_url = ""
        elif not self.media_url.startswith(SAFE_PREFIXES):
            raise ValueError("Adresse du média invalide.")
        if self.kind == "vf":
            self.choices = ["Vrai", "Faux"]
            if self.correct not in (0, 1):
                raise ValueError("Choisissez Vrai ou Faux.")
            self.accepted = []
        elif self.kind == "qcm":
            self.choices = [c.strip()[:100] for c in self.choices]
            if not 2 <= len(self.choices) <= 4 or not all(self.choices):
                raise ValueError("Un QCM a de 2 à 4 réponses, toutes remplies.")
            if self.correct is None or not 0 <= self.correct < len(self.choices):
                raise ValueError("Désignez la bonne réponse.")
            self.accepted = []
        else:  # libre
            self.choices, self.correct = [], None
            self.accepted = [a.strip()[:100] for a in self.accepted if a.strip()]
            if not self.accepted:
                raise ValueError("Indiquez au moins une réponse acceptée.")
        return self


class QuizIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)
    questions: list[QuestionIn] = Field(min_length=1, max_length=100)

    @field_validator("title", "description")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class SessionIn(BaseModel):
    quiz_id: int
    mode: Literal["multi", "solo", "open"]
    names: list[str] = []
    auto: bool = False                                  # multi : enchaîne les questions sans l'organisateur
    auto_delay: int = Field(default=8, ge=1, le=60)     # pause (s) avant la question suivante


class JoinIn(BaseModel):
    code: str
    name: str
