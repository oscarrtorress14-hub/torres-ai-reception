import hashlib, hmac, time
from app.elevenlabs_webhook import verify_elevenlabs_signature

def signed_header(body, secret, timestamp):
    digest = hmac.new(secret.encode(), str(timestamp).encode() + b"." + body,
                      hashlib.sha256).hexdigest()
    return f"t={timestamp},v0={digest}"

def test_valid_signature():
    body, secret, ts = b'{"type":"post_call_transcription"}', "test-secret", int(time.time())
    assert verify_elevenlabs_signature(body, signed_header(body, secret, ts), secret)

def test_invalid_signature():
    ts = int(time.time())
    assert not verify_elevenlabs_signature(b"{}", f"t={ts},v0={'0'*64}", "secret")

def test_stale_signature_rejected():
    body, secret, ts = b"{}", "secret", 1_700_000_000
    assert not verify_elevenlabs_signature(body, signed_header(body, secret, ts),
                                           secret, now=ts + 1801)
