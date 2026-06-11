from fastapi import FastAPI
from src.config import settings

app = FastAPI(
    title=settings.APP_TITLE,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Роутеры подключаются здесь по мере реализации:
# app.include_router(accounts_router, prefix="/api/v1/accounts", tags=["Accounts"])
# app.include_router(movies_router, prefix="/api/v1/movies", tags=["Movies"])
# app.include_router(cart_router, prefix="/api/v1/cart", tags=["Cart"])
# app.include_router(orders_router, prefix="/api/v1/orders", tags=["Orders"])

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
