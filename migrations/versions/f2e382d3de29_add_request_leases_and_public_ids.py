
"""Add request leases, heartbeat tracking, and public request IDs.

Revision ID: f2e382d3de29
Revises: 0fa7fd0d9559
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Alembic revision identifiers
revision: str = "f2e382d3de29"
down_revision: Union[str, Sequence[str], None] = "0fa7fd0d9559"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add request reliability and recovery fields."""

    # Client-facing request identifier (e.g. REQ-...)
    op.add_column(
        "requests",
        sa.Column(
            "public_request_id",
            sa.String(length=100),
            nullable=True,
        ),
    )

    # Current worker holding the request lease
    op.add_column(
        "requests",
        sa.Column(
            "lease_owner_id",
            sa.String(length=255),
            nullable=True,
        ),
    )

    # Unique token used to validate lease ownership
    op.add_column(
        "requests",
        sa.Column(
            "lease_token",
            sa.String(length=64),
            nullable=True,
        ),
    )

    # UTC timestamp when the worker lease expires
    op.add_column(
        "requests",
        sa.Column(
            "lease_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # UTC timestamp of the last successful heartbeat
    op.add_column(
        "requests",
        sa.Column(
            "last_heartbeat_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Public request IDs must be unique within a tenant
    op.create_unique_constraint(
        "uq_requests_tenant_public_request_id",
        "requests",
        ["tenant_id", "public_request_id"],
    )

    # Speed up tenant-scoped expired request recovery
    op.create_index(
        "ix_requests_tenant_status_lease_expiry",
        "requests",
        ["tenant_id", "status", "lease_expires_at"],
    )


def downgrade() -> None:
    """Remove request reliability and recovery fields."""

    op.drop_index(
        "ix_requests_tenant_status_lease_expiry",
        table_name="requests",
    )

    op.drop_constraint(
        "uq_requests_tenant_public_request_id",
        "requests",
        type_="unique",
    )

    op.drop_column("requests", "last_heartbeat_at")
    op.drop_column("requests", "lease_expires_at")
    op.drop_column("requests", "lease_token")
    op.drop_column("requests", "lease_owner_id")
    op.drop_column("requests", "public_request_id")
