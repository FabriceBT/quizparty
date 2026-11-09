"""Série, joker 50/50, équipes, questions « ordre » et « point », catégories, quiz du jour, sauvegarde."""
import io
import zipfile

from app import openmode
from app.scoring import (clean_value, correct_display_order, is_correct, joker_hidden, order_perm, shown_choices,
                         streak_bonus, streak_before)

ORDRE = {"kind": "ordre", "text": "Du plus petit au plus grand", "choices": ["Souris", "Chat", "Cheval", "Éléphant"],
         "time_limit": 20}
POINT = {"kind": "point", "text": "Où est le chat ?", "media_type": "image", "media_url": "/static/demo/drapeau-italie.svg",
         "accepted": ["50", "50", "10"], "time_limit": 20}
QCM = {"kind": "qcm", "text": "2+2 ?", "choices": ["3", "4", "5", "6"], "correct": 1, "time_limit": 20}
QCM2 = {"kind": "qcm", "text": "3+3 ?", "choices": ["5", "6", "7", "8"], "correct": 1, "time_limit": 20}
QCM3 = {"kind": "qcm", "text": "4+4 ?", "choices": ["7", "8", "9", "10"], "correct": 1, "time_limit": 20}


def quiz(client, questions, **extra):
    r = client.post("/api/quizzes", json={"title": "T", "questions": questions, **extra})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def open_code(client, qid):
    return client.post("/api/sessions", json={"quiz_id": qid, "mode": "open"}).json()["code"]


def join(client, code, name="Lea", team=""):
    return client.post(f"/api/open/{code}/join", json={"name": name, "team": team}).json()["token"]


def question(client, code, tok):
    return client.get(f"/api/open/{code}/question", params={"token": tok}).json()


def answer(client, code, tok, idx, value):
    return client.post(f"/api/open/{code}/answer", json={"token": tok, "question_index": idx, "value": value}).json()


# ---------------------------------------------------------------- règles pures
def test_bonus_de_serie():
    assert [streak_bonus(n) for n in range(0, 9)] == [0, 0, 50, 100, 150, 200, 250, 250, 250]
    assert streak_before([True, False, True, True]) == 2 and streak_before([]) == 0 and streak_before([True, False]) == 0


def test_ordre_melange_et_correction():
    q = {"id": 5, **ORDRE}
    perm = order_perm(5, 4)
    assert perm != [0, 1, 2, 3] and sorted(perm) == [0, 1, 2, 3]
    assert order_perm(5, 4) == perm                                    # stable : même ordre pour tous et après rechargement
    shown = shown_choices(q)
    assert sorted(shown) == sorted(q["choices"]) and shown != q["choices"]
    good = correct_display_order(q)                                    # indices à toucher dans l'ordre
    assert [shown[i] for i in good] == q["choices"] and is_correct(q, good)
    assert not is_correct(q, list(reversed(good)))
    assert clean_value(q, good) == good and clean_value(q, [0, 0, 1, 2]) is None and clean_value(q, "x") is None


def test_point_correction():
    q = {"id": 1, **POINT}
    assert is_correct(q, [52, 49]) and not is_correct(q, [80, 50])
    assert clean_value(q, [50, 50.04]) == [50.0, 50.0] and clean_value(q, [120, 5]) is None and clean_value(q, [1]) is None


def test_joker_cache_la_moitie_des_mauvaises():
    q = {"id": 1, "kind": "qcm", "choices": list("abcd"), "correct": 2}
    h = joker_hidden(q, 7)
    assert len(h) == 2 and 2 not in h and h == joker_hidden(q, 7)
    assert len(joker_hidden({**q, "choices": list("abc")}, 7)) == 1
    assert joker_hidden({**q, "choices": list("ab")}, 7) == [] and joker_hidden({**q, "kind": "vf"}, 7) == []


# ---------------------------------------------------------------- validation des questions
def test_validation_ordre_et_point(client):
    bad = lambda q: client.post("/api/quizzes", json={"title": "x", "questions": [q]}).status_code == 422
    assert bad({**ORDRE, "choices": ["a"]}) and bad({**ORDRE, "choices": ["a", ""]})
    assert bad({**POINT, "accepted": []}) and bad({**POINT, "media_type": "none", "media_url": ""})
    assert bad({**POINT, "accepted": ["150", "50", "10"]}) and bad({**POINT, "accepted": ["50", "50", "1"]})
    qid = quiz(client, [ORDRE, POINT], category="Animaux")
    got = client.get(f"/api/quizzes/{qid}").json()
    assert got["category"] == "Animaux" and got["questions"][0]["choices"] == ORDRE["choices"]   # l'éditeur voit le bon ordre
    assert got["questions"][1]["accepted"] == ["50", "50", "10"]


# ---------------------------------------------------------------- mode « quand on veut »
def test_open_ordre_point_serie_et_joker(client):
    openmode._started.clear(); openmode._joker.clear()
    code = open_code(client, quiz(client, [QCM, ORDRE, POINT, QCM2]))
    tok = join(client, code)

    q = question(client, code, tok)
    assert q["joker_available"] and q["hidden"] == [] and q["streak"] == 0
    j = client.post(f"/api/open/{code}/joker", json={"token": tok, "question_index": 0}).json()
    assert len(j["hidden"]) == 2 and 1 not in j["hidden"]
    assert question(client, code, tok)["hidden"] == j["hidden"] and not question(client, code, tok)["joker_available"]
    hidden_try = answer(client, code, tok, 0, j["hidden"][0])           # réponse masquée : refusée (compte comme faux)
    assert not hidden_try["correct"]

    q = question(client, code, tok)                                     # ordre : choix mélangés, jamais le bon ordre
    assert q["question"]["kind"] == "ordre" and q["question"]["choices"] != ORDRE["choices"]
    assert q["streak"] == 0 and not q["joker_available"]               # joker déjà consommé
    shown = q["question"]["choices"]
    order = [shown.index(c) for c in ORDRE["choices"]]
    r = answer(client, code, tok, 1, order)
    assert r["correct"] and r["bonus"] == 0 and r["streak"] == 1 and r["correct_order"] == order    # la série repart après l'erreur

    question(client, code, tok)
    r = answer(client, code, tok, 2, [51, 48])                          # point : dans la zone, 2e bonne d'affilée -> +50
    assert r["correct"] and r["bonus"] == 50 and r["streak"] == 2 and r["target"] == {"x": 50.0, "y": 50.0, "r": 10.0}
    assert question(client, code, tok)["streak"] == 2

    question(client, code, tok)
    r = answer(client, code, tok, 3, 1)                                 # 3e d'affilée -> +100
    assert r["correct"] and r["bonus"] == 100 and r["finished"] and r["points"] >= 1000
    tok2 = join(client, code, "Tom")
    question(client, code, tok2)
    assert not answer(client, code, tok2, 0, 99)["correct"]


def test_open_joker_divise_les_points(client):
    openmode._started.clear(); openmode._joker.clear()
    code = open_code(client, quiz(client, [QCM, QCM2]))
    a, b = join(client, code, "A"), join(client, code, "B")
    question(client, code, a); question(client, code, b)
    client.post(f"/api/open/{code}/joker", json={"token": a, "question_index": 0})
    with_joker, without = answer(client, code, a, 0, 1), answer(client, code, b, 0, 1)
    assert with_joker["correct"] and without["correct"] and with_joker["points"] < without["points"] * 0.6


def test_joker_une_seule_fois(client):
    openmode._started.clear(); openmode._joker.clear()
    code = open_code(client, quiz(client, [QCM, QCM2]))
    tok = join(client, code)
    question(client, code, tok)
    assert client.post(f"/api/open/{code}/joker", json={"token": tok, "question_index": 0}).status_code == 200
    answer(client, code, tok, 0, 1)
    question(client, code, tok)
    assert client.post(f"/api/open/{code}/joker", json={"token": tok, "question_index": 1}).status_code == 409


def test_equipes_open_et_resultats(client):
    openmode._started.clear()
    code = open_code(client, quiz(client, [QCM]))
    for name, team, val in [("A", "rouge", 1), ("B", "rouge", 0), ("C", "bleu", 1), ("D", "n'importe", 1)]:
        tok = join(client, code, name, team)
        question(client, code, tok); answer(client, code, tok, 0, val)
    res = client.get(f"/api/sessions/{code}/results").json()
    assert {p["name"]: p["team"] for p in res["players"]} == {"A": "rouge", "B": "rouge", "C": "bleu", "D": ""}
    teams = {t["team"]: t for t in res["teams"]}
    assert teams["rouge"]["players"] == 2 and teams["bleu"]["players"] == 1 and teams["bleu"]["avg"] > teams["rouge"]["avg"]


# ---------------------------------------------------------------- multi (WebSocket)
def recv_until(ws, phase, tries=30):
    for _ in range(tries):
        msg = ws.receive_json()
        if msg.get("type") == "state" and msg["phase"] == phase:
            return msg
    raise AssertionError(phase)


def test_multi_serie_joker_equipes_ordre(client):
    qid = quiz(client, [QCM, ORDRE, QCM3])
    r = client.post("/api/sessions", json={"quiz_id": qid, "mode": "multi"}).json()
    code, key = r["code"], r["url"].split("k=")[1]
    tok = {n: client.post("/api/join", json={"code": code, "name": n, "team": t}).json()["token"]
           for n, t in (("Lea", "rouge"), ("Tom", "bleu"))}
    with client.websocket_connect(f"/ws/host/{code}?k={key}") as host, \
         client.websocket_connect(f"/ws/play/{code}?token={tok['Lea']}") as lea, \
         client.websocket_connect(f"/ws/play/{code}?token={tok['Tom']}") as tom:
        recv_until(host, "lobby"); recv_until(lea, "lobby"); recv_until(tom, "lobby")
        host.send_json({"type": "start"})
        sl = recv_until(lea, "question"); recv_until(tom, "question")
        assert sl["joker_available"] and sl["streak"] == 0
        lea.send_json({"type": "joker"})
        sl = recv_until(lea, "question")
        assert len(sl["hidden"]) == 2 and not sl["joker_available"]
        lea.send_json({"type": "answer", "value": 1}); tom.send_json({"type": "answer", "value": 1})
        rl, rt = recv_until(lea, "reveal"), recv_until(tom, "reveal")
        assert rl["me"]["points"] < rt["me"]["points"] * 0.6              # joker : points ÷ 2
        assert {t["team"] for t in rl["teams"]} == {"rouge", "bleu"}
        assert rl["leaderboard"][0]["team"] in ("rouge", "bleu")

        host.send_json({"type": "next"})
        sl = recv_until(lea, "question"); recv_until(tom, "question")
        assert sl["streak"] == 1 and not sl["joker_available"] and sl["question"]["choices"] != ORDRE["choices"]
        shown = sl["question"]["choices"]
        order = [shown.index(c) for c in ORDRE["choices"]]
        lea.send_json({"type": "answer", "value": order}); tom.send_json({"type": "answer", "value": [0, 1, 2, 3]})
        rl, rt = recv_until(lea, "reveal"), recv_until(tom, "reveal")
        assert rl["me"]["correct"] and rl["me"]["bonus"] == 50 and rl["me"]["streak"] == 2
        assert rl["reveal"]["correct_order"] == order and rl["reveal"]["distribution"] is None
        assert not rt["me"]["correct"] and rt["me"]["streak"] == 0

        host.send_json({"type": "next"})
        recv_until(lea, "question"); recv_until(tom, "question")
        lea.send_json({"type": "answer", "value": [1, 2]})                 # valeur invalide : ignorée
        host.send_json({"type": "skip"})
        assert recv_until(lea, "reveal")["me"]["points"] == 0


# ---------------------------------------------------------------- solo (un seul téléphone)
def test_solo_serie_joker_et_nouveaux_types(client):
    from app import main
    main._solo_joker.clear()
    qid = quiz(client, [QCM, ORDRE, POINT])
    code = client.post("/api/sessions", json={"quiz_id": qid, "mode": "solo", "names": ["Ana"]}).json()["code"]
    info = client.get(f"/api/solo/{code}").json()
    pid = info["players"][0]["id"]
    assert info["players"][0]["joker"] and info["players"][0]["streak"] == 0
    assert info["questions"][1]["choices"] != ORDRE["choices"] and "accepted" not in info["questions"][2]
    h = client.post(f"/api/solo/{code}/joker", json={"player_id": pid, "question_index": 0}).json()["hidden"]
    assert len(h) == 2
    post = lambda i, v: client.post(f"/api/solo/{code}/answer", json={"player_id": pid, "question_index": i, "value": v, "elapsed_ms": 1000}).json()
    assert post(0, 1)["correct"]
    shown = info["questions"][1]["choices"]
    r = post(1, [shown.index(c) for c in ORDRE["choices"]])
    assert r["correct"] and r["bonus"] == 50 and r["streak"] == 2
    r = post(2, [50, 50])
    assert r["correct"] and r["bonus"] == 100 and r["target"]["r"] == 10.0


# ---------------------------------------------------------------- bibliothèque
def test_bibliotheque_categories_quiz_du_jour(client):
    qid = quiz(client, [QCM], category="Maths")
    lst = client.get("/api/library").json()
    mine = next(q for q in lst if q["id"] == qid)
    assert mine["category"] == "Maths" and sum(1 for q in lst if q["daily"]) == 1
    assert client.get("/api/quizzes").json()[0]["category"] in ("Maths", "")


def test_bibliotheque_remise_a_zero_hebdomadaire(client):
    from datetime import timedelta
    from app import db, library
    qid = quiz(client, [QCM])
    code = client.get(f"/q/{qid}", follow_redirects=False).headers["location"].split("/j/")[1]
    with db.SessionLocal() as s:                                       # on vieillit la partie : elle date de la semaine dernière
        gs = library.running_session(s, qid)
        gs.created_at = db.now() - timedelta(days=8)
        s.commit()
        assert library.running_session(s, qid) is None
    assert next(q for q in client.get("/api/library").json() if q["id"] == qid)["players"] == 0
    new = client.get(f"/q/{qid}", follow_redirects=False).headers["location"].split("/j/")[1]
    assert new != code
    assert client.get(f"/api/sessions/{code}/results").json()["status"] == "finished"      # archivée dans l'historique
    assert client.get(f"/api/sessions/{new}/results").json()["weekly"] is True


# ---------------------------------------------------------------- sauvegarde / PWA
def test_sauvegarde_et_restauration(client):
    qid = quiz(client, [QCM, ORDRE, POINT], category="Sauv", title="Quiz à sauvegarder")
    client.post(f"/api/library/{qid}/publish", json={"published": False})
    r = client.get("/api/backup")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert "quizzes.json" in z.namelist()
    # déjà présent -> ignoré
    up = client.post("/api/restore", files={"file": ("s.zip", r.content, "application/zip")}).json()
    assert up["added"] == 0 and up["skipped"] >= 1
    # après suppression -> recréé, avec sa rubrique, ses questions et sa visibilité
    client.delete(f"/api/quizzes/{qid}")
    up = client.post("/api/restore", files={"file": ("s.zip", r.content, "application/zip")}).json()
    assert up["added"] >= 1
    back = next(q for q in client.get("/api/quizzes").json() if q["category"] == "Sauv")
    assert back["questions"] == 3 and all(q["id"] != back["id"] for q in client.get("/api/library").json())
    # fichier invalide et chemin piégé
    assert client.post("/api/restore", files={"file": ("x.zip", b"pas un zip", "application/zip")}).status_code == 400
    evil = io.BytesIO()
    with zipfile.ZipFile(evil, "w") as zz:
        zz.writestr("quizzes.json", '{"quizzes": []}')
        zz.writestr("media/../../evil.txt", "x")
    assert client.post("/api/restore", files={"file": ("e.zip", evil.getvalue(), "application/zip")}).json() == {"added": 0, "skipped": 0}


def test_service_worker(client):
    r = client.get("/sw.js")
    assert r.status_code == 200 and "javascript" in r.headers["content-type"] and r.headers["service-worker-allowed"] == "/"


def test_fichiers_statiques_versionnes(client):
    """Les pages référencent les JS/CSS avec ?v=… pour qu'un téléphone n'utilise jamais un ancien fichier en cache."""
    for url in ("/play", "/j/123456", "/results/x", "/library"):
        html = client.get(url).text
        assert "/static/css/app.css?v=" in html and "/static/js/common.js?v=" in html, url
