import hashlib
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import db as dbmod
from app import models  # noqa: F401
from app.config import Settings, get_settings
from app.db import Base, get_db, make_engine
from app.main import app as fastapi_app
from cryptography.fernet import Fernet

from app.services import catalog, embeddings, limiter, llm, runtime, titles


def fake_embed(base_url, model, texts, timeout=120.0):
    """Deterministic bag-of-words vectors so tests never need a real Ollama."""
    vectors = []
    for text in texts:
        vec = [0.0] * 64
        for token in re.findall(r"\w+", text.lower()):
            vec[int(hashlib.md5(token.encode()).hexdigest(), 16) % 64] += 1.0
        vectors.append(vec)
    return vectors


@pytest.fixture(autouse=True)
def stub_local_runtime(monkeypatch):
    async def no_title(*_a, **_k):
        return None

    async def unknown_caps(*_a, **_k):
        return None

    monkeypatch.setattr(llm, "generate_title", no_title)
    monkeypatch.setattr(titles, "generate", no_title)
    limiter.reset()
    catalog.clear_cache()
    monkeypatch.setattr(runtime, "get_capabilities", unknown_caps)
    monkeypatch.setattr(embeddings, "embed_texts", fake_embed)


@pytest.fixture()
def test_settings(tmp_path):
    return Settings(
        data_dir=str(tmp_path), chunk_size=300, chunk_overlap=30, retrieval_char_budget=1500, retrieval_top_k=3,
        searxng_url=None, imagegen_url=None, deepseek_api_key=None, gemini_api_key=None,
        encryption_key=Fernet.generate_key().decode(), provider_retry_backoff_s=0.0,
    )


@pytest.fixture()
def client(monkeypatch, test_settings):
    engine = make_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(dbmod, "SessionLocal", Session)  # used by streaming + background jobs

    def override():
        with Session() as s:
            yield s

    fastapi_app.dependency_overrides[get_db] = override
    fastapi_app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


def make_headers(client):
    return {"Authorization": "Bearer " + client.post("/api/v1/auth/guest").json()["access_token"]}


@pytest.fixture()
def guest_headers(client):
    return make_headers(client)
