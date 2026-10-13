"""Column-level encryption for sensitive values (mobile numbers, meeting links, MFA secrets).

Values are Fernet-encrypted (AES-128-CBC + HMAC) before they reach the database, so a raw
dump shows ciphertext. Because ciphertext is randomised, equality checks (duplicate mobile
numbers) use a separate HMAC "blind index" column.
"""
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _fernet():
    return Fernet(settings.FIELD_ENCRYPTION_KEY.encode())


def blind_index(value: str) -> str:
    normalised = "".join(ch for ch in str(value) if ch.isalnum()).lower()
    return hmac.new(settings.BLIND_INDEX_KEY.encode(), normalised.encode(), hashlib.sha256).hexdigest()


class EncryptedTextField(models.TextField):
    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value in (None, ""):
            return value
        return _fernet().encrypt(str(value).encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value in (None, ""):
            return value
        try:
            return _fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            return None
