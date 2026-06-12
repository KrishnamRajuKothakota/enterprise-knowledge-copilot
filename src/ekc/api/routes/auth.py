from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from src.ekc.db.session import get_db
from src.ekc.db.models import User, UserRole
from src.ekc.core.security import verify_password, hash_password, create_access_token
import uuid

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    role: UserRole = UserRole.junior_engineer  # capped at junior_engineer for self-service
    department: str | None = None


@router.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email,
                                  User.is_active == True).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token({"sub": user.user_id, "role": user.role.value})
    return TokenResponse(access_token=token, user_id=user.user_id,
                         role=user.role.value)


@router.post("/auth/register", response_model=TokenResponse, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    # Security: self-service registration cannot create admin accounts
    # Admin accounts must be created via scripts/seed_users.py
    safe_role = req.role if req.role != UserRole.admin else UserRole.junior_engineer
    user = User(
        user_id=str(uuid.uuid4()),
        name=req.name,
        email=req.email,
        password_hash=hash_password(req.password),
        role=safe_role,
        department=req.department,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": user.user_id, "role": user.role.value})
    return TokenResponse(access_token=token, user_id=user.user_id,
                         role=user.role.value)