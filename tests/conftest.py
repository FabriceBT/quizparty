import os
import tempfile

# Base et médias isolés : doit être défini AVANT l'import de l'application.
os.environ["QUIZ_DATA"] = tempfile.mkdtemp(prefix="quizparty-test-")
os.environ.pop("QUIZ_ADMIN_PASSWORD", None)

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
