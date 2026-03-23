from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.schemas.user import UserCreate, UserRead
from app.crud import create_user, get_user_by_email
from app.core.db import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserRead)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    if get_user_by_email(db, user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    return create_user(db, user_in)
