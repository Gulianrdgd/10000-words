"""Test setup.

DATA_DIR is redirected before app.database is imported, so tests never touch
the real app.db — importing app.database creates the SQLite file at import
time, which makes the ordering here load-bearing.
"""
import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="1000mots-tests-")
os.environ.pop("AZURE_SPEECH_KEY", None)
os.environ.pop("AZURE_SPEECH_REGION", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
def client():
    """A started app (lifespan runs the seed), with its own empty account."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth(client):
    """Registers a throwaway account and returns an auth header for it."""
    import uuid

    body = {"username": f"t{uuid.uuid4().hex[:10]}", "password": "test12345"}
    res = client.post("/auth/register", json=body)
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}
