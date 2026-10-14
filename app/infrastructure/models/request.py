from decimal import Decimal
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class AgentRequest(Base):
    __tablename__ = "requests"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False, index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id"), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    latency: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    input_tokens: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    output_tokens: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    estimated_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
