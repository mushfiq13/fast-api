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
