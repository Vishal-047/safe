import os
import jwt
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger('safelane.platform')

JWT_SECRET = os.environ.get("JWT_SECRET")
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")

if not JWT_SECRET:
    raise ValueError("JWT_SECRET environment variable is required.")
if not ENCRYPTION_KEY:
    raise ValueError("ENCRYPTION_KEY environment variable is required.")

fernet = Fernet(ENCRYPTION_KEY.encode())

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
