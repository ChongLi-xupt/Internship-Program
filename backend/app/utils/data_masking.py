"""
Utility functions: data masking (AES-256-GCM), SQL parsing helpers, text utils.
"""

import hashlib
import os
import re
from typing import Any, Dict


# ── Data Masking / Encryption ──

def encrypt_data(plaintext: str) -> str:
    """Encrypt sensitive data (e.g., DB passwords) using AES-256-GCM."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = bytes.fromhex(_get_encryption_key())
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return (nonce + ciphertext).hex()


def decrypt_data(ciphertext_hex: str) -> str:
    """Decrypt data encrypted with encrypt_data()."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = bytes.fromhex(_get_encryption_key())
    raw = bytes.fromhex(ciphertext_hex)
    nonce, ciphertext = raw[:12], raw[12:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def decrypt_connection_config(encrypted: str | None) -> Dict[str, Any]:
    """Decrypt and parse stored connection config JSON."""
    if not encrypted:
        return {}
    import json
    decrypted = decrypt_data(encrypted)
    return json.loads(decrypted)


def _get_encryption_key() -> str:
    """Get encryption key from config, ensuring valid format."""
    from app.config import settings
    key = settings.encryption_key.strip()
    if len(key) != 64:  # 32 bytes = 64 hex chars
        raise ValueError(f"ENCRYPTION_KEY must be 32 bytes (64 hex chars), got {len(key)}")
    return key


# ── SQL Parsing Helpers ──

def validate_sql_syntax(sql: str) -> tuple[bool, str]:
    """Validate SQL syntax using sqlglot. Returns (is_valid, error_message)."""
    try:
        import sqlglot

        parsed = sqlglot.parse_one(sql)
        return True, str(parsed)
    except Exception as e:
        return False, str(e)


def extract_tables_from_sql(sql: str) -> list[str]:
    """Extract table names referenced in a SQL statement."""
    try:
        import sqlglot

        parsed = sqlglot.parse_one(sql)
        tables = set()
        for table in parsed.find_all(sqlglot.exp.Table):
            tables.add(str(table.name) if table.name else "")
        return sorted(t for t in tables if t)
    except Exception:
        return []


def normalize_sql(sql: str) -> str:
    """Normalize SQL for comparison (whitespace/case normalization)."""
    try:
        import sqlglot

        parsed = sqlglot.parse_one(sql)
        return str(parsed).strip().lower()
    except Exception:
        return sql.strip()


# ── Text Utilities ──

def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """Truncate text to max_length, adding suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def extract_citation_markers(text: str) -> list[tuple[int, str]]:
    """Extract citation markers like [doc_1], [1], etc. Returns [(position, marker)]."""
    pattern = re.compile(r"\[(doc_(\d+)|(\d))\]")
    return [(m.start(), m.group()) for m in pattern.finditer(text)]


def mask_sensitive_value(value: str, mask_type: str = "phone") -> str:
    """Apply simple masking to sensitive values."""
    if not value:
        return value
    if mask_type == "phone":
        if len(value) >= 7:
            return value[:3] + "****" + value[-4:]
        return "****"
    elif mask_type == "id_card":
        if len(value) >= 10:
            return value[:6] + "*" * (len(value) - 10) + value[-4:]
        return "***"
    elif mask_type == "email":
        at_pos = value.find("@")
        if at_pos > 1:
            return value[0] + "***" + value[at_pos:]
        return "***@***"
    elif mask_type == "name":
        if len(value) > 1:
            return value[0] + "*" * (len(value) - 1)
        return "*"
    return "***"


def compute_permission_fingerprint(permissions: list[str]) -> str:
    """
    Compute a hash of user permissions for cache key generation.
    Users with different permissions MUST NOT share cached results.
    """
    sorted_perms = sorted(set(permissions))
    perm_string = ",".join(sorted_perms)
    return hashlib.sha256(perm_string.encode()).hexdigest()[:12]
