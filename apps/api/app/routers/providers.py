"""API-key management. Keys are write-only: they are encrypted at rest and never returned by any endpoint."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.providers import CLOUD_IDS, PROVIDERS
from app.providers.base import CallContext
from app.schemas import ProviderKeyIn, ProviderOut, ProviderTestIn
from app.services import catalog, credentials, limiter

router = APIRouter(prefix="/providers", tags=["providers"])


def _provider(provider_id: str) -> str:
    if provider_id not in CLOUD_IDS:
        raise HTTPException(404, "Unknown provider")
    return provider_id


def _out(pid: str, status: dict) -> ProviderOut:
    return ProviderOut(id=pid, label=PROVIDERS[pid].label, **status[pid])


@router.get("", response_model=list[ProviderOut])
def list_providers(user: User = Depends(get_current_user), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    status = credentials.key_status(db, user.id, settings)
    return [_out(pid, status) for pid in CLOUD_IDS]


@router.put("/{provider_id}/key", response_model=ProviderOut)
def save_key(
    provider_id: str, body: ProviderKeyIn,
    user: User = Depends(get_current_user), db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
):
    pid = _provider(provider_id)
    limiter.enforce(f"keys:{user.id}", 20, 60)
    try:
        key = credentials.validate_key(pid, body.api_key)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    credentials.save_user_key(db, user.id, pid, key, settings)
    catalog.clear_cache()
    return _out(pid, credentials.key_status(db, user.id, settings))


@router.delete("/{provider_id}/key", response_model=ProviderOut)
def delete_key(provider_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    pid = _provider(provider_id)
    limiter.enforce(f"keys:{user.id}", 20, 60)
    credentials.delete_user_key(db, user.id, pid)
    catalog.clear_cache()
    return _out(pid, credentials.key_status(db, user.id, settings))


@router.post("/{provider_id}/test")
async def test_key(
    provider_id: str, body: ProviderTestIn,
    user: User = Depends(get_current_user), db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
):
    """Tests a key you are about to save (sent in the body, never stored by this call) or the one already in use."""
    pid = _provider(provider_id)
    limiter.enforce(f"keys:{user.id}", 20, 60)
    if body.api_key:
        try:
            key = credentials.validate_key(pid, body.api_key)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    else:
        key = credentials.resolve_keys(db, user.id, settings).get(pid)
        if not key:
            raise HTTPException(422, f"No {PROVIDERS[pid].label} API key to test. Enter one first.")
    ok, message = await PROVIDERS[pid].test(CallContext(key, settings))
    catalog.clear_cache()
    return {"ok": ok, "message": message}
