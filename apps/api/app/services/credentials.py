"""API-key handling: encryption at rest, resolution (user key > server env key), masking and log redaction."""
import logging
import os
import re
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import ProviderCredential, utcnow

ENV_VARS = {"deepseek": "DEEPSEEK_API_KEY", "gemini": "GEMINI_API_KEY"}
KEY_RE = re.compile(r"^[A-Za-z0-9._\-]{16,200}$")
SECRET_RE = re.compile(r"(sk-[A-Za-z0-9_\-]{12,}|AIza[0-9A-Za-z_\-]{20,}|Bearer\s+[A-Za-z0-9._\-]{12,})")


def redact(text: str) -> str:
    return SECRET_RE.sub("[redacted]", text)


class RedactingFilter(logging.Filter):
    """Scrubs API-key-shaped strings from every log record, including tracebacks."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact(record.getMessage())
            record.args = ()
            if record.exc_info:
                record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
                record.exc_info = None
        except Exception:  # never let logging break the app
            pass
        return True


def install_log_redaction() -> None:
    flt = RedactingFilter()
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "synapto.agent"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactingFilter) for f in logger.filters):
            logger.addFilter(flt)
        for handler in logger.handlers:
            if not any(isinstance(f, RedactingFilter) for f in handler.filters):
                handler.addFilter(flt)


# ---------- encryption ----------
def _fernet(settings: Settings) -> Fernet:
    key = settings.encryption_key
    if not key:
        path = Path(settings.data_dir) / ".secret_key"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            try:  # O_EXCL: never overwrite an existing key file
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as fh:
                    fh.write(Fernet.generate_key().decode())
            except FileExistsError:
                pass
        key = path.read_text().strip()
    return Fernet(key.encode())


def encrypt(settings: Settings, plaintext: str) -> str:
    return _fernet(settings).encrypt(plaintext.encode()).decode()


def decrypt(settings: Settings, token: str) -> str | None:
    try:
        return _fernet(settings).decrypt(token.encode()).decode()
    except InvalidToken:
        return None  # wrong master key or corrupted row: treated as "no key"


# ---------- validation / masking ----------
def validate_key(provider: str, key: str) -> str:
    cleaned = key.strip()
    if provider not in ENV_VARS:
        raise ValueError("Unknown provider")
    if not KEY_RE.match(cleaned):
        raise ValueError("That doesn't look like an API key (16–200 letters, digits, dots, dashes or underscores, no spaces).")
    return cleaned


def mask(last4: str | None) -> str | None:
    return f"••••••••{last4}" if last4 else None


def _env_key(settings: Settings, provider: str) -> str | None:
    value = getattr(settings, f"{provider}_api_key", None)
    return value.strip() if value and value.strip() else None


# ---------- storage ----------
def save_user_key(db: Session, user_id: str, provider: str, key: str, settings: Settings) -> None:
    row = db.scalar(select(ProviderCredential).where(ProviderCredential.user_id == user_id, ProviderCredential.provider == provider))
    token = encrypt(settings, key)
    if row is None:
        db.add(ProviderCredential(user_id=user_id, provider=provider, ciphertext=token, last4=key[-4:]))
    else:
        row.ciphertext, row.last4, row.updated_at = token, key[-4:], utcnow()
    db.commit()


def delete_user_key(db: Session, user_id: str, provider: str) -> bool:
    row = db.scalar(select(ProviderCredential).where(ProviderCredential.user_id == user_id, ProviderCredential.provider == provider))
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def resolve_keys(db: Session, user_id: str, settings: Settings) -> dict[str, str]:
    """provider -> plaintext key. A user's own key wins over the server-wide environment key."""
    keys: dict[str, str] = {}
    rows = db.scalars(select(ProviderCredential).where(ProviderCredential.user_id == user_id))
    for row in rows:
        plain = decrypt(settings, row.ciphertext)
        if plain:
            keys[row.provider] = plain
    for provider in ENV_VARS:
        if provider not in keys and (env := _env_key(settings, provider)):
            keys[provider] = env
    return keys


def key_status(db: Session, user_id: str, settings: Settings) -> dict[str, dict]:
    """Masked, non-secret status for the Settings screen."""
    out: dict[str, dict] = {}
    rows = {r.provider: r for r in db.scalars(select(ProviderCredential).where(ProviderCredential.user_id == user_id))}
    for provider, env_var in ENV_VARS.items():
        row = rows.get(provider)
        env = _env_key(settings, provider)
        if row is not None and decrypt(settings, row.ciphertext):
            out[provider] = {"configured": True, "source": "user", "masked": mask(row.last4), "env_var": env_var}
        elif env:
            out[provider] = {"configured": True, "source": "server", "masked": mask(env[-4:]), "env_var": env_var}
        else:
            out[provider] = {"configured": False, "source": None, "masked": None, "env_var": env_var}
    return out
