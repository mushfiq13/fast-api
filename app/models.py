from .database import Base
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func

class User(Base):
    __tablename__ = "users"

    # Primary key column
    id = Column(
        Integer,
        primary_key=True,  # Unique identifier
        index=True         # Create index for faster queries
    )

    # Email column
    email = Column(
        String(255),       # Maximum 255 characters
        nullable=False,    # Cannot be NULL
        unique=True,       # Must be unique across all users
        index=True         # Create index for faster lookups
    )

    # Username column
    username = Column(
        String(50),        # Maximum 50 characters
        nullable=False,    # Cannot be NULL
        unique=True,       # Must be unique across all users
        index=True         # Create index for faster lookups
    )

    # NEVER store plain password!
    password_hash = Column(String(255), nullable=False)

    # Available Roles: "user", "admin"
    role = Column(String(5), nullable=False, server_default="user")

    is_active = Column(Boolean, nullable=False, server_default="True")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self):
        """String representation of User object."""
        return f"<User(id={self.id}, email='{self.email}', username='{self.username}')>"

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

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

class NoteResponse(BaseModel):
    id: str = Field(..., description="Unique identifier (MongoDB ObjectId)")
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
