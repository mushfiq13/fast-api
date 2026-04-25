import os
import time
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Query, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from bson import ObjectId
from datetime import datetime, timedelta
from typing import List, Optional

from .database import SessionLocal
from .mongodb import connect_to_mongodb, close_mongodb_connection, get_mongodb
from .elasticsearch import connect_to_elasticsearch, close_elasticsearch_connection, get_elasticsearch
from .models import User
from .schemas import Token, UserCreate, UserOut, UserUpdate, \
    NoteCreate, NoteOut, NoteUpdate, SearchResult, \
    ActivityLogCreate, ActivityLogOut
from .redis_client import connect_to_redis, close_redis_connection, cache_get, cache_set, cache_delete, cache_delete_pattern
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

# Load environment variables
load_dotenv()

ELASTICSEARCH_INDEX = os.getenv("ELASTICSEARCH_INDEX")

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
    await connect_to_elasticsearch()
    await connect_to_redis()

@app.on_event("shutdown")
async def shutdown_event():
    await close_mongodb_connection()
    await close_elasticsearch_connection()
    await close_redis_connection()

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

# HTTPBearer scheme for token authentication
security = HTTPBearer()

# Dependency: Get current authenticated user
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Extract token from credentials
    token = credentials.credentials

    # Decode token
    email = decode_access_token(token)
    if email is None:
        raise credentials_exception

    # Get user from database
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    return user

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

@app.post("/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
async def create_note(note: NoteCreate):
    mongodb = get_mongodb()
    es = get_elasticsearch()

    # Prepare note document
    note_dict: dict[str, any] = note.model_dump()
    note_dict["created_at"] = datetime.utcnow()

    # Insert into MongoDB
    result = await mongodb.notes.insert_one(note_dict)

    # Index in Elasticsearch
    await es.index(
        index=ELASTICSEARCH_INDEX,
        id=str(result.inserted_id),
        document={
            "title": note.title,
            "content": note.content,
            "tags": note.tags,
            "created_at": note_dict["created_at"].isoformat()
        }
    )

    # Return created note
    note_dict["_id"] = str(result.inserted_id)
    return note_dict

@app.get("/notes", response_model=list[NoteOut], status_code=status.HTTP_200_OK)
async def get_all_notes(limit: int = Query(default=10, le=100)):
    mongodb = get_mongodb()

    # Find all notes, sort by creation time (newest first)
    notes = await mongodb.notes.find().sort("created_at", -1).to_list(length=limit)

    for note in notes:
        note["_id"] = str(note["_id"])

    return notes

@app.get("/notes/{note_id}", response_model=NoteOut)
async def get_note(
    note_id: str,
    x_cache_control: Optional[str] = Header(None)
):
    start_time = time.time()

    # Check if cache should be bypassed
    bypass_cache = x_cache_control == "no_cache"

    # Try cache first (unless bypassed)
    if not bypass_cache:
        cached_note = await cache_get(f"note:{note_id}")
        if cached_note:
            elapsed = time.time() - start_time
            print(f"Cache hit for note:{note_id} {elapsed:.2f}ms")
            # Converting ISO string back to datetime for response
            cached_note["created_at"] = datetime.fromisoformat(cached_note["created_at"])
            return cached_note

    # Validate ObjectId format
    if not ObjectId.is_valid(note_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid note ID")

    mongodb = get_mongodb()
    note = await mongodb.notes.find_one({"_id": ObjectId(note_id)})

    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    note["_id"] = str(note["_id"])

    # Prepare cache-friendly version (datetime -> ISO string)
    cache_note = note.copy()
    cache_note["created_at"] = note["created_at"].isoformat()

    # Store in cache for future requests
    await cache_set(f"note:{note_id}", cache_note)

    elapsed = time.time() - start_time
    print(f"Cache miss for note:{note_id} {elapsed:.2f}ms")

    return note

@app.put("/notes/{note_id}", response_model=NoteOut)
async def update_note(note_id: str, note_update: NoteUpdate):
    if not ObjectId(note_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid note ID")

    db = get_mongodb()

    # Only include fields that were provided
    update_data = note_update.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    # Update the note
    result = await db.notes.update_one(
        {"_id": ObjectId(note_id)},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    # Invalidate cache (CRITICAL!)
    await cache_delete(f"note:{note_id}")

    # Retrieve and return updated note
    updated_note = await db.notes.find_one({"_id": ObjectId(note_id)})
    updated_note["_id"] = str(updated_note["_id"])
    return updated_note

@app.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: str):
    # Validate ObjectId format
    if not ObjectId(note_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid note ID")

    mongodb = get_mongodb()
    result = await mongodb.notes.delete_one({"_id": ObjectId(note_id)})

    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    # Invalidate cache (CRITICAL!)
    await cache_delete(f"note:{note_id}")

    # Delete from Elasticsearch
    es = get_elasticsearch()
    try:
        await es.delete(index=ELASTICSEARCH_INDEX,  id=note_id)
    except Exception as e:
        print(f"Error deleting note from Elasticsearch: {e}")

    return None

@app.get("/cache/stats")
async def cache_stats():
    from .redis_client import get_redis
    redis = get_redis()

    info = await redis.info()

    total_commands = info.get("total_commands_processed", 0)
    keyspace_hits = info.get("keyspace_hits", 0)
    keyspace_misses = info.get("keyspace_misses", 0)

    total_requests = keyspace_hits + keyspace_misses
    hit_rate = (keyspace_hits / total_requests * 100) if total_requests > 0 else 0

    return {
        "total_commands": total_commands,
        "keyspace_hits": keyspace_hits,
        "keyspace_misses": keyspace_misses,
        "hit_rate_percent": round(hit_rate, 2)
    }

@app.delete("/cache/notes", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cache(admin: User = Depends(require_admin)):
    await cache_delete_pattern("note:*")

@app.get("/search", response_model=list[SearchResult], status_code=status.HTTP_200_OK)
async def search_notes(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=10, le=100)
):
    es = get_elasticsearch()

    # Build Elasticsearch query
    search_body = {
        "query": {
            "multi_match": {
                "query": q,
                "fields": ["title^3", "content"],
                "fuzziness": "AUTO"
            }
        },
        "highlight": {
            "fields": {
                "title": {},
                "content": {"fragment_size": 150}
            }
        },
        "size": limit
    }

    # Execute search
    response = await es.search(
        index=ELASTICSEARCH_INDEX,
        body=search_body
    )

    # Format results
    results = []
    for hit in response["hits"]["hits"]:
        result = SearchResult(
            id=hit["_id"],
            title=hit["_source"]["title"],
            content=hit["_source"]["content"],
            tags=hit["_source"]["tags"],
            score=hit["_score"],
            highlight=hit.get("highlight")
        )
        results.append(result)

    return results

@app.post("/auth/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if email or username already exists
    existing_user = db.query(User).filter(
        (User.email == user_data.email) | (User.username == user_data.username)
    ).first()

    if existing_user:
        if existing_user.email == user_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )

    # Hash password
    hashed_password = hash_password(user_data.password)

    # Create new user
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=hashed_password
    )
    db.add(new_user)        # Add to session
    db.commit()             # Save to database
    db.refresh(new_user)    # Reload from database (get the ID)

    return new_user

@app.post("/auth/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # Find user by username
    user = db.query(User).filter(User.username == form_data.username).first()

    # Check if user exists and password is correct
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Log login activity to MongoDB
    mongodb = get_mongodb()
    await mongodb.activity_logs.insert_one({
        "user_id": user.id,
        "action": "login",
        "timestamp": datetime.utcnow(),
        "metadata": {}
    })

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/profile", response_model=UserOut)
async def get_profile(current_user: User = Depends(get_current_user)):
    # Automatic logging: log profile view
    mongodb = get_mongodb()
    await mongodb.activity_logs.insert_one({
        "user_id": current_user.id,
        "action": "profile_view",
        "timestamp": datetime.utcnow(),
        "metadata": {}
    })

    return current_user

# READ: Get all users
@app.get("/users", response_model=list[UserOut], status_code=status.HTTP_200_OK)
async def get_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Automatic logging: log users list view
    mongodb = get_mongodb()
    await mongodb.activity_logs.insert_one({
        "user_id": current_user.id,
        "action": "users_list_view",
        "timestamp": datetime.utcnow(),
        "metadata": {}
    })

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
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Prevent admin from deleting themselves
    if admin.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account")

    # Find the user to delete
    user = db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found")

    db.delete(user)     # Mark for deletion
    db.commit()         # Execute deletion

    return None

@app.post("/logs", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_custom_log(
    log_data: ActivityLogCreate,
    current_user: User = Depends(get_current_user)
):
    mongodb = get_mongodb()

    log_document = {
        "user_id": current_user.id,
        "action": log_data.action,
        "timestamp": datetime.utcnow(),
        "metadata": log_data.metadata or {}
    }

    result = await mongodb.activity_logs.insert_one(log_document)

    return { "log_id": str(result.inserted_id) }

@app.get("/logs", response_model=list[ActivityLogOut], status_code=status.HTTP_200_OK)
async def get_my_logs(
    current_user: User = Depends(get_current_user),
    limit: int = 10
):
    mongodb = get_mongodb()

    cursor = mongodb.activity_logs.find(
        {"user_id": current_user.id}
    ).sort("timestamp", -1).limit(limit)

    logs = await cursor.to_list(length=limit)

    # Convert ObjectId to string for JSON serialization
    for log in logs:
        log["_id"] = str(log["_id"])

    return logs

@app.get("/users/{user_id}/logs", response_model=list[ActivityLogOut], status_code=status.HTTP_200_OK)
async def get_user_logs(
    user_id: int,
    admin: User = Depends(require_admin),
    limit: int = 10,
    db: Session = Depends(get_db)
):
    # Check if user exists in PostgreSQL
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found")

    # Get logs from MongoDB
    mongodb = get_mongodb()
    cursor = mongodb.activity_logs.find(
        {"user_id": user_id}
    ).sort("timestamp", -1).limit(limit)

    logs = await cursor.to_list(length=limit)

    # Convert ObjectId to string for JSON serialization
    for log in logs:
        logs["_id"] = str(log["_id"])

    return logs
