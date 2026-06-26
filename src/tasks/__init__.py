"""Celery application and periodic tasks."""

import logging
from datetime import UTC, datetime

from celery import Celery
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from src.config import settings

# Replace async driver with sync equivalent for Celery workers
_sync_url = settings.DATABASE_URL.replace("+aiosqlite", "").replace("+asyncpg", "")
sync_engine = create_engine(_sync_url, echo=False)

celery_app = Celery("cinema", broker=settings.REDIS_URL)
celery_app.conf.beat_schedule = {
    "cleanup-expired-tokens": {
        "task": "src.tasks.cleanup_expired_tokens",
        "schedule": 60.0,  # every 60 seconds
    },
}
celery_app.conf.timezone = "UTC"

logger = logging.getLogger(__name__)
logger.info(
    "Celery app initialized with broker %s and database %s",
    settings.REDIS_URL,
    _sync_url,
)


@celery_app.task
def cleanup_expired_tokens() -> dict[str, int]:
    """Delete expired activation, password-reset, and refresh tokens."""
    from src.accounts.models import ActivationToken, PasswordResetToken, RefreshToken

    now = datetime.now(UTC)
    logger.info("Starting expired token cleanup at %s", now.isoformat())
    counts: dict[str, int] = {}

    with Session(sync_engine) as session:
        r = session.execute(
            delete(ActivationToken).where(ActivationToken.expires_at < now)
        )
        counts["activation_tokens"] = r.rowcount  # type: ignore[attr-defined]

        r = session.execute(
            delete(PasswordResetToken).where(PasswordResetToken.expires_at < now)
        )
        counts["password_reset_tokens"] = r.rowcount  # type: ignore[attr-defined]

        r = session.execute(delete(RefreshToken).where(RefreshToken.expires_at < now))
        counts["refresh_tokens"] = r.rowcount  # type: ignore[attr-defined]

        session.commit()

    total = sum(counts.values())
    logger.info(
        "Token cleanup finished: %d removed "
        "(activation=%d, password_reset=%d, refresh=%d)",
        total,
        counts["activation_tokens"],
        counts["password_reset_tokens"],
        counts["refresh_tokens"],
    )
    return counts
