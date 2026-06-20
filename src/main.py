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
# Keep legacy admin user management routes available under accounts for compatibility
app.include_router(admin_router, prefix="/api/v1/accounts", tags=["Accounts"])


@app.get("/api/health", response_model=StatusResponse)
async def health_check():
    return StatusResponse(status="ok")
