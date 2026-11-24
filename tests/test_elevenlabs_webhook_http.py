import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import elevenlabs_webhook as webhook


SECRET = "local-test-secret"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("ELEVENLABS_AGENT_ID", "test-agent")
    monkeypatch.setattr(webhook, "DB_PATH", tmp_path / "test.db")
    return TestClient(app)


def signed_headers(payload):
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    digest = hmac.new(
        SECRET.encode(),
        timestamp.encode() + b"." + body,
        hashlib.sha256
    ).hexdigest()
    return body, {
        "Content-Type": "application/json",
        "ElevenLabs-Signature": f"t={timestamp},v0={digest}"
    }


def test_missing_secret_returns_503(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_WEBHOOK_SECRET", raising=False)
    with TestClient(app) as test_client:
        response = test_client.post(
            "/webhooks/elevenlabs",
            json={"type": "post_call_transcription", "data": {}}
        )
    assert response.status_code == 503


def test_invalid_signature_returns_401(client):
    response = client.post(
        "/webhooks/elevenlabs",
        content=b'{"type":"post_call_transcription","data":{}}',
        headers={"ElevenLabs-Signature": "t=1,v0=invalid"}
    )
    assert response.status_code == 401


def test_valid_event_is_stored_once(client):
    payload = {
        "type": "post_call_transcription",
        "data": {
            "conversation_id": "test-conversation",
            "agent_id": "test-agent"
        },
        "event_timestamp": time.time()
    }
    body, headers = signed_headers(payload)

    first = client.post("/webhooks/elevenlabs", content=body, headers=headers)
    second = client.post("/webhooks/elevenlabs", content=body, headers=headers)

    assert first.status_code == 200
    assert first.json()["received"] is True
    assert first.json()["duplicate"] is False
    assert second.status_code == 200
    assert second.json()["duplicate"] is True


def test_malformed_json_returns_400(client):
    body = b"{not-json"
    timestamp = str(int(time.time()))
    digest = hmac.new(
        SECRET.encode(), timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    response = client.post(
        "/webhooks/elevenlabs",
        content=body,
        headers={"ElevenLabs-Signature": f"t={timestamp},v0={digest}"}
    )
    assert response.status_code == 400


def test_unsupported_event_returns_400(client):
    payload = {"type": "unknown_event", "data": {}}
    body, headers = signed_headers(payload)
    response = client.post("/webhooks/elevenlabs", content=body, headers=headers)
    assert response.status_code == 400
def test_audio_event_is_rejected(client):
    payload = {
        "type": "post_call_audio",
        "data": {"conversation_id": "audio-test"}
    }
    body, headers = signed_headers(payload)
    response = client.post(
        "/webhooks/elevenlabs",
        content=body,
        headers=headers
    )
    assert response.status_code == 400


def test_transcription_content_is_not_stored(client):
    import sqlite3

    private_text = "TRANSCRIPT_PRIVATE_TEST_987654"
    payload = {
        "type": "post_call_transcription",
        "data": {
            "conversation_id": "transcript-test",
            "agent_id": "test-agent",
            "transcript": private_text
        },
        "event_timestamp": time.time()
    }
    body, headers = signed_headers(payload)
    response = client.post(
        "/webhooks/elevenlabs",
        content=body,
        headers=headers
    )

    assert response.status_code == 200

    with sqlite3.connect(webhook.DB_PATH) as connection:
        rows = connection.execute(
            "SELECT * FROM call_events"
        ).fetchall()

    assert private_text not in repr(rows)


def test_rejects_unauthorized_agent(client):
    payload = {"type": "post_call_transcription", "data": {"conversation_id": "foreign-agent", "agent_id": "unauthorized-agent"}}
    body, headers = signed_headers(payload)
    response = client.post("/webhooks/elevenlabs", content=body, headers=headers)
    assert response.status_code == 403
