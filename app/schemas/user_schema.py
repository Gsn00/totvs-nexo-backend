from pydantic import BaseModel, EmailStr
from datetime import datetime
from app.enums.role import Role

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: Role
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True