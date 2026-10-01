from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    theme_preference: str = "dark"
    created_at: datetime

    model_config = {"from_attributes": True}


class UserPreferenceUpdate(BaseModel):
    theme_preference: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
