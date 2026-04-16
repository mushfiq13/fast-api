from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr                          # Validates email format
    username: str = Field(
        min_length=3,                        # Minimum 3 characters
        max_length=50                        # Maximum 50 characters
    )
    password: str = Field(min_length=6, description="Minimum 6 characters")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "alice@example.com",
                "username": "alice",
                "password": "securepassword123"
            }
        }

class UserUpdate(BaseModel):
    email: EmailStr | None = None            # Optional email
    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=50
    )

class UserOut(BaseModel):
    id: int
    email: EmailStr
    username: str

    class Config:
        """Pydantic configuration."""
        from_attributes = True               # Allow creating from ORM models
        json_schema_extra = {
            "example": {
                "id": 1,
                "email": "alice@example.com",
                "username": "alice"
            }
        }

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer"
            }
        }

class TokenData(BaseModel):
    email: Optional[str] = None
