"""Jeu de démonstration : 15 questions de culture générale (QCM, vrai/faux, réponse libre, image)."""
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import db
from .schemas import QuizIn

DEMO = {
    "title": "Culture générale – démo",
    "description": "15 questions pour tester Quiz Party : QCM, vrai/faux, réponses libres et image.",
    "questions": [
        {"kind": "qcm", "text": "Quelle est la capitale de l'Australie ?",
         "choices": ["Sydney", "Canberra", "Melbourne", "Perth"], "correct": 1, "time_limit": 15,
         "explanation": "Canberra a été créée de toutes pièces pour être capitale, en compromis entre Sydney et Melbourne."},
        {"kind": "vf", "text": "La Grande Muraille de Chine est visible à l'œil nu depuis la Lune.",
         "correct": 1, "time_limit": 10,
         "explanation": "C'est un mythe : elle est bien trop étroite pour être distinguée à cette distance."},
        {"kind": "qcm", "text": "De quel pays est ce drapeau ?", "media_type": "image",
         "media_url": "/static/demo/drapeau-italie.svg",
         "choices": ["Irlande", "Italie", "Hongrie", "Mexique"], "correct": 1, "time_limit": 15,
         "explanation": "Trois bandes verticales vert, blanc, rouge : c'est le drapeau italien."},
        {"kind": "libre", "text": "Quel est le plus grand océan du monde ?",
         "accepted": ["Pacifique", "Océan Pacifique", "L'océan Pacifique"], "time_limit": 20,
         "explanation": "L'océan Pacifique couvre environ un tiers de la surface du globe."},
        {"kind": "qcm", "text": "Combien de joueurs une équipe de football aligne-t-elle sur le terrain, gardien compris ?",
         "choices": ["9", "10", "11", "12"], "correct": 2, "time_limit": 10,
         "explanation": "Onze joueurs : dix joueurs de champ et un gardien."},
        {"kind": "qcm", "text": "Qui a peint la Joconde ?",
         "choices": ["Michel-Ange", "Léonard de Vinci", "Raphaël", "Botticelli"], "correct": 1, "time_limit": 15,
         "explanation": "Léonard de Vinci l'a peinte au début du XVIe siècle ; elle est exposée au Louvre."},
        {"kind": "vf", "text": "Un kilo de plumes pèse plus lourd qu'un kilo de plomb.",
         "correct": 1, "time_limit": 10,
         "explanation": "Les deux pèsent exactement un kilo : seul le volume change."},
        {"kind": "qcm", "text": "Quel est le symbole chimique de l'or ?",
         "choices": ["Ag", "Au", "Or", "Fe"], "correct": 1, "time_limit": 15,
         "explanation": "Au vient du latin « aurum »."},
        {"kind": "qcm", "text": "En quelle année le mur de Berlin est-il tombé ?",
         "choices": ["1985", "1989", "1991", "1979"], "correct": 1, "time_limit": 20,
         "explanation": "Le 9 novembre 1989."},
        {"kind": "libre", "text": "Quelle planète est surnommée « la planète rouge » ?",
         "accepted": ["Mars"], "time_limit": 15,
         "explanation": "Sa couleur vient de l'oxyde de fer présent à sa surface."},
        {"kind": "qcm", "text": "Quel est le plus grand mammifère terrestre ?",
         "choices": ["Éléphant d'Afrique", "Girafe", "Rhinocéros blanc", "Hippopotame"], "correct": 0,
         "time_limit": 20, "explanation": "L'éléphant de savane d'Afrique peut dépasser 6 tonnes."},
        {"kind": "vf", "text": "Botaniquement, la tomate est un fruit.", "correct": 0, "time_limit": 10,
         "explanation": "Elle se développe à partir de la fleur et contient les graines : c'est bien un fruit."},
        {"kind": "qcm", "text": "Dans quelle ville se trouve la célèbre tour penchée ?",
         "choices": ["Florence", "Pise", "Venise", "Rome"], "correct": 1, "time_limit": 15,
         "explanation": "La tour de Pise penche depuis la fin de sa construction, à cause d'un sol meuble."},
        {"kind": "qcm", "text": "Combien de côtés a un hexagone ?",
         "choices": ["5", "6", "7", "8"], "correct": 1, "time_limit": 10,
         "explanation": "« Hexa » signifie six en grec."},
        {"kind": "libre", "text": "Quel fleuve traverse Paris ?", "accepted": ["La Seine", "Seine"],
         "time_limit": 15, "explanation": "La Seine, longue de 777 km, se jette dans la Manche."},
    ],
}


def create_quiz(s: Session, data: QuizIn) -> db.Quiz:
    quiz = db.Quiz(title=data.title, description=data.description)
    for i, q in enumerate(data.questions):
        quiz.questions.append(db.Question(
            position=i, kind=q.kind, text=q.text, media_type=q.media_type, media_url=q.media_url,
            choices_json=json.dumps(q.choices, ensure_ascii=False), correct=q.correct,
            accepted_json=json.dumps(q.accepted, ensure_ascii=False),
            time_limit=q.time_limit, explanation=q.explanation))
    s.add(quiz)
    s.commit()
    return quiz


def seed_demo_if_empty(s: Session):
    if s.scalar(select(func.count(db.Quiz.id))) == 0:
        create_quiz(s, QuizIn(**DEMO))
