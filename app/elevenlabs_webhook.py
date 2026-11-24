
"""Authenticated, metadata-only ElevenLabs webhook receiver."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import sqlite3
import time

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()

DB_PATH = Path(__file__).resolve().parent.parent / "demo.db"
MAX_BODY_BYTES = 256 * 1024
ALLOWED_EVENTS = {"post_call_transcription", "call_initiation_failure"}


def _db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_table():
    with _db() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS call_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_key TEXT NOT NULL UNIQUE,
                conversation_id TEXT,
                agent_id TEXT,
                event_type TEXT NOT NULL,
                event_timestamp REAL,
                call_status TEXT,
                failure_reason TEXT,
                received_at TEXT NOT NULL
            )
        """)


def verify_elevenlabs_signature(
    raw_body: bytes,
    signature_header: str | None,
    secret: str,
    *,
    now: int | None = None,
    tolerance_seconds: int = 1800,
) -> bool:
    if not signature_header or not secret:
        return False

    try:
        values = dict(
            part.strip().split("=", 1)
            for part in signature_header.split(",")
        )
        timestamp = values["t"]
        supplied = values["v0"]
        stamp = int(timestamp)
    except (KeyError, ValueError):
        return False

    current = int(time.time()) if now is None else now
    if abs(current - stamp) > tolerance_seconds:
        return False

    signed = timestamp.encode() + b"." + raw_body
    expected = hmac.new(
        secret.encode(),
        signed,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, supplied)


async def _read_limited_body(request: Request) -> bytes:
    content_length = request.headers.get("content-length")

    if content_length:
        try:
            if int(content_length) > MAX_BODY_BYTES:
                raise HTTPException(413, "Webhook payload too large")
        except ValueError:
            raise HTTPException(400, "Invalid Content-Length")

    chunks = []
    total = 0

    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_BODY_BYTES:
            raise HTTPException(413, "Webhook payload too large")
        chunks.append(chunk)

    return b"".join(chunks)


@router.post("/webhooks/elevenlabs", status_code=200)
async def receive_elevenlabs_webhook(request: Request) -> dict[str, Any]:
    secret = os.getenv("ELEVENLABS_WEBHOOK_SECRET", "")
    expected_agent_id = os.getenv("ELEVENLABS_AGENT_ID", "")

    if not secret or not expected_agent_id:
        raise HTTPException(
            503,
            "ElevenLabs webhook is not fully configured",
        )

    raw = await _read_limited_body(request)

    if not verify_elevenlabs_signature(
        raw,
        request.headers.get("ElevenLabs-Signature"),
        secret,
    ):
        raise HTTPException(401, "Invalid webhook signature")

    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(400, "Invalid JSON payload")

    if not isinstance(payload, dict):
        raise HTTPException(400, "JSON payload must be an object")

    event_type = payload.get("type")
    data = payload.get("data")

    if not isinstance(event_type, str) or event_type not in ALLOWED_EVENTS:
        raise HTTPException(400, "Unsupported webhook event")

    if not isinstance(data, dict):
        raise HTTPException(400, "Invalid event data")

    conversation_id = data.get("conversation_id")
    agent_id = data.get("agent_id")
    timestamp = payload.get("event_timestamp")

    if not isinstance(agent_id, str) or not hmac.compare_digest(
        agent_id,
        expected_agent_id,
    ):
        raise HTTPException(403, "Unauthorized ElevenLabs agent")

    if conversation_id is not None and (
        not isinstance(conversation_id, str) or not conversation_id.strip()
    ):
        raise HTTPException(400, "Invalid conversation_id")

    if timestamp is not None:
        if (
            isinstance(timestamp, bool)
            or not isinstance(timestamp, (int, float))
            or not math.isfinite(timestamp)
        ):
            raise HTTPException(400, "Invalid event_timestamp")

    event_key = (
        f"{event_type}:{conversation_id}"
        if conversation_id
        else hashlib.sha256(raw).hexdigest()
    )

    status = data.get("status")
    reason = data.get("failure_reason")

    if not isinstance(status, str):
        status = None

    if not isinstance(reason, str):
        reason = None

    _ensure_table()

    with _db() as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO call_events
            (
                event_key,
                conversation_id,
                agent_id,
                event_type,
                event_timestamp,
                call_status,
                failure_reason,
                received_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_key,
                conversation_id,
                agent_id,
                event_type,
                timestamp,
                status,
                reason,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        inserted = cursor.rowcount == 1

    return {
        "received": True,
        "duplicate": not inserted,
        "event_type": event_type,
    }

