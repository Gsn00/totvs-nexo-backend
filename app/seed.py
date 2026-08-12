import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user_model import User
from app.services.security import hash_password

load_dotenv()

def create_admin_user():
    name = os.getenv("ADMIN_NAME")
    email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_PASSWORD")

    db: Session = SessionLocal()
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        return

    password = hash_password(password)

    new_user = User(name=name, email=email, password_hash=password, role="admin")

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
        