import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.infrastructure.database import engine

logger = logging.getLogger("aegistwin.health")


def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except SQLAlchemyError:
        logger.exception("Database health check failed")

        return {
            "status": "unhealthy",
            "database": "disconnected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


if __name__ == "__main__":
    print(database_health())
