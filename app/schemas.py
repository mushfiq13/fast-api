from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

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

class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Note title")
    content: str = Field(..., min_length=1, description="Note content")
    tags: Optional[list[str]] = Field(default=[], description="Optional tags for categorization")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Learn FastAPI",
                "content": "FastAPI is a modern web framework for building APIs",
                "tags": ["python", "fastapi", "tutorial"]
            }
        }

class NoteOut(BaseModel):
    id: str = Field(..., alias="_id", description="Unique identifier (MongoDB ObjectId)")
    title: str
    content: str
    tags: list[str]
    created_at: datetime = Field(..., description="Timestamp when note was created")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "60c72b2f9b1d4c3a5e8f9a1b",
                "title": "Learn FastAPI",
                "content": "FastAPI is a modern web framework",
                "tags": ["python", "fastapi"],
                "created_at": "2024-06-01T12:00:00Z"
            }
        }

class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    tags: Optional[list[str]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Updated Title",
                "tags": ["python", "fastapi", "mongodb"]
            }
        }

class SearchResult(BaseModel):
    id: str
    title: str
    content: str
    tags: list[str]
    score: float
    highlight: Optional[dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "title": "FastAPI Tutorial",
                "content": "FastAPI is a modern web framework...",
                "tags": ["fastapi", "python"],
                "score": 8.5,
                "highlight": {
                    "title": ["<em>FastAPI</em> Tutorial"]
                }
            }
        }

class ActivityLogCreate(BaseModel):
    """Input for creating activity logs"""
    action: str = Field(description="Action performed (e.g., login, profile_update)")
    metadata: Optional[dict] = Field(default={}, description="Additional information")

    class Config:
        json_schema_extra = {
            "example": {
                "action": "login",
                "metadata": {
                    "ip_address": "192.168.1.1",
                    "user_agent": "Mozilla/5.0"
                }
            }
        }

class ActivityLogOut(BaseModel):
    """Output for activity logs (includes MongoDB _id)"""
    id: str = Field(alias="_id", description="MongoDB document ID")
    user_id: int
    action: str
    timestamp: datetime
    metadata: dict = {}

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "user_id": 1,
                "action": "login",
                "timestamp": "2024-12-17T10:30:00Z",
                "metadata": {"ip_address": "192.168.1.1"}
            }
        }
