"""In-memory approval workflow for policy-gated tool calls."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable

from app.contracts import DecisionAction, PolicyDecision, ToolCall
from app.store import InMemoryStore


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"


@dataclass
class ApprovalRequest:
    approval_id: str
    call: ToolCall
    created_at: datetime
    expires_at: datetime
    status: ApprovalStatus = ApprovalStatus.PENDING


class ApprovalManager:
    """Create and consume one-use approvals for REQUIRE_APPROVAL decisions."""

    def __init__(
        self,
        store: InMemoryStore | None = None,
        *,
        ttl: timedelta = timedelta(minutes=5),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if ttl <= timedelta(0):
            raise ValueError("Approval TTL must be greater than zero.")
        self.store = store or InMemoryStore()
        self.ttl = ttl
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._next_id = 1

    def create_pending(
        self,
        call: ToolCall,
        decision: PolicyDecision,
        *,
        expires_at: datetime | None = None,
    ) -> ApprovalRequest:
        if decision.action != DecisionAction.REQUIRE_APPROVAL:
            raise ValueError("An approval can only be created for a REQUIRE_APPROVAL decision.")
        if decision.call_id != call.call_id:
            raise ValueError("The approval decision must refer to the supplied tool call.")

        created_at = self._now()
        expiry = expires_at or created_at + self.ttl
        self._validate_aware(expiry)
        if expiry <= created_at:
            raise ValueError("Approval expiration must be in the future.")

        while True:
            approval_id = f"APR-{self._next_id:06d}"
            self._next_id += 1
            if approval_id not in self.store.approvals:
                break

        request = ApprovalRequest(
            approval_id=approval_id,
            call=call,
            created_at=created_at,
            expires_at=expiry,
        )
        self.store.approvals[approval_id] = request
        return request

    def get_approval(self, approval_id: str) -> ApprovalRequest | None:
        request = self.store.approvals.get(approval_id)
        return request if isinstance(request, ApprovalRequest) else None

    def approve(self, approval_id: str, *, now: datetime | None = None) -> bool:
        request = self.get_approval(approval_id)
        if request is None or not self._is_pending_and_unexpired(request, now):
            return False
        request.status = ApprovalStatus.APPROVED
        return True

    def deny(self, approval_id: str, *, now: datetime | None = None) -> bool:
        request = self.get_approval(approval_id)
        if request is None or not self._is_pending_and_unexpired(request, now):
            return False
        request.status = ApprovalStatus.DENIED
        return True

    def authorize(
        self,
        approval_id: str,
        call: ToolCall,
        *,
        now: datetime | None = None,
    ) -> bool:
        request = self.get_approval(approval_id)
        if request is None:
            return False
        if request.status == ApprovalStatus.APPROVED and self._is_expired(request, now):
            request.status = ApprovalStatus.EXPIRED
            return False
        if request.status != ApprovalStatus.APPROVED or request.call != call:
            return False

        request.status = ApprovalStatus.CONSUMED
        return True

    def _is_pending_and_unexpired(
        self, request: ApprovalRequest, now: datetime | None
    ) -> bool:
        if request.status != ApprovalStatus.PENDING:
            return False
        if self._is_expired(request, now):
            request.status = ApprovalStatus.EXPIRED
            return False
        return True

    def _is_expired(self, request: ApprovalRequest, now: datetime | None) -> bool:
        current_time = self._now(now)
        return current_time >= request.expires_at

    def _now(self, value: datetime | None = None) -> datetime:
        current_time = value if value is not None else self._clock()
        self._validate_aware(current_time)
        return current_time

    @staticmethod
    def _validate_aware(value: datetime) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Approval timestamps must be timezone-aware.")