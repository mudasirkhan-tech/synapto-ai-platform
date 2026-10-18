from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.services import limiter
from app.security import burn_verify, create_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _token(user: User, settings: Settings) -> TokenOut:
    return TokenOut(access_token=create_token(user.id, settings), user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    limiter.enforce("register", 30, 3600)
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    name = (body.display_name or email.split("@")[0]).strip()[:80] or "User"
    user = User(email=email, password_hash=hash_password(body.password), display_name=name)
    db.add(user)
    db.commit()
    return _token(user, settings)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    limiter.enforce(f"login:{body.email.lower()}", 10, 60)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not user.password_hash:
        burn_verify(body.password)
        raise HTTPException(401, "Incorrect email or password")
    if not verify_password(user.password_hash, body.password):
        raise HTTPException(401, "Incorrect email or password")
    return _token(user, settings)


@router.post("/guest", response_model=TokenOut)
def guest(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    limiter.enforce("guest", 60, 3600)
    user = User(display_name="Guest", is_guest=True)
    db.add(user)
    db.commit()
    return _token(user, settings)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
