from fastapi import FastAPI

from src.accounts.routers import router as accounts_router
from src.admin.routers import router as admin_router
from src.cart.routers import router as cart_router
from src.config import settings
from src.general_schemas import StatusResponse
from src.movies.genres_routers import router as genres_router
from src.movies.routers import router as movies_router
from src.orders.routers import router as orders_router

app = FastAPI(
    title=settings.APP_TITLE,
    description=(
        "REST API for an online cinema platform.\n\n"
        "## Features\n"
        "- **Accounts** — registration, activation, login/logout, JWT token refresh, "
        "password change & reset, profile management\n"
        "- **Movies** — browse, search, sort, CRUD (moderator+), comments, ratings, "
        "likes, favorites\n"
        "- **Genres** — list, CRUD (moderator+), movies-by-genre\n"
        "- **Cart** — add / remove / clear items, purchased-movie guard\n"
        "- **Orders** — create from cart, pay, cancel, admin overview\n"
        "- **Admin** — change user roles, manual activation\n\n"
        "## Authentication\n"
        "Most endpoints require a **Bearer JWT** token in the `Authorization` header. "
        "Obtain one via the `/api/v1/accounts/login` endpoint."
    ),
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Routers are registered here as implemented
app.include_router(accounts_router, prefix="/api/v1/accounts", tags=["Accounts"])
app.include_router(movies_router, prefix="/api/v1/movies", tags=["Movies"])
app.include_router(genres_router, prefix="/api/v1/genres", tags=["Genres"])
app.include_router(cart_router, prefix="/api/v1/cart", tags=["Cart"])
app.include_router(orders_router, prefix="/api/v1/orders", tags=["Orders"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin"])


@app.get(
    "/api/health",
    response_model=StatusResponse,
    tags=["Health"],
    summary="Health check",
    description="Simple liveness probe. Returns `{\"status\": \"ok\"}` when the service is running.",
)
async def health_check():
    return StatusResponse(status="ok")
