import time

QUIZ = {
    "title": "Mini quiz", "description": "test",
    "questions": [
        {"kind": "qcm", "text": "2+2 ?", "choices": ["3", "4", "5"], "correct": 1, "time_limit": 10, "explanation": "quatre"},
        {"kind": "libre", "text": "Capitale de la France ?", "accepted": ["Paris"], "time_limit": 10},
    ],
}


def make_quiz(client, data=QUIZ):
    r = client.post("/api/quizzes", json=data)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_demo_seed_15_questions(client):
    quizzes = client.get("/api/quizzes").json()
    demo = next(q for q in quizzes if q["title"].startswith("Culture générale"))
    assert demo["questions"] == 15


def test_pages_ok(client):
    for url in ["/", "/play", "/quizzes", "/quizzes/new", "/history", "/j/123456", "/results/x", "/review/x"]:
        assert client.get(url).status_code == 200, url
    assert client.get("/static/demo/drapeau-italie.svg").status_code == 200


def test_validation(client):
    bad = {"title": "x", "questions": [{"kind": "qcm", "text": "?", "choices": ["a"], "correct": 0}]}
    assert client.post("/api/quizzes", json=bad).status_code == 422
    bad = {"title": "x", "questions": [{"kind": "qcm", "text": "?", "choices": ["a", "b"], "correct": 0,
                                         "media_type": "image", "media_url": "javascript:alert(1)"}]}
    assert client.post("/api/quizzes", json=bad).status_code == 422


def test_crud_dupliquer_supprimer(client):
    qid = make_quiz(client)
    got = client.get(f"/api/quizzes/{qid}").json()
    got["title"] = "Renommé"
    got["questions"] = got["questions"][:1]
    assert client.put(f"/api/quizzes/{qid}", json=got).status_code == 200
    assert len(client.get(f"/api/quizzes/{qid}").json()["questions"]) == 1
    copy = client.post(f"/api/quizzes/{qid}/duplicate").json()["id"]
    assert client.get(f"/api/quizzes/{copy}").json()["title"] == "Renommé (copie)"
    assert client.delete(f"/api/quizzes/{copy}").status_code == 200
    assert client.get(f"/api/quizzes/{copy}").status_code == 404


def test_upload(client):
    ok = client.post("/api/upload", files={"file": ("a.png", b"\x89PNG....", "image/png")})
    assert ok.status_code == 200 and ok.json()["url"].startswith("/media/")
    assert client.get(ok.json()["url"]).status_code == 200
    assert client.post("/api/upload", files={"file": ("evil.svg", b"<svg/>", "image/svg+xml")}).status_code == 400
    assert client.post("/api/upload", files={"file": ("x.exe", b"MZ", "application/octet-stream")}).status_code == 400


def test_mode_un_telephone(client):
    qid = make_quiz(client)
    r = client.post("/api/sessions", json={"quiz_id": qid, "mode": "solo", "names": ["Ana", "Ben"]}).json()
    code = r["code"]
    info = client.get(f"/api/solo/{code}").json()
    assert "correct" not in info["questions"][0]          # la bonne réponse n'est jamais envoyée avant de répondre
    ana, ben = info["players"]

    def answer(p, qi, value, ms=2000):
        return client.post(f"/api/solo/{code}/answer", json={"player_id": p["id"], "question_index": qi, "value": value, "elapsed_ms": ms})

    a = answer(ana, 0, 1, 0).json()
    assert a["correct"] and a["points"] == 1000
    assert answer(ana, 0, 1).status_code == 409           # une seule réponse par question
    assert not answer(ben, 0, 0).json()["correct"]
    assert answer(ana, 1, "paris").json()["correct"]
    assert answer(ben, 1, None).json()["points"] == 0     # temps écoulé
    client.post(f"/api/solo/{code}/finish")

    res = client.get(f"/api/sessions/{code}/results").json()
    assert [p["name"] for p in res["players"]] == ["Ana", "Ben"]
    assert res["players"][0]["pct"] == 100 and res["players"][1]["pct"] == 0
    rev = client.get(f"/api/sessions/{code}/review").json()
    assert rev["questions"][0]["answers"][0]["name"] == "Ana" and rev["questions"][0]["correct_text"] == "4"
    xlsx = client.get(f"/api/sessions/{code}/export.xlsx")
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    assert any(h["code"] == code for h in client.get("/api/history").json())


def recv_until(ws, phase, tries=20):
    for _ in range(tries):
        msg = ws.receive_json()
        if msg.get("type") == "state" and msg["phase"] == phase:
            return msg
    raise AssertionError(f"phase {phase} jamais reçue")


def test_partie_multi_complete(client):
    qid = make_quiz(client)
    r = client.post("/api/sessions", json={"quiz_id": qid, "mode": "multi"}).json()
    code, key = r["code"], r["url"].split("k=")[1]
    assert client.get(f"/api/sessions/{code}/exists").status_code == 200
    assert client.get(f"/qr/{code}.svg").headers["content-type"] == "image/svg+xml"

    tok = {n: client.post("/api/join", json={"code": code, "name": n}).json()["token"] for n in ("Lea", "Tom")}
    assert client.post("/api/join", json={"code": code, "name": "lea"}).status_code == 400   # prénom déjà pris
    assert client.post("/api/join", json={"code": "000000", "name": "X"}).status_code == 404

    with client.websocket_connect(f"/ws/host/{code}?k={key}") as host, \
         client.websocket_connect(f"/ws/play/{code}?token={tok['Lea']}") as lea, \
         client.websocket_connect(f"/ws/play/{code}?token={tok['Tom']}") as tom:
        assert recv_until(host, "lobby")["player_count"] == 2
        recv_until(lea, "lobby"); recv_until(tom, "lobby")

        host.send_json({"type": "start"})
        s = recv_until(lea, "question")
        assert s["question"]["text"] == "2+2 ?" and "correct" not in s["question"]
        recv_until(tom, "question")

        lea.send_json({"type": "answer", "value": 1})      # juste
        tom.send_json({"type": "answer", "value": 0})      # faux -> tout le monde a répondu : révélation immédiate
        rl = recv_until(lea, "reveal")
        assert rl["me"]["correct"] and rl["me"]["points"] > 500 and rl["me"]["rank"] == 1
        rt = recv_until(tom, "reveal")
        assert not rt["me"]["correct"] and rt["me"]["points"] == 0 and rt["me"]["rank"] == 2
        assert rl["reveal"]["distribution"] == [1, 1, 0]

        host.send_json({"type": "next"})
        recv_until(lea, "question"); recv_until(tom, "question")
        lea.send_json({"type": "answer", "value": "PARIS"})
        host.send_json({"type": "skip"})                   # l'organisateur n'attend pas Tom
        assert recv_until(tom, "reveal")["me"]["given"] == ""
        host.send_json({"type": "next"})
        assert recv_until(lea, "finished")["results_url"] == f"/results/{code}"

    res = client.get(f"/api/sessions/{code}/results").json()
    assert res["status"] == "finished" and res["players"][0]["name"] == "Lea" and res["players"][0]["correct"] == 2


def test_chrono_serveur(client):
    qid = make_quiz(client, {"title": "t", "questions": [
        {"kind": "vf", "text": "Vrai ?", "correct": 0, "time_limit": 10}]})
    r = client.post("/api/sessions", json={"quiz_id": qid, "mode": "multi"}).json()
    code, key = r["code"], r["url"].split("k=")[1]
    tok = client.post("/api/join", json={"code": code, "name": "Zoe"}).json()["token"]
    with client.websocket_connect(f"/ws/host/{code}?k={key}") as host, \
         client.websocket_connect(f"/ws/play/{code}?token={tok}") as zoe:
        recv_until(zoe, "lobby")
        host.send_json({"type": "start"})
        q = recv_until(zoe, "question")
        assert 0 < q["remaining_ms"] <= 10_000


def test_ws_refuse_mauvais_jeton(client):
    qid = make_quiz(client)
    code = client.post("/api/sessions", json={"quiz_id": qid, "mode": "multi"}).json()["code"]
    import pytest
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/play/{code}?token=nope"):
            pass
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/host/{code}?k=nope"):
            pass


def test_mot_de_passe_organisateur(client, monkeypatch):
    monkeypatch.setenv("QUIZ_ADMIN_PASSWORD", "secret")
    assert client.get("/api/quizzes").status_code == 401
    assert client.get("/quizzes", follow_redirects=False).status_code == 303
    assert client.get("/play").status_code == 200                     # les joueurs n'ont pas besoin de mot de passe
    assert client.post("/login", data={"password": "faux", "next": "/quizzes"}, follow_redirects=False).headers["location"].startswith("/login")
    client.post("/login", data={"password": "secret", "next": "/quizzes"})
    assert client.get("/api/quizzes").status_code == 200


def test_mode_automatique(client):
    """Sans aucun message de l'organisateur après « start » : révélation puis question suivante puis podium, tout seul."""
    qid = make_quiz(client)
    r = client.post("/api/sessions", json={"quiz_id": qid, "mode": "multi", "auto": True, "auto_delay": 1}).json()
    code, key = r["code"], r["url"].split("k=")[1]
    tok = client.post("/api/join", json={"code": code, "name": "Lea"}).json()["token"]
    with client.websocket_connect(f"/ws/host/{code}?k={key}") as host, \
         client.websocket_connect(f"/ws/play/{code}?token={tok}") as lea:
        lobby = recv_until(host, "lobby")
        assert lobby["auto"] is True and lobby["auto_delay"] == 1
        recv_until(lea, "lobby")
        host.send_json({"type": "start"})
        recv_until(lea, "question")
        lea.send_json({"type": "answer", "value": 1})
        rev = recv_until(lea, "reveal")
        assert rev["reveal"]["next_in_ms"] is not None and rev["reveal"]["next_in_ms"] <= 1000
        q2 = recv_until(lea, "question")                    # ... sans « next » de l'organisateur
        assert q2["question"]["index"] == 1
        lea.send_json({"type": "answer", "value": "paris"})
        recv_until(lea, "reveal")
        assert recv_until(lea, "finished")["results_url"] == f"/results/{code}"   # podium automatique
    res = client.get(f"/api/sessions/{code}/results").json()
    assert res["status"] == "finished" and res["players"][0]["correct"] == 2


def test_mode_automatique_reglable_en_cours_de_partie(client):
    """Mode manuel par défaut ; l'organisateur peut l'activer en pleine révélation, puis le couper."""
    qid = make_quiz(client)
    r = client.post("/api/sessions", json={"quiz_id": qid, "mode": "multi"}).json()
    code, key = r["code"], r["url"].split("k=")[1]
    tok = client.post("/api/join", json={"code": code, "name": "Lea"}).json()["token"]
    with client.websocket_connect(f"/ws/host/{code}?k={key}") as host, \
         client.websocket_connect(f"/ws/play/{code}?token={tok}") as lea:
        assert recv_until(host, "lobby")["auto"] is False
        recv_until(lea, "lobby")
        host.send_json({"type": "start"})
        recv_until(lea, "question")
        lea.send_json({"type": "answer", "value": 1})
        assert recv_until(lea, "reveal")["reveal"]["next_in_ms"] is None      # manuel : on attend l'organisateur
        host.send_json({"type": "auto", "value": True, "delay": 1})            # activé pendant la révélation
        assert recv_until(lea, "reveal")["reveal"]["next_in_ms"] is not None
        assert recv_until(lea, "question")["question"]["index"] == 1
        host.send_json({"type": "auto", "value": False, "delay": 1})
        assert recv_until(lea, "question")["auto"] is False


def test_delai_automatique_invalide(client):
    qid = make_quiz(client)
    assert client.post("/api/sessions", json={"quiz_id": qid, "mode": "multi", "auto": True, "auto_delay": 0}).status_code == 422


def open_session(client):
    qid = make_quiz(client)
    r = client.post("/api/sessions", json={"quiz_id": qid, "mode": "open"}).json()
    assert r["url"] == f"/open/{r['code']}"
    return r["code"]


def join_open(client, code, name):
    r = client.post(f"/api/open/{code}/join", json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_mode_quand_on_veut(client):
    code = open_session(client)
    assert client.get(f"/api/sessions/{code}/exists").status_code == 200       # le QR / saisie du code marche
    assert "Quiz Party" in client.get(f"/j/{code}").text and "open.js" in client.get(f"/j/{code}").text
    assert client.get(f"/open/{code}").status_code == 200

    lea, tom = join_open(client, code, "Lea"), join_open(client, code, "Tom")
    assert client.post(f"/api/open/{code}/join", json={"name": "lea"}).status_code == 400   # prénom déjà pris

    # Léa joue seule, tout de suite ; Tom n'a pas encore commencé.
    q = client.get(f"/api/open/{code}/question", params={"token": lea}).json()
    assert q["state"] == "question" and q["question"]["index"] == 0 and "correct" not in q["question"]
    assert 0 < q["remaining_ms"] <= 10_000
    a = client.post(f"/api/open/{code}/answer", json={"token": lea, "question_index": 0, "value": 1}).json()
    assert a["correct"] and a["points"] > 500 and not a["finished"]
    # une question ne se répond pas deux fois, ni dans le désordre
    assert client.post(f"/api/open/{code}/answer", json={"token": lea, "question_index": 0, "value": 1}).status_code == 409
    q2 = client.get(f"/api/open/{code}/question", params={"token": lea}).json()
    assert q2["question"]["index"] == 1
    a2 = client.post(f"/api/open/{code}/answer", json={"token": lea, "question_index": 1, "value": "paris"}).json()
    assert a2["correct"] and a2["finished"]
    assert client.get(f"/api/open/{code}/question", params={"token": lea}).json()["state"] == "done"

    # classement en direct : Léa a fini, Tom n'a rien joué ; la revue des réponses reste fermée
    res = client.get(f"/api/sessions/{code}/results").json()
    assert res["status"] == "running" and res["mode"] == "open"
    assert [(p["name"], p["answered"]) for p in res["players"]] == [("Lea", 2), ("Tom", 0)]
    assert client.get(f"/api/sessions/{code}/review").status_code == 403

    # Tom joue plus tard, rate la 1re question
    client.get(f"/api/open/{code}/question", params={"token": tom})
    bad = client.post(f"/api/open/{code}/answer", json={"token": tom, "question_index": 0, "value": 0}).json()
    assert not bad["correct"] and bad["points"] == 0

    # jeton inconnu / absent
    assert client.get(f"/api/open/{code}/question", params={"token": "nope"}).status_code == 401
    assert client.get(f"/api/open/{code}/question").status_code == 401

    # clôture : plus de nouveaux joueurs, revue des réponses ouverte
    assert client.post(f"/api/open/{code}/close").status_code == 200
    assert client.post(f"/api/open/{code}/join", json={"name": "Zoe"}).status_code == 400
    assert client.get(f"/api/open/{code}/question", params={"token": tom}).json()["state"] == "closed"
    assert client.post(f"/api/open/{code}/answer", json={"token": tom, "question_index": 1, "value": "paris"}).status_code == 400
    assert client.get(f"/api/sessions/{code}/review").status_code == 200
    assert client.get(f"/api/sessions/{code}/exists").status_code == 404
    res = client.get(f"/api/sessions/{code}/results").json()
    assert res["status"] == "finished" and res["players"][0]["name"] == "Lea"


def test_mode_quand_on_veut_chrono_serveur(client):
    """Fermer l'onglet ne gèle pas le chrono : une question expirée est comptée 0 point, la suivante est proposée."""
    from app import openmode
    openmode._started.clear()
    code = open_session(client)
    tok = join_open(client, code, "Max")
    client.get(f"/api/open/{code}/question", params={"token": tok})
    pid = next(iter(openmode._started))
    openmode._started[pid] = (0, time.monotonic() - 3600)         # la question 1 a été affichée il y a une heure
    q = client.get(f"/api/open/{code}/question", params={"token": tok}).json()
    assert q["question"]["index"] == 1                              # la 1re est passée, comptée sans réponse
    late = client.post(f"/api/open/{code}/answer", json={"token": tok, "question_index": 0, "value": 1})
    assert late.status_code == 409                                  # trop tard pour la 1re
    res = client.get(f"/api/sessions/{code}/results").json()
    assert res["players"][0]["answered"] == 1 and res["players"][0]["score"] == 0


def test_mode_quand_on_veut_reponse_hors_delai(client):
    from app import openmode
    openmode._started.clear()
    code = open_session(client)
    tok = join_open(client, code, "Max")
    client.get(f"/api/open/{code}/question", params={"token": tok})
    pid = next(iter(openmode._started))
    openmode._started[pid] = (0, time.monotonic() - 10.2)          # dans la tolérance réseau : limite 10 s + 0,4 s
    a = client.post(f"/api/open/{code}/answer", json={"token": tok, "question_index": 0, "value": 1}).json()
    assert a["correct"] and a["points"] == 500 and not a["timed_out"]   # accepté, mais au minimum de points


def test_adresse_publique_codespace(client, monkeypatch):
    """Dans un Codespace, le serveur voit « localhost » : le QR code doit pointer vers l'adresse publique du port."""
    monkeypatch.setenv("CODESPACE_NAME", "mon-espace-abc")
    monkeypatch.setenv("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
    from app.main import codespace_url, is_local_only, public_base
    from starlette.requests import Request
    req = Request({"type": "http", "method": "GET", "path": "/", "headers": [(b"host", b"localhost:8000")],
                   "server": ("localhost", 8000), "scheme": "http", "query_string": b""})
    assert public_base(req) == "https://mon-espace-abc-8000.app.github.dev"
    assert codespace_url(req) and not is_local_only(req)
    monkeypatch.setenv("QUIZ_PUBLIC_URL", "https://exemple.fr/")
    assert public_base(req) == "https://exemple.fr"            # le réglage explicite reste prioritaire


def test_demarrage_automatique(client):
    """Mode automatique : le quiz démarre seul après l'arrivée du 1er joueur, sans « start » de l'organisateur."""
    qid = make_quiz(client)
    r = client.post("/api/sessions", json={"quiz_id": qid, "mode": "multi", "auto": True, "auto_delay": 1}).json()
    code, key = r["code"], r["url"].split("k=")[1]
    with client.websocket_connect(f"/ws/host/{code}?k={key}") as host:
        lobby = recv_until(host, "lobby")
        assert lobby["auto_start"] == 30 and "start_in_ms" not in lobby          # pas de joueur : pas de compte à rebours
        host.send_json({"type": "auto", "value": True, "delay": 1, "start_delay": 1})   # démarrage dans 1 s
        recv_until(host, "lobby")
        tok = client.post("/api/join", json={"code": code, "name": "Lea"}).json()["token"]
        with client.websocket_connect(f"/ws/play/{code}?token={tok}") as lea:
            s = recv_until(lea, "lobby")
            assert 0 < s["start_in_ms"] <= 1000
            q = recv_until(lea, "question")                                       # démarré sans « start »
            assert q["question"]["index"] == 0


def test_demarrage_automatique_manuel(client):
    """Avec « Je lance moi-même » (0) ou le mode automatique coupé, rien ne démarre tout seul."""
    qid = make_quiz(client)
    r = client.post("/api/sessions", json={"quiz_id": qid, "mode": "multi", "auto": True}).json()
    code, key = r["code"], r["url"].split("k=")[1]
    with client.websocket_connect(f"/ws/host/{code}?k={key}") as host:
        recv_until(host, "lobby")
        host.send_json({"type": "auto", "value": True, "delay": 8, "start_delay": 0})
        recv_until(host, "lobby")
        client.post("/api/join", json={"code": code, "name": "Lea"})
        assert "start_in_ms" not in recv_until(host, "lobby")


def test_library_self_service(client):
    qid = make_quiz(client)
    lst = client.get("/api/library").json()
    assert any(q["id"] == qid for q in lst)                              # publié par défaut
    r = client.get(f"/q/{qid}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/j/")
    code = r.headers["location"].split("/j/")[1]
    assert client.get(f"/q/{qid}", follow_redirects=False).headers["location"] == f"/j/{code}"   # même partie permanente
    join_open(client, code, "Lea")
    assert client.post(f"/api/open/{code}/join", json={"name": "Lea"}).status_code == 200      # doublon autorisé
    assert client.get(f"/api/sessions/{code}/results").json()["library"] is True
    assert next(q for q in client.get("/api/library").json() if q["id"] == qid)["players"] == 2
    # masquer
    assert client.post(f"/api/library/{qid}/publish", json={"published": False}).status_code == 200
    assert all(q["id"] != qid for q in client.get("/api/library").json())
    assert client.get(f"/q/{qid}").status_code == 404
    client.post(f"/api/library/{qid}/publish", json={"published": True})
    # remise à zéro : nouvelle partie à la visite suivante
    client.post(f"/api/library/{qid}/reset")
    new = client.get(f"/q/{qid}", follow_redirects=False).headers["location"].split("/j/")[1]
    assert new != code
    assert client.get("/library").status_code == 200 and client.get("/qr-play.svg").status_code == 200
    assert client.get("/api/library/admin").json()
