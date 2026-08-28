import math

from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from email_validator import validate_email, EmailNotValidError

from app.database import SessionLocal
from app.models.user_model import User
from app.enums.role import Role
from app.schemas.user_schema import UserResponse
from app.services.security import hash_password
from app.services.jwt import get_current_user, require_roles
from app.services.logger import log_system_event

router = APIRouter(prefix="/users", tags=["users"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

admin_developer_only = Depends(require_roles(Role.ADMIN, Role.DEVELOPER))

# Função auxiliar para validar o formato do e-mail
def verify_and_normalize_email(email_str: str) -> str:
    try:
        # Valida a sintaxe e normaliza o e-mail (ex: tira espaços, converte minúsculas)
        email_info = validate_email(email_str, check_deliverability=False)
        return email_info.normalized
    except EmailNotValidError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de e-mail inválido: {str(e)}"
        )

admin_or_dev = Depends(require_roles(Role.ADMIN, Role.DEVELOPER))

@router.get("", dependencies=[admin_or_dev])
def get_users(page: int = 1, limit: int = 10, db: Session = Depends(get_db)):
    query = db.query(User)
    
    # Contagem total de usuários
    total_users = query.count()
    total_pages = math.ceil(total_users / limit) if total_users > 0 else 1
    
    # Busca paginada
    offset = (page - 1) * limit
    users = query.order_by(User.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "users": users,
        "total_users": total_users,
        "total_pages": total_pages,
        "current_page": page,
        "limit": limit
    }

@router.get("/{user_id}", response_model=UserResponse, dependencies=[admin_developer_only])
def get_user_by_id(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED, dependencies=[admin_developer_only])
def create_user(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: Role = Form(default=Role.USER),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Valida se o e-mail tem um formato válido
    normalized_email = verify_and_normalize_email(email)

    # 2. Verifica se o e-mail já está cadastrado
    existing_user = db.query(User).filter(func.lower(User.email) == func.lower(normalized_email)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email is already registered")

    new_user = User(
        name=name,
        email=normalized_email,
        password_hash=hash_password(password),
        role=role
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_system_event(
        db=db,
        level="INFO",
        source="Users",
        message=f"Usuário '{new_user.email}' ({new_user.role.value}) criado por '{current_user.email}'"
    )

    return new_user

@router.put("/{user_id}", response_model=UserResponse, dependencies=[admin_developer_only])
def update_user(
    user_id: int,
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    role: Optional[Role] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    changes = []
    if email:
        normalized_email = verify_and_normalize_email(email)
        email_exists = db.query(User).filter(
            func.lower(User.email) == func.lower(normalized_email), 
            User.id != user_id
        ).first()
        if email_exists:
            raise HTTPException(status_code=400, detail="Email is already in use")
        
        user.email = normalized_email
        changes.append("email")

    if name:
        user.name = name
        changes.append("nome")
    if password:
        user.password_hash = hash_password(password)
        changes.append("senha")
    if role:
        user.role = role
        changes.append(f"perfil para {role.value}")

    db.commit()
    db.refresh(user)

    # Log de Atualização
    log_system_event(
        db=db,
        level="INFO",
        source="Users",
        message=f"Usuário #{user.id} ({user.email}) atualizado por '{current_user.email}'. Campos: {', '.join(changes)}"
    )

    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[admin_developer_only])
def delete_user(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    deleted_email = user.email

    db.delete(user)
    db.commit()

    log_system_event(
        db=db,
        level="WARNING",
        source="Users",
        message=f"Usuário '{deleted_email}' (ID #{user_id}) foi excluído por '{current_user.email}'"
    )

    return None