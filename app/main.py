import os
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from bson import ObjectId
from datetime import datetime

from .database import SessionLocal, connect_to_mongodb, close_mongodb_connection, get_mongo_db
from .models import User, NoteCreate, NoteResponse, NoteUpdate
from .schemas import UserCreate, UserOut, UserUpdate

# Load environment variables
load_dotenv()

# Create FastAPI instance
app = FastAPI(
    title=os.getenv("APP_NAME", "FastAPI Application"),
    description="A CRUD API for user management with PostgreSQL",
    version="1.0.0"
)

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    await connect_to_mongodb()

@app.on_event("shutdown")
async def shutdown_event():
    await close_mongodb_connection()

# Dependency: Database Session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Health check endpoint
@app.get("/ping", status_code=status.HTTP_200_OK)
def ping():
    return {"message": "pong"}

# CREATE: Add a new user
@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    # Check if email or username already exists
    existing_user = db.query(User).filter(
        (User.email == payload.email) | (User.username == payload.username)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already exists")

    # Create new user
    user = User(email=payload.email, username=payload.username)
    db.add(user)        # Add to session
    db.commit()         # Save to database
    db.refresh(user)    # Reload from database (get the ID)

    return user

# READ: Get all users
@app.get("/users", response_model=list[UserOut], status_code=status.HTTP_200_OK)
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.id.asc()).all()

# READ: Get single user by ID
@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found")

    return user

# UPDATE: Modify existing user
@app.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db)
):
    # Get existing user
    user  = db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found")

    # Update email if provided and different
    if payload.email and payload.email != user.email:
        # Check if email already taken
        if db.query(User).filter(User.email == payload.email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use")
        user.email = payload.email

    # Update username if provided and different
    if payload.username and payload.username != user.username:
        # Check if username already taken
        if db.query(User).filter(User.username == payload.username).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already in use")
        user.username = payload.username

    db.add(user)        # Mark as modified
    db.commit()         # Save changes
    db.refresh(user)    # Reload from database

    return user

# DELETE: Remove a user
@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found")

    db.delete(user)     # Mark for deletion
    db.commit()         # Execute deletion

    return None

# Helper function to convert MongoDB document to response format
def note_helper(note) -> dict:
    """
    Convert MongoDB document to API response format.

    Converts ObjectId to string and structures data according to NoteResponse schema.
    """
    return {
        "id": str(note["_id"]),
        "title": note["title"],
        "content": note["content"],
        "tags": note.get("tags", []),
        "created_at": note["created_at"]
    }

@app.post("/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(note: NoteCreate):
    db = get_mongo_db()

    # Prepare note document
    note_dict: dict[str, any] = note.model_dump()
    note_dict["created_at"] = datetime.utcnow()

    # Insert into MongoDB
    result = await db.notes.insert_one(note_dict)

    # Retrieve the created note
    created_note = await db.notes.find_one({"_id": result.inserted_id})

    return note_helper(created_note)

@app.get("/notes", response_model=list[NoteResponse], status_code=status.HTTP_200_OK)
async def get_all_notes():
    db = get_mongo_db()

    # Find all notes, sort by creation time (newest first)
    notes = await db.notes.find().sort("created_at", -1).to_list(length=100)

    return [note_helper(note) for note in notes]

@app.get("/notes/{note_id}", response_model=NoteResponse)
async def get_note(note_id: str):
    # Validate ObjectId format
    if not ObjectId.is_valid(note_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid note ID format")

    db = get_mongo_db()
    note = await db.notes.find_one({"_id": ObjectId(note_id)})

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found")

    return note_helper(note)

@app.put("/notes/{note_id}", response_model=NoteResponse)
async def update_note(note_id: str, note_update: NoteUpdate):
    if not ObjectId(note_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid note ID format")

    db = get_mongo_db()

    # Only include fields that were provided
    update_data = note_update.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update")

    # Update the note
    result = await db.notes.update_one(
        {"_id": ObjectId(note_id)},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found")

    # Retrieve and return updated note
    updated_note = await db.notes.find_one({"_id": ObjectId(note_id)})
    return note_helper(updated_note)

async def delete_note(note_id: str):
    # Validate ObjectId format
    if not ObjectId(note_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid note ID format")

    db = get_mongo_db()
    result = await db.notes.delete_one({"_id": ObjectId(note_id)})

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found")

    return None
