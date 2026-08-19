from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user_model import User
from app.services.security import verify_password, hash_password
from app.services.jwt import create_jwt_token
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(prefix='/auth', tags=['auth'])
limiter = Limiter(key_func=get_remote_address)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/login")
@limiter.limit("5/minute")
def login_route(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    username = form_data.username
    password = form_data.password

    db_user = db.query(User).filter(func.lower(User.email) == func.lower(username)).first()
    if not db_user:
        # Usado para evitar ataques de enumeração de usuários, mesmo que o usuário não exista, a verificação de senha é feita com uma senha falsa
        verify_password(password, hash_password("fake_password"))
        raise HTTPException(status_code=401, detail="User not found or incorrect password")

    if verify_password(password, db_user.password_hash):
        token = create_jwt_token(db_user.id)
        return {"access_token": token, "token_type": "Bearer"}
    else:
        raise HTTPException(status_code=401, detail="User not found or incorrect password")
