# Online Cinema API

REST API for an online cinema platform: movie catalog, authentication, shopping cart, and orders.

## Technologies

* Python 3.11, FastAPI, SQLAlchemy 2.0 (async), SQLite
* JWT authentication, Celery + Redis
* Docker, Poetry, pytest

## Quick Start

### Local Setup

```bash
poetry install
cp .env.example .env
alembic upgrade head
uvicorn src.main:app --reload
```

### Docker

```bash
docker compose up --build
```

## API Documentation

* Swagger UI: http://localhost:8000/api/docs
* ReDoc: http://localhost:8000/api/redoc

## Tests

```bash
pytest --cov=src
```

## Project Structure

*(module descriptions)*

## Features

* User registration, account activation, JWT authentication, password reset
* Movie catalog with filtering, search, sorting, and pagination
* Comments, ratings, likes, and favorites
* Shopping cart
* Order management
* Roles: User, Moderator, Admin
