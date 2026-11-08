"""Configuration centrale (lue une seule fois à l'import)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Dossier de données : base SQLite + médias importés.
DATA_DIR = Path(os.environ.get("QUIZ_DATA", BASE_DIR / "data"))
MEDIA_DIR = DATA_DIR / "media"
DATA_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# Base de données : SQLite par défaut, PostgreSQL possible via QUIZ_DB_URL.
DB_URL = os.environ.get("QUIZ_DB_URL", f"sqlite:///{(DATA_DIR / 'quizparty.db').as_posix()}")

# Taille maximale d'un fichier importé (Mo).
MAX_UPLOAD_MB = int(os.environ.get("QUIZ_MAX_UPLOAD_MB", "50"))

MAX_PLAYERS = 200
