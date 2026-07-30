import uuid
from datetime import datetime, UTC

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db, UserModel
from app.core.security import hash_password, verify_password, create_access_token
from app.core.rate_limit import limiter, AUTH_LIMIT
from app.schemas.auth import (
    SignupRequest, LoginRequest, TokenResponse, UserResponse,
)
from app.api.deps import CurrentUserDep

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_user_response(u: UserModel) -> UserResponse:
    return UserResponse(id=u.id, email=u.email, display_name=u.display_name)


@router.post("/signup", response_model=TokenResponse, status_code=201)
@limiter.limit(AUTH_LIMIT)
def signup(request: Request, body: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = body.email.lower().strip()
    if db.query(UserModel).filter(UserModel.email == email).first():
        raise HTTPException(409, "An account with this email already exists")

    user = UserModel(
        id=str(uuid.uuid4()),
        email=email,
        hashed_password=hash_password(body.password),
        display_name=(body.display_name or "").strip() or None,
        created_at=datetime.now(UTC),
    )
    db.add(user)
    db.commit()

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=_to_user_response(user))


@router.post("/login", response_model=TokenResponse)
@limiter.limit(AUTH_LIMIT)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = body.email.lower().strip()
    user = db.query(UserModel).filter(UserModel.email == email).first()
    # Same error for missing user vs wrong password (no account enumeration)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Incorrect email or password")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=_to_user_response(user))


@router.get("/me", response_model=UserResponse)
def me(current_user: CurrentUserDep) -> UserResponse:
    return _to_user_response(current_user)
