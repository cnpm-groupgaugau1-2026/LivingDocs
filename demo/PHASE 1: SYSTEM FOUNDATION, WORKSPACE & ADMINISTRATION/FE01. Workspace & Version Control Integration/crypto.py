import base64
import hashlib
import hmac
import secrets
import time

import jwt


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = b""
    counter = 0
    while len(out) < length:
        out += hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()
        counter += 1
    return out[:length]


def encrypt_text(plain: str, secret: str) -> str:
    key = hashlib.sha256(secret.encode()).digest()
    nonce = secrets.token_bytes(16)
    data = plain.encode()
    cipher = bytes(a ^ b for a, b in zip(data, _keystream(key, nonce, len(data))))
    mac = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(nonce + mac + cipher).decode()


def decrypt_text(token: str, secret: str) -> str:
    key = hashlib.sha256(secret.encode()).digest()
    raw = base64.urlsafe_b64decode(token.encode())
    nonce, mac, cipher = raw[:16], raw[16:48], raw[48:]
    expected = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        raise ValueError("invalid token")
    data = bytes(a ^ b for a, b in zip(cipher, _keystream(key, nonce, len(cipher))))
    return data.decode()


def sign_session(user_id: int, session_id: str, secret: str, ttl: int) -> str:
    now = int(time.time())
    return jwt.encode({"sub": str(user_id), "sid": session_id, "iat": now, "exp": now + ttl}, secret, algorithm="HS256")


def verify_session(token: str, secret: str) -> dict:
    return jwt.decode(token, secret, algorithms=["HS256"])


def sign_state(secret: str, ttl: int = 600) -> str:
    now = int(time.time())
    return jwt.encode({"n": secrets.token_urlsafe(12), "exp": now + ttl, "k": "state"}, secret, algorithm="HS256")


def verify_state(state: str, secret: str) -> bool:
    try:
        return jwt.decode(state, secret, algorithms=["HS256"]).get("k") == "state"
    except jwt.PyJWTError:
        return False


def make_app_jwt(app_id: str, private_key: str) -> str:
    now = int(time.time())
    return jwt.encode({"iat": now - 60, "exp": now + 540, "iss": str(app_id)}, private_key, algorithm="RS256")


def sign_payload(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, header: str) -> bool:
    if not header:
        return False
    return hmac.compare_digest(sign_payload(secret, body), header)
