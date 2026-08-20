from datetime import datetime, timedelta, timezone
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
import os
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from app.enums.role import Role

load_dotenv()

JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM')
JWT_EXP_DELTA_DAYS = int(os.getenv('JWT_EXP_DELTA_DAYS', 1))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def create_jwt_token(user):
    expire = datetime.now(timezone.utc) + timedelta(days=JWT_EXP_DELTA_DAYS)
    payload = {
        'sub': str(user.id),
        'email': user.email,
        'name': user.name,
        'role': user.role.value,
        'exp': expire
    }
    encoded_jwt = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def decode_jwt_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_roles(*allowed_roles: Role):
    def role_checker(payload: dict = Depends(decode_jwt_token)):
        user_role = Role(payload.get('role'))
        if user_role not in allowed_roles:
            raise HTTPException(status_code=403, detail="You do not have permission to access this resource")
        return payload
    return role_checker