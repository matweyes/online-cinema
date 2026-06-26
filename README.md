# Online Cinema API

REST API backend for an online cinema platform — movie catalog, user accounts with JWT authentication, shopping cart, orders, and admin panel.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Setup](#local-setup)
  - [Docker](#docker)
- [Environment Variables](#environment-variables)
- [Database Migrations](#database-migrations)
- [API Documentation](#api-documentation)
- [API Endpoints](#api-endpoints)
  - [Health](#health)
  - [Accounts](#accounts)
  - [Movies](#movies)
  - [Genres](#genres)
  - [Cart](#cart)
  - [Orders](#orders)
  - [Admin](#admin)
- [Authentication](#authentication)
- [Roles & Permissions](#roles--permissions)
- [Background Tasks](#background-tasks)
- [Testing](#testing)
- [Linting & Type Checking](#linting--type-checking)
- [CI/CD](#cicd)

---

## Features

- **User Accounts** — registration with email, account activation via token, login/logout, JWT access & refresh tokens, password change and reset
- **Movie Catalog** — browse, search by name/description, sort by price/year/meta_score, pagination
- **Movie CRUD** — create, update, delete movies (moderator+ only)
- **Genres** — list with movie counts, CRUD (moderator+), filter movies by genre
- **Comments** — threaded comments on movies (with parent/reply support)
- **Ratings** — rate movies on a 1–10 scale
- **Likes & Favorites** — like comments, add/remove movies from favorites
- **Shopping Cart** — add/remove/clear items, purchased-movie guard (can't re-add bought movies)
- **Orders** — create from cart, pay, cancel; admin can view all orders with filters
- **Purchase Records** — tracks which movies a user has bought
- **Admin Panel** — change user roles, manually activate accounts
- **User Profiles** — first/last name, avatar, gender, date of birth, bio
- **Background Tasks** — Celery + Redis for periodic cleanup of expired tokens
- **Role-Based Access** — User, Moderator, Admin with endpoint-level enforcement

---

## Tech Stack

| Layer              | Technology                                      |
| ------------------ | ----------------------------------------------- |
| **Framework**      | FastAPI 0.115                                   |
| **Language**       | Python 3.11+                                    |
| **ORM**            | SQLAlchemy 2.0 (async) + aiosqlite              |
| **Database**       | SQLite (easily swappable)                        |
| **Migrations**     | Alembic                                         |
| **Auth**           | JWT (python-jose) + bcrypt (passlib)             |
| **Validation**     | Pydantic v2 + pydantic-settings                 |
| **Task Queue**     | Celery 5 with Redis broker                      |
| **Email**          | fastapi-mail (SMTP)                             |
| **HTTP Client**    | httpx                                           |
| **Dependency Mgmt**| Poetry                                          |
| **Containerization**| Docker + Docker Compose                        |
| **Testing**        | pytest + pytest-asyncio + pytest-cov + factory-boy |
| **Linting**        | Ruff                                            |
| **Type Checking**  | mypy (with Pydantic & SQLAlchemy plugins)        |

---

## Project Structure

```
online-cinema/
├── src/
│   ├── main.py              # FastAPI app entry point, router registration
│   ├── config.py             # Settings (pydantic-settings, reads .env)
│   ├── database.py           # Async engine, session factory, Base
│   ├── general_schemas.py    # Shared Pydantic schemas (StatusResponse)
│   ├── accounts/
│   │   ├── enums.py          # UserGroupEnum, GenderEnum
│   │   ├── models.py         # User, UserProfile, UserGroup, tokens
│   │   ├── routers.py        # Auth & profile endpoints
│   │   ├── schemas.py        # Request/response schemas
│   │   └── helpers.py        # JWT utils, password hashing, dependencies
│   ├── movies/
│   │   ├── models.py         # Movie, Genre, Star, Director, Comment, pivots
│   │   ├── routers.py        # Movie CRUD, comments, ratings, likes, favorites
│   │   ├── genres_routers.py # Genre CRUD, movies-by-genre
│   │   ├── schemas.py        # Movie/Genre/Comment schemas
│   │   └── helpers.py        # Moderator guard dependency
│   ├── cart/
│   │   ├── models.py         # Cart, CartItem, Purchase
│   │   ├── routers.py        # Cart operations
│   │   └── schemas.py        # Cart schemas
│   ├── orders/
│   │   ├── models.py         # Order, OrderItem, OrderStatusEnum
│   │   ├── routers.py        # Order lifecycle endpoints
│   │   ├── schemas.py        # Order schemas
│   │   └── helpers.py        # Order access dependency
│   ├── admin/
│   │   └── routers.py        # Role management, manual activation
│   └── tasks/
│       └── __init__.py       # Celery app, periodic token cleanup task
├── tests/
│   ├── conftest.py           # Fixtures: async DB, test client, users
│   ├── test_accounts.py      # Auth & profile tests
│   ├── test_movies.py        # Movie CRUD tests
│   ├── test_genres.py        # Genre tests
│   ├── test_cart.py          # Cart tests
│   ├── test_orders.py        # Order tests
│   ├── test_admin.py         # Admin tests
│   └── test_health.py        # Health check test
├── alembic/                  # Database migrations
├── .github/workflows/ci.yml  # GitHub Actions CI pipeline
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **Poetry** — [install guide](https://python-poetry.org/docs/#installation)
- **Docker & Docker Compose** (optional, for containerized setup)
- **Redis** (required for Celery; included in Docker Compose)

### Local Setup

```bash
# 1. Clone the repository
git clone <repo-url> && cd online-cinema

# 2. Install dependencies
poetry install

# 3. Configure environment
cp .env.example .env
# Edit .env with your settings (see Environment Variables below)

# 4. Run database migrations
poetry run alembic upgrade head

# 5. Start the server
poetry run uvicorn src.main:app --reload
```

The API will be available at `http://localhost:8000`.

### Docker

```bash
# Build and start all services (web, redis, celery worker, celery beat)
docker compose up --build
```

Services started by Docker Compose:

| Service            | Container            | Port  |
| ------------------ | -------------------- | ----- |
| **Web (FastAPI)**  | `cinema-web`         | 8000  |
| **Redis**          | `cinema-redis`       | 6379  |
| **Celery Worker**  | `cinema-celery-worker` | —   |
| **Celery Beat**    | `cinema-celery-beat`   | —   |

---

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed:

| Variable          | Default                                | Description                          |
| ----------------- | -------------------------------------- | ------------------------------------ |
| `DATABASE_URL`    | `sqlite+aiosqlite:///./data/cinema.db` | Async database connection string     |
| `SECRET_KEY`      | `your-secret-key-change-me`            | JWT signing key (**change in prod**) |
| `REDIS_URL`       | `redis://redis:6379/0`                 | Redis broker URL for Celery          |
| `MAIL_USERNAME`   | *(empty)*                              | SMTP username                        |
| `MAIL_PASSWORD`   | *(empty)*                              | SMTP password                        |
| `MAIL_FROM`       | `noreply@cinema.local`                 | Sender email address                 |
| `MAIL_SERVER`     | `smtp.gmail.com`                       | SMTP server host                     |
| `MAIL_PORT`       | `587`                                  | SMTP server port                     |

Additional settings with defaults (configurable via env vars):

| Variable                          | Default | Description                        |
| --------------------------------- | ------- | ---------------------------------- |
| `ACCESS_TOKEN_EXPIRE_MINUTES`     | `30`    | JWT access token lifetime          |
| `REFRESH_TOKEN_EXPIRE_DAYS`       | `7`     | Refresh token lifetime             |
| `ACTIVATION_TOKEN_EXPIRE_HOURS`   | `24`    | Account activation token lifetime  |
| `PASSWORD_RESET_TOKEN_EXPIRE_HOURS` | `1`  | Password reset token lifetime      |

---

## Database Migrations

```bash
# Apply all migrations
poetry run alembic upgrade head

# Create a new migration after model changes
poetry run alembic revision --autogenerate -m "description"

# Downgrade one step
poetry run alembic downgrade -1
```

---

## API Documentation

Interactive docs are available when the server is running:

- **Swagger UI** — [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
- **ReDoc** — [http://localhost:8000/api/redoc](http://localhost:8000/api/redoc)
- **OpenAPI JSON** — [http://localhost:8000/api/openapi.json](http://localhost:8000/api/openapi.json)

---

## API Endpoints

### Health

| Method | Endpoint      | Description    | Auth |
| ------ | ------------- | -------------- | ---- |
| GET    | `/api/health` | Liveness probe | No   |

### Accounts

| Method | Endpoint                        | Description                | Auth     |
| ------ | ------------------------------- | -------------------------- | -------- |
| POST   | `/api/v1/accounts/register`     | Register a new user        | No       |
| POST   | `/api/v1/accounts/activation`   | Activate account via token | No       |
| POST   | `/api/v1/accounts/activation/resend` | Resend activation token | No  |
| POST   | `/api/v1/accounts/login`        | Log in (get tokens)        | No       |
| POST   | `/api/v1/accounts/logout`       | Invalidate refresh token   | Bearer   |
| POST   | `/api/v1/accounts/refresh`      | Refresh access token       | No       |
| PATCH  | `/api/v1/accounts/change-password` | Change password         | Bearer   |
| POST   | `/api/v1/accounts/forgot-password` | Request password reset  | No       |
| POST   | `/api/v1/accounts/reset-password`  | Reset password with token | No     |
| GET    | `/api/v1/accounts/me`           | Get current user info      | Bearer   |
| PATCH  | `/api/v1/accounts/me/profile`   | Update user profile        | Bearer   |

### Movies

| Method | Endpoint                                       | Description             | Auth       |
| ------ | ---------------------------------------------- | ----------------------- | ---------- |
| GET    | `/api/v1/movies/`                              | List movies (paginated) | No         |
| GET    | `/api/v1/movies/{movie_id}`                    | Get movie details       | No         |
| POST   | `/api/v1/movies/`                              | Create movie            | Moderator+ |
| PATCH  | `/api/v1/movies/{movie_id}`                    | Update movie            | Moderator+ |
| DELETE | `/api/v1/movies/{movie_id}`                    | Delete movie            | Moderator+ |
| GET    | `/api/v1/movies/{movie_id}/comments`           | List comments           | No         |
| POST   | `/api/v1/movies/{movie_id}/comments`           | Post a comment          | Bearer     |
| POST   | `/api/v1/movies/{movie_id}/comments/{id}/likes`| Like a comment          | Bearer     |
| POST   | `/api/v1/movies/{movie_id}/rate`               | Rate a movie (1–10)     | Bearer     |
| POST   | `/api/v1/movies/{movie_id}/likes`              | Like a movie            | Bearer     |
| GET    | `/api/v1/movies/favorites`                     | List favorites          | Bearer     |
| POST   | `/api/v1/movies/{movie_id}/favorites`          | Add to favorites        | Bearer     |
| DELETE | `/api/v1/movies/{movie_id}/favorites`          | Remove from favorites   | Bearer     |

### Genres

| Method | Endpoint                          | Description           | Auth       |
| ------ | --------------------------------- | --------------------- | ---------- |
| GET    | `/api/v1/genres/`                 | List all genres       | No         |
| GET    | `/api/v1/genres/{genre_id}/movies`| Movies by genre       | No         |
| POST   | `/api/v1/genres/`                 | Create genre          | Moderator+ |
| PATCH  | `/api/v1/genres/{genre_id}`       | Update genre          | Moderator+ |
| DELETE | `/api/v1/genres/{genre_id}`       | Delete genre          | Moderator+ |

### Cart

| Method | Endpoint                         | Description               | Auth   |
| ------ | -------------------------------- | ------------------------- | ------ |
| GET    | `/api/v1/cart/`                  | View cart                 | Bearer |
| POST   | `/api/v1/cart/items`             | Add movie to cart         | Bearer |
| DELETE | `/api/v1/cart/items/{movie_id}`  | Remove movie from cart    | Bearer |
| DELETE | `/api/v1/cart/items`             | Clear entire cart         | Bearer |

### Orders

| Method | Endpoint                          | Description                | Auth   |
| ------ | --------------------------------- | -------------------------- | ------ |
| POST   | `/api/v1/orders/`                 | Create order from cart     | Bearer |
| GET    | `/api/v1/orders/`                 | List my orders             | Bearer |
| GET    | `/api/v1/orders/{order_id}`       | Get order details          | Bearer |
| POST   | `/api/v1/orders/{order_id}/pay`   | Pay for order              | Bearer |
| POST   | `/api/v1/orders/{order_id}/cancel`| Cancel order               | Bearer |
| GET    | `/api/v1/orders/admin/all`        | List all orders (filtered) | Admin  |

### Admin

| Method | Endpoint                                 | Description              | Auth  |
| ------ | ---------------------------------------- | ------------------------ | ----- |
| PATCH  | `/api/v1/admin/users/{user_id}/group`    | Change user role         | Admin |
| PATCH  | `/api/v1/admin/users/{user_id}/activation`| Manually activate user  | Admin |

---

## Authentication

The API uses **JWT Bearer tokens**:

1. Register via `POST /api/v1/accounts/register` → receive an activation token
2. Activate via `POST /api/v1/accounts/activation`
3. Log in via `POST /api/v1/accounts/login` → receive `access_token` + `refresh_token`
4. Include the access token in requests: `Authorization: Bearer <access_token>`
5. Refresh via `POST /api/v1/accounts/refresh` when the access token expires

**Password requirements**: 8–128 characters, must include uppercase, lowercase, digit, and special character. No spaces.

---

## Roles & Permissions

| Role          | Capabilities                                                                 |
| ------------- | ---------------------------------------------------------------------------- |
| **User**      | Browse movies, manage cart & orders, comment, rate, like, manage own profile  |
| **Moderator** | All User permissions + create/update/delete movies and genres                 |
| **Admin**     | All Moderator permissions + manage user roles, manual activation, view all orders |

---

## Background Tasks

**Celery** with **Redis** as the message broker handles periodic tasks:

- **Token Cleanup** — runs every 60 seconds, deletes expired activation tokens, password reset tokens, and refresh tokens from the database

The Celery worker and beat scheduler are configured in `docker-compose.yml` and start automatically with `docker compose up`.

---

## Testing

```bash
# Run all tests with coverage
poetry run pytest --cov=src

# Run with coverage report in XML (used by CI)
poetry run pytest --cov=src --cov-report=xml

# Run a specific test file
poetry run pytest tests/test_movies.py -v
```

Test suite covers: accounts, movies, genres, cart, orders, admin, and health check.
Tests use an in-memory SQLite database and async test client via `httpx`.

---

## Linting & Type Checking

```bash
# Lint with Ruff
poetry run ruff check src/ tests/

# Auto-fix lint issues
poetry run ruff check src/ tests/ --fix

# Type check with mypy
poetry run mypy src/
```

Ruff is configured with rules: `E`, `F`, `I`, `N`, `W`, `UP`, `B`, `SIM` (targeting Python 3.11, line length 88).

---

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`) runs on pushes to `main` and pull requests targeting `main`:

1. **Lint** — Ruff + mypy (matrix: Python 3.11 & 3.12)
2. **Test** — pytest with coverage (Python 3.12, runs after lint passes)
3. **Artifact** — uploads `coverage.xml` as a build artifact
