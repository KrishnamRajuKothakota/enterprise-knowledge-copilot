from fastapi import Depends, Header
from sqlalchemy.orm import Session
from typing import Optional
from src.ekc.db.session import get_db
from src.ekc.db.models import User, UserRole
from src.ekc.core.security import decode_token
from src.ekc.core.exceptions import UnauthorizedException, ForbiddenException


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedException()
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException("Invalid token")
    user = db.query(User).filter(User.user_id == user_id,
                                  User.is_active == True).first()
    if not user:
        raise UnauthorizedException("User not found or inactive")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise ForbiddenException("Admin role required")
    return current_user