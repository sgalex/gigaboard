from pydantic import BaseModel, EmailStr, Field, model_validator
from uuid import UUID
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=255)
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "username": "john_doe",
                "password": "secure_password_123"
            }
        }

class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "secure_password_123"
            }
        }

class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    role: str = "user"  # "user" | "admin"
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def ensure_role(cls, data: any) -> any:
        """Гарантирует наличие role (для старых записей или ORM без атрибута)."""
        if isinstance(data, dict):
            if data.get("role") is None:
                data = {**data, "role": "user"}
        else:
            if getattr(data, "role", None) is None:
                data = {
                    "id": getattr(data, "id", None),
                    "email": getattr(data, "email", ""),
                    "username": getattr(data, "username", ""),
                    "role": "user",
                    "created_at": getattr(data, "created_at", None),
                    "updated_at": getattr(data, "updated_at", None),
                }
        return data

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "user@example.com",
                "username": "john_doe",
                "created_at": "2026-01-23T10:00:00",
                "updated_at": "2026-01-23T10:00:00"
            }
        }

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    expires_in: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "user": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "email": "user@example.com",
                    "username": "john_doe",
                    "created_at": "2026-01-23T10:00:00",
                    "updated_at": "2026-01-23T10:00:00"
                },
                "expires_in": 86400
            }
        }

class ErrorResponse(BaseModel):
    detail: str
    status_code: int
