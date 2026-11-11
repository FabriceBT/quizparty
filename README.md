# 🎉 Fouquiz

Application de quiz en direct, simple et moderne. Les participants **scannent un QR code** avec leur téléphone (aucune installation, aucun compte) et jouent ensemble : questions synchronisées, chrono, classement en direct, podium animé, revue des réponses.

> Version 1 : une **application web mobile** (s'ouvre dans le navigateur du téléphone, installable sur l'écran d'accueil). C'est le choix le plus simple et le plus économique : un seul code pour Android *et* iPhone, rien à publier dans les boutiques pour commencer.

## Fonctionnalités

| | |
|---|---|
| **Créer un quiz** | titre, description, questions illimitées, QCM (2 à 4 réponses), vrai/faux, réponse libre, image / vidéo / son, temps (10, 15, 20, 30 s), explication, réorganisation ↑↓ |
| **Mode multi-téléphones** | code à 6 chiffres + QR code, prénom, questions et chrono synchronisés par WebSocket, classement en direct, reconnexion automatique |
| **Mode automatique** | case à cocher à la création de la partie (ou sur l'écran organisateur, à tout moment) : le quiz **démarre seul** (par défaut 30 s après l'arrivée du 1er joueur, réglable ou désactivable), puis après chaque question la bonne réponse s'affiche et la suivante arrive toute seule après une pause réglable (5 à 30 s), jusqu'au podium. Fonctionne même si l'organisateur ferme son écran |
| **Mode « quand on veut »** | un QR code à partager (affiche, écran, message) : chacun scanne et fait le quiz **seul, quand il veut**, à son rythme. Aucun organisateur : les questions s'enchaînent toutes seules, chaque question est chronométrée par le serveur, classement provisoire en direct, clôture par l'organisateur |
| **Bibliothèque en libre-service** | un seul QR code (`/library` côté organisateur) qui ouvre le catalogue `/play` : les joueurs choisissent **n'importe quel quiz, à tout moment**, sans aucun lancement par l'organisateur. Chaque quiz a un classement permanent ; on peut masquer un quiz ou remettre son classement à zéro |
| **Types de questions** | QCM, vrai/faux, réponse libre, **remettre dans l'ordre** (2 à 5 éléments, mélangés pour les joueurs) et **point sur une image** (on touche l'image, l'organisateur place la bonne zone) |
| **Bonus de série** | +50 points par bonne réponse d'affilée à partir de la 2e, plafonné à +250 🔥 |
| **Joker 50/50** | un par joueur et par partie : masque la moitié des mauvaises réponses d'un QCM de 3-4 réponses, la bonne réponse vaut alors moitié moins de points |
| **Équipes** | 🔴 🔵 🟢 🟡 au choix (facultatif) à l'arrivée ; classement des équipes à la moyenne de points par joueur |
| **Bibliothèque enrichie** | rubriques et recherche, **quiz du jour**, record personnel sur le téléphone, classement qui repart de zéro **chaque lundi** (`QUIZ_LIBRARY_WEEKLY=0` pour le garder en permanence) |
| **Application installable** | bouton « Installer » sur Android, explication sur iPhone ; fonctionne en HTTPS (Codespaces, hébergement) |
| **Sauvegarde / restauration** | page « Mes quiz » : un ZIP avec tous les quiz et leurs médias, à remettre en un clic après un redéploiement |
| **Mode un seul téléphone** | l'organisateur saisit les prénoms, chacun répond à son tour, le téléphone se passe de main en main |
| **Jeu** | gros boutons, chrono animé, compte à rebours sonore, flash vert / rouge, bonne réponse + explication après chaque question |
| **Points** | 0 si faux ; de **500 à 1000** pour une bonne réponse selon la rapidité |
| **Podium** | médailles 🥇🥈🥉, marches animées, confettis, fanfare, % de réussite |
| **Revue des réponses** | question par question : réponse de chaque joueur, ✅/❌, bonne réponse, explication, classement de la question |
| **Administration** | Mes quiz (modifier, dupliquer, supprimer), historique des parties, export **Excel**, impression / PDF |
| **Confort** | mode clair / sombre, sons activables, interface en français, mot de passe organisateur optionnel |

Un quiz de démonstration de **15 questions** est créé automatiquement au premier lancement.

## Installation sous Windows

### 1. Installer Python (une seule fois)

1. Allez sur <https://www.python.org/downloads/> et téléchargez Python **3.12 ou plus récent**.
2. Lancez l'installateur et **cochez « Add python.exe to PATH »** (case en bas de la première fenêtre), puis *Install Now*.

### 2. Lancer l'application

1. Décompressez le dossier `quizparty` où vous voulez (ex. `C:\quizparty`).
2. Double-cliquez sur **`run.bat`**.
   - Au premier lancement, les composants s'installent automatiquement (1 à 2 minutes).
   - Au pare-feu Windows, cliquez sur **« Autoriser l'accès »** (réseau privé) : c'est ce qui permet aux téléphones de se connecter.
3. Le navigateur s'ouvre sur `http://localhost:8000`. Pour arrêter : fermez la fenêtre noire.

### 3. Jouer avec des téléphones

1. L'ordinateur et les téléphones doivent être sur le **même Wi-Fi**.
2. Sur l'ordinateur : **Mes quiz → 📱 Partie multi-téléphones**.
3. L'écran affiche un **QR code** et un code à 6 chiffres. Projetez-le sur un écran ou une TV.
4. Les participants scannent le QR code (appareil photo du téléphone), saisissent leur prénom, et attendent.
5. Cliquez sur **Lancer le quiz**. À la fin de chaque question, vous voyez la bonne réponse et le classement, puis **Question suivante**.
6. *Mode automatique (facultatif)* : cochez **⏩ Mode automatique** en créant la partie (ou sur l'écran organisateur). Le quiz démarre tout seul quelques secondes après l'arrivée du premier joueur (compte à rebours affiché ; réglable sur l'écran organisateur, ou « Je lance moi-même » pour garder la main). Ensuite tout s'enchaîne sans intervention : question, révélation, pause, question suivante, podium. Le bouton **Question suivante** reste disponible pour accélérer, et la case peut être décochée en cours de partie pour reprendre la main.

> Si le QR code ne fonctionne pas : vérifiez le Wi-Fi (le Wi-Fi « invité » isole souvent les appareils entre eux) et le pare-feu. Vous pouvez aussi saisir à la main l'adresse affichée sous le QR code.

### Mode « quand on veut » (chacun joue à son rythme)

1. **Mes quiz → 🕒 Quand on veut**. L'écran affiche le QR code, le code à 6 chiffres et le classement en direct.
2. Partagez le QR code ou le lien : chacun joue quand il le souhaite, depuis son téléphone. Rien ne dépend de vous : après chaque question, la correction s'affiche 5 secondes puis la suivante arrive toute seule (bouton **Continuer** pour accélérer).
3. Le temps de chaque question est compté par le serveur : fermer ou recharger la page ne donne pas de temps en plus. Une question restée sans réponse après son délai vaut 0 point.
4. Le classement est **provisoire** tant que le quiz est ouvert. Quand vous voulez, **Clôturer le quiz** (écran `Historique → 🕒 Gérer`) : plus personne ne peut jouer, le podium est définitif et chacun peut revoir les bonnes réponses (cachées jusque-là pour que les premiers ne soufflent pas les réponses aux suivants).
5. Les données sont enregistrées : le quiz reste ouvert même si vous arrêtez puis relancez le serveur. Pour que les participants puissent jouer, l'ordinateur doit rester allumé avec l'application lancée.

### Mode un seul téléphone

**Mes quiz → 👥 Un seul téléphone**, saisissez les prénoms (un par ligne) et passez le téléphone à chaque question.

## Où sont mes données ?

Dans le dossier `data/` : la base `quizparty.db` (SQLite) et les médias importés (`data/media/`). **Sauvegarder = copier ce dossier.**

## Réglages (variables d'environnement, facultatives)

| Variable | Rôle |
|---|---|
| `QUIZ_ADMIN_PASSWORD` | protège la création de quiz, l'historique et le lancement des parties. Les joueurs n'ont jamais besoin de mot de passe. **À définir dès que l'application est accessible depuis Internet.** |
| `QUIZ_PUBLIC_URL` | adresse publique à mettre dans le QR code (ex. `https://quiz.mondomaine.fr`) |
| `QUIZ_DATA` | dossier des données (défaut : `data/`) |
| `QUIZ_DB_URL` | base de données (défaut : SQLite ; PostgreSQL possible, voir plus bas) |
| `QUIZ_MAX_UPLOAD_MB` | taille maximale d'un fichier importé (défaut : 50) |
| `QUIZ_LIBRARY_WEEKLY` | `0` pour ne pas remettre à zéro chaque lundi le classement de la bibliothèque (défaut : remise à zéro) |

Sous Windows, pour définir un mot de passe : ouvrez `run.bat` avec le Bloc-notes et ajoutez avant la ligne `python -m uvicorn` : `set QUIZ_ADMIN_PASSWORD=monmotdepasse`.

## Protection des données personnelles

- Aucun compte joueur, aucun e-mail : seul un **prénom** est demandé, uniquement pour la durée de la partie et l'historique.
- Aucun service tiers, aucun traceur, aucune police externe : tout est hébergé par vous. (Seules les vidéos YouTube, si vous en intégrez, chargent YouTube.)
- Pour supprimer des données : *Historique → 🗑* (partie) ou *Mes quiz → Supprimer* (quiz et parties associées).
- Les médias importés sont limités aux images, vidéos et sons courants. Les SVG sont refusés à l'import (risque de scripts).

## Architecture (pour faire évoluer le projet)

```
app/
  main.py      routes : pages, API REST, WebSockets, mot de passe organisateur
  game.py      moteur de partie en direct (phases lobby → question → reveal → finished)
  scoring.py   correction + calcul des points (fonctions pures, testées)
  db.py        modèles SQLAlchemy : Quiz, Question, GameSession, Player, Answer
  schemas.py   validation des quiz (Pydantic)
  services.py  classement, revue des réponses, export Excel
  seed.py      quiz de démonstration (15 questions)
templates/     pages Jinja2 (une par écran)
static/js/     interface en JavaScript pur, sans outil de build
tests/         14 tests (scoring, API, partie complète par WebSocket)
```

Principes : le **serveur fait autorité** (chrono, correction, points) ; chaque changement d'état est envoyé en bloc aux clients, donc une reconnexion réaffiche l'écran exact ; la bonne réponse n'est **jamais** envoyée aux joueurs avant la fin de la question.

Lancer les tests : `.venv\Scripts\activate` puis `python -m pytest`.

Idées d'évolutions faciles : musique d'ambiance, sons personnalisés par bonne/mauvaise réponse, glisser-déposer des questions, thèmes graphiques, import de quiz depuis un fichier Excel.

## Mettre en ligne (pour jouer à distance)

**Le plus simple et gratuit : GitHub Codespaces** (port 8000 en *Public*, puis lancer le serveur comme indiqué plus haut). L'adresse change à chaque nouveau Codespace et le serveur s'arrête quand il s'endort : c'est adapté à une soirée, pas à un QR code imprimé. Un `Dockerfile` est aussi fourni pour un hébergement de votre choix. Le dossier `seed/` accepte des sauvegardes `.zip` rechargées à chaque démarrage.

Il faut un hébergement qui accepte les **WebSockets**, un disque persistant (ou PostgreSQL) et le **HTTPS** (indispensable pour installer l'application sur un téléphone). Un petit serveur privé virtuel (VPS) à quelques euros par mois suffit pour plusieurs centaines de joueurs.

Commande de démarrage : `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` derrière un reverse proxy HTTPS (Caddy ou Nginx, avec la prise en charge des WebSockets). Définissez `QUIZ_ADMIN_PASSWORD` et `QUIZ_PUBLIC_URL`.

**PostgreSQL** (facultatif) : `pip install "psycopg[binary]"` puis `QUIZ_DB_URL=postgresql+psycopg://utilisateur:motdepasse@serveur/quizparty`. *(Prévu par l'architecture mais non testé dans cette version.)*

Limite actuelle : l'état d'une partie *en cours* est gardé en mémoire ; un redémarrage du serveur en pleine partie l'interrompt (les parties terminées et les quiz sont, eux, conservés). Elle fonctionne avec **un seul processus** serveur.

## Publier sur Android et iOS

### Étape 1 — Sans boutique (recommandé pour commencer, gratuit)

Une fois l'application en ligne en HTTPS, chaque participant peut l'installer comme une application :

- **Android (Chrome)** : menu ⋮ → **Installer l'application** (ou *Ajouter à l'écran d'accueil*).
- **iPhone (Safari)** : bouton Partager → **Sur l'écran d'accueil**.

L'icône « Fouquiz » apparaît alors comme n'importe quelle application, en plein écran. Le plus simple pour un événement : afficher le QR code, les joueurs n'ont rien à installer.

### Étape 2 — Google Play (Android)

1. Créez un compte développeur Google Play (frais d'inscription uniques, environ 25 $ — à vérifier).
2. Générez un paquet Android qui encapsule votre site avec **Bubblewrap** (outil officiel Google pour les « Trusted Web Activity ») : `npm i -g @bubblewrap/cli` puis `bubblewrap init --manifest https://VOTRE-SITE/static/manifest.webmanifest` et `bubblewrap build`.
3. Ajoutez le fichier `assetlinks.json` demandé sur votre site (il prouve que vous possédez le site), puis déposez le fichier `.aab` dans la Play Console.

### Étape 3 — App Store (iPhone)

1. Compte Apple Developer (abonnement annuel, environ 99 $ — à vérifier) et **un Mac avec Xcode**.
2. Encapsulez le site avec **Capacitor** (`npm i @capacitor/core @capacitor/cli`, `npx cap add ios`, en pointant `server.url` vers votre site), ouvrez le projet dans Xcode, puis *Product → Archive* et envoi vers App Store Connect.
3. Attention : Apple refuse parfois les simples « sites emballés ». Ajoutez des éléments natifs (par exemple le scan de QR code via l'appareil photo, ou les notifications) pour augmenter vos chances.

Pour de la diffusion privée (entreprise, association), l'installation depuis l'écran d'accueil (étape 1) évite tous ces frais et délais de validation.

## Ce qui n'est pas dans cette première version

Musique d'ambiance et sons importés par l'organisateur (les effets sonores sont générés par l'application et coupables d'un clic) ; export PDF direct (utilisez *Imprimer / enregistrer en PDF* sur la page des résultats) ; glisser-déposer des questions (boutons ↑↓ à la place) ; applications natives dans les boutiques (voir ci-dessus).
