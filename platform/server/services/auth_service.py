import os
import jwt
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger('safelane.platform')

import base64
import hashlib

JWT_SECRET = os.environ.get("JWT_SECRET", "default_jwt_secret_safelane_demo_2026")
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "mwqVH_ai0ZtuiKFJhWr0uZnUxtmfHBJ0CJqMY3RcmMY=")

try:
    fernet = Fernet(ENCRYPTION_KEY.encode())
except Exception as e:
    logger.warning(f"ENCRYPTION_KEY is not a valid Fernet key: {e}. Deriving valid key from SHA256.")
    derived_key = base64.urlsafe_b64encode(hashlib.sha256(ENCRYPTION_KEY.encode()).digest())
    fernet = Fernet(derived_key)

def encrypt_pat(pat: str) -> str:
    return fernet.encrypt(pat.encode()).decode()

def decrypt_pat(encrypted: str) -> str:
    return fernet.decrypt(encrypted.encode()).decode()

def create_jwt(user_data: dict) -> str:
    payload = user_data.copy()
    payload['exp'] = datetime.now(timezone.utc) + timedelta(hours=24)
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise ValueError("Invalid or expired JWT")
