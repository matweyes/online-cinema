from fastapi import FastAPI

from src.accounts.routers import router as accounts_router
from src.config import settings
from src.movies.routers import router as movies_router

app = FastAPI(
    title=settings.APP_TITLE,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Routers are registered here as implemented
app.include_router(accounts_router, prefix="/api/v1/accounts", tags=["Accounts"])
app.include_router(movies_router, prefix="/api/v1/movies", tags=["Movies"])
# app.include_router(cart_router, prefix="/api/v1/cart", tags=["Cart"])
# app.include_router(orders_router, prefix="/api/v1/orders", tags=["Orders"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
