"""Authenticated, metadata-only ElevenLabs webhook receiver."""
from __future__ import annotations
import hashlib, hmac, json, os, sqlite3, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()
DB_PATH = Path(__file__).resolve().parent.parent / "demo.db"
MAX_BODY_BYTES = 256 * 1024
ALLOWED_EVENTS = {"post_call_transcription", "call_initiation_failure"}

def _db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def _ensure_table():
    with _db() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS call_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_key TEXT NOT NULL UNIQUE,
            conversation_id TEXT, agent_id TEXT, event_type TEXT NOT NULL,
            event_timestamp REAL, call_status TEXT, failure_reason TEXT,
            received_at TEXT NOT NULL
        )""")

def verify_elevenlabs_signature(raw_body: bytes, signature_header: str | None,
                                secret: str, *, now: int | None = None,
                                tolerance_seconds: int = 1800) -> bool:
    if not signature_header or not secret:
        return False
    try:
        values = dict(part.strip().split("=", 1) for part in signature_header.split(","))
        timestamp = values["t"]
        supplied = values["v0"]
        stamp = int(timestamp)
    except (KeyError, ValueError):
        return False
    current = int(time.time()) if now is None else now
    if abs(current - stamp) > tolerance_seconds:
        return False
    signed = timestamp.encode() + b"." + raw_body
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied)

@router.post("/webhooks/elevenlabs", status_code=200)
async def receive_elevenlabs_webhook(request: Request) -> dict[str, Any]:
    secret = os.getenv("ELEVENLABS_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(503, "ElevenLabs webhook is not configured")
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(413, "Webhook payload too large")
    if not verify_elevenlabs_signature(raw, request.headers.get("ElevenLabs-Signature"), secret):
        raise HTTPException(401, "Invalid webhook signature")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(400, "Invalid JSON payload")
    event_type, data = payload.get("type"), payload.get("data")
    if event_type not in ALLOWED_EVENTS or not isinstance(data, dict):
        raise HTTPException(400, "Unsupported webhook event")
    conversation_id, agent_id = data.get("conversation_id"), data.get("agent_id")
    timestamp = payload.get("event_timestamp")
    if conversation_id is not None and not isinstance(conversation_id, str):
        raise HTTPException(400, "Invalid conversation_id")
    if agent_id is not None and not isinstance(agent_id, str):
        raise HTTPException(400, "Invalid agent_id")
    if timestamp is not None and not isinstance(timestamp, (int, float)):
        raise HTTPException(400, "Invalid event_timestamp")
    event_key = (f"{event_type}:{conversation_id}" if conversation_id
                 else hashlib.sha256(raw).hexdigest())
    status, reason = data.get("status"), data.get("failure_reason")
    if not isinstance(status, str): status = None
    if not isinstance(reason, str): reason = None
    _ensure_table()
    with _db() as c:
        cur = c.execute("""INSERT OR IGNORE INTO call_events
        (event_key, conversation_id, agent_id, event_type, event_timestamp,
         call_status, failure_reason, received_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_key, conversation_id, agent_id, event_type, timestamp, status, reason,
         datetime.now(timezone.utc).isoformat()))
        inserted = cur.rowcount == 1
    return {"received": True, "duplicate": not inserted, "event_type": event_type}
