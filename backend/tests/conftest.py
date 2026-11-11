import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Every test gets its own database and the real demo data unless it overrides it."""
    monkeypatch.setenv("SELLERPULSE_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("SELLERPULSE_DATA", str(ROOT / "data" / "demo_seller.json"))
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    from app import db, llm
    llm._transport = None
    db.init_db()
    yield
    llm._transport = None


@pytest.fixture
def demo_data():
    return json.loads((ROOT / "data" / "demo_seller.json").read_text(encoding="utf-8"))


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app, SESSIONS
    SESSIONS.clear()
    with TestClient(app) as c:
        yield c
