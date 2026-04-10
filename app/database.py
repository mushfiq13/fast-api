import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from motor.motor_asyncio import AsyncIOMotorClient

# Load environment variables from .env file
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# MongoDB connection settings
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "lab3_db")

# Global MongoDB client and database instances
mongo_client: AsyncIOMotorClient = None
mongo_db = None

# Base class for all models
class Base(DeclarativeBase):
    pass

# Create database engine
engine = create_engine(
    DATABASE_URL,
    echo=True,  # Enable SQL query logging for debugging
    future=True  # Use SQLAlchemy 2.0 style queries
)

# Create session factory
# Sessions are your "workspace" for database operations
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,     # Don't automatically flush changes
    autocommit=False,    # Don't automatically commit
    future=True          # Use SQLAlchemy 2.0 style queries
)

async def connect_to_mongodb():
    global mongo_client, mongo_db

    mongo_client = AsyncIOMotorClient(MONGODB_URL)
    mongo_db = mongo_client[MONGODB_DB_NAME]

    print(f"✅ Connected to MongoDB at {MONGODB_URL}")
    print(f"✅ Using database: {MONGODB_DB_NAME}")

async def close_mongodb_connection():
    global mongo_client

    if mongo_client:
        mongo_client.close()
        print("✅ Closed MongoDB connection")

def get_mongo_db():
    return mongo_db
