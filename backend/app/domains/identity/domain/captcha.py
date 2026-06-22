import base64
import hashlib
import hmac
import json
import random
import uuid
from html import escape

from flask import current_app

from app.utils.time import utcnow


CAPTCHA_TTL_SECONDS = 5 * 60
CAPTCHA_TERMS_VERSION = "2026.06"
CAPTCHA_CHALLENGE_TYPES = ("sum", "difference", "phrase")


def captcha_secret():
    return current_app.config.get("SECRET_KEY", "nexus-prime")


def captcha_signature(payload):
    message = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(captcha_secret().encode("utf-8"), message, hashlib.sha256).hexdigest()


def normalize_captcha_answer(answer):
    return str(answer or "").strip().upper().replace(" ", "")


def captcha_answer_hash(answer, nonce):
    normalized = normalize_captcha_answer(answer)
    message = f"{nonce}:{normalized}".encode("utf-8")
    return hmac.new(captcha_secret().encode("utf-8"), message, hashlib.sha256).hexdigest()


def encode_captcha_token(payload):
    signed = {**payload, "signature": captcha_signature(payload)}
    raw = json.dumps(signed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_captcha_token(token):
    if not token:
        return None
    try:
        padded = f"{token}{'=' * (-len(token) % 4)}"
        signed = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except Exception:
        return None
    signature = signed.pop("signature", "")
    if not signature or not hmac.compare_digest(signature, captcha_signature(signed)):
        return None
    if int(utcnow().timestamp()) - int(signed.get("issued_at", 0)) > CAPTCHA_TTL_SECONDS:
        return None
    return signed


def captcha_svg(label, prompt):
    label = escape(label)
    prompt = escape(prompt)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="220" height="72" viewBox="0 0 220 72" role="img">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#14b8a6"/><stop offset="1" stop-color="#2563eb"/></linearGradient></defs>'
        '<rect width="220" height="72" rx="18" fill="#f8fafc"/>'
        '<path d="M18 54 C48 16, 72 64, 110 28 S166 26, 204 50" fill="none" stroke="#cbd5e1" stroke-width="2"/>'
        '<circle cx="35" cy="20" r="3" fill="#99f6e4"/><circle cx="188" cy="18" r="4" fill="#bfdbfe"/>'
        '<text x="18" y="28" fill="#64748b" font-family="Arial, sans-serif" font-size="11" font-weight="700">REGISTER CHECK</text>'
        f'<text x="18" y="54" fill="url(#g)" font-family="Arial, sans-serif" font-size="25" font-weight="900">{label}</text>'
        f"<title>{prompt}</title>"
        "</svg>"
    )


def new_captcha_challenge(random_source=None):
    rng = random_source or random
    challenge_type = rng.choice(CAPTCHA_CHALLENGE_TYPES)
    if challenge_type == "sum":
        a = rng.randint(12, 38)
        b = rng.randint(4, 18)
        answer = str(a + b)
        label = f"{a} + {b} = ?"
        prompt = "请输入算式结果"
    elif challenge_type == "difference":
        a = rng.randint(31, 69)
        b = rng.randint(6, 24)
        answer = str(a - b)
        label = f"{a} - {b} = ?"
        prompt = "请输入算式结果"
    else:
        code = "".join(rng.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(4))
        answer = code
        label = " ".join(code)
        prompt = "请输入图中 4 位字符"
    issued_at = int(utcnow().timestamp())
    nonce = uuid.uuid4().hex
    token = encode_captcha_token({
        "answer_hash": captcha_answer_hash(answer, nonce),
        "issued_at": issued_at,
        "nonce": nonce,
        "type": challenge_type,
    })
    image = captcha_svg(label, prompt)
    return {
        "token": token,
        "image": image,
        "image_data_url": "data:image/svg+xml;base64," + base64.b64encode(image.encode("utf-8")).decode("ascii"),
        "prompt": prompt,
        "expires_in": CAPTCHA_TTL_SECONDS,
        "terms_version": CAPTCHA_TERMS_VERSION,
    }
