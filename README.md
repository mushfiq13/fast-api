# FastAPI Application

A REST API built with FastAPI featuring user management (PostgreSQL), notes and
user activity logs (MongoDB), with JWT-based authentication.

## Tech Stack

| Layer         | Technology                            |
| ------------- | ------------------------------------- |
| Framework     | FastAPI                               |
| ASGI Server   | Uvicorn                               |
| Relational DB | PostgreSQL (via SQLAlchemy + Alembic) |
| Document DB   | MongoDB (via Motor — async)           |
| Auth          | JWT (python-jose) + bcrypt (passlib)  |
| Validation    | Pydantic v2                           |

## Project Structure

```
fast-api/
├── app/
│   ├── main.py        # Route definitions and app entry point
│   ├── models.py      # SQLAlchemy User model + Pydantic Note models
│   ├── schemas.py     # Pydantic schemas (UserCreate, UserOut, Token, etc.)
│   ├── database.py    # PostgreSQL and MongoDB connection setup
│   └── auth.py        # Password hashing, JWT creation/decoding
├── alembic/           # Database migration files
├── requirements.txt
└── .env.example
```

## Setup

### 1. Clone and create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in your values:

```env
APP_NAME=FastAPI Application
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/mydatabase
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=mydatabase
```

### 3. Run database migrations

```bash
alembic upgrade head
```

### 4. Start the server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`. Interactive docs:
`http://localhost:8000/docs`

## API Endpoints

### Health

| Method | Path    | Description  |
| ------ | ------- | ------------ |
| GET    | `/ping` | Health check |

### Authentication

| Method | Path           | Description                                  |
| ------ | -------------- | -------------------------------------------- |
| POST   | `/auth/signup` | Register a new user                          |
| POST   | `/auth/login`  | Login and receive a JWT token                |
| GET    | `/profile`     | Get the current authenticated user's profile |

### Users

| Method | Path               | Description      |
| ------ | ------------------ | ---------------- |
| GET    | `/users`           | List all users   |
| GET    | `/users/{user_id}` | Get a user by ID |
| PUT    | `/users/{user_id}` | Update a user    |
| DELETE | `/users/{user_id}` | Delete a user    |

### Notes

| Method | Path               | Description                   |
| ------ | ------------------ | ----------------------------- |
| POST   | `/notes`           | Create a note                 |
| GET    | `/notes`           | List all notes (newest first) |
| GET    | `/notes/{note_id}` | Get a note by ID              |
| PUT    | `/notes/{note_id}` | Update a note                 |

## Authentication Flow

1. Register via `POST /auth/signup` with `email`, `username`, and `password`.
2. Login via `POST /auth/login` (OAuth2 password form) to receive a Bearer
   token.
3. Include the token in the `Authorization` header for protected routes:
   ```
   Authorization: Bearer <token>
   ```
