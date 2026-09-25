"""Error taxonomy shared by every layer of the runtime.

Each failure mode that a caller can act on gets its own type.  The console
layer maps ``http_status`` onto a response code and the audit layer records
``code`` so that a rejection is explainable after the fact.
"""

from __future__ import annotations

from typing import Any


class LineControlError(Exception):
    """Base class for every error raised by the runtime."""

    code = "line_control_error"
    http_status = 400

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, Any] = dict(context)

    def as_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "context": dict(self.context),
        }


class ValidationError(LineControlError):
    """A caller supplied a value that cannot be interpreted."""

    code = "validation_error"


class OrderViolationError(LineControlError):
    """A stage was requested out of the declared sequence."""

    code = "order_violation"
    http_status = 409


class NotDurableError(LineControlError):
    """A prerequisite state was never written durably."""

    code = "not_durable"
    http_status = 409


class InterlockBlockedError(LineControlError):
    """An interlock or latch currently forbids the action."""

    code = "interlock_blocked"
    http_status = 409


class ArtifactExpiredError(LineControlError):
    """A confirmation, snapshot or baseline is past its validity window."""

    code = "artifact_expired"
    http_status = 409


class StaleGenerationError(LineControlError):
    """An artifact belongs to an older generation than the current one."""

    code = "stale_generation"
    http_status = 409


class OverLimitError(LineControlError):
    """A measured value crossed a configured bound."""

    code = "over_limit"
    http_status = 409


class BelowLimitError(OverLimitError):
    """A measured value dropped under a configured bound."""

    code = "below_limit"


class DuplicateError(LineControlError):
    """An identity that must stay unique was reused."""

    code = "duplicate"
    http_status = 409


class RecordError(LineControlError):
    """The record stream was used in a way its invariants forbid."""

    code = "record_error"


class UnknownRecordError(RecordError):
    """A tombstone referenced a sequence that does not exist."""

    code = "unknown_record"
    http_status = 404


class NotFoundError(LineControlError):
    """A requested resource does not exist."""

    code = "not_found"
    http_status = 404


class MethodNotAllowedError(LineControlError):
    """The path exists but not for this verb."""

    code = "method_not_allowed"
    http_status = 405


class RestoreError(LineControlError):
    """Restart could not build a state that satisfies the watermark rules."""

    code = "restore_error"
    http_status = 500


ERROR_STATUS: dict[str, int] = {
    ValidationError.code: ValidationError.http_status,
    OrderViolationError.code: OrderViolationError.http_status,
    NotDurableError.code: NotDurableError.http_status,
    InterlockBlockedError.code: InterlockBlockedError.http_status,
    ArtifactExpiredError.code: ArtifactExpiredError.http_status,
    StaleGenerationError.code: StaleGenerationError.http_status,
    OverLimitError.code: OverLimitError.http_status,
    BelowLimitError.code: BelowLimitError.http_status,
    DuplicateError.code: DuplicateError.http_status,
    RecordError.code: RecordError.http_status,
    UnknownRecordError.code: UnknownRecordError.http_status,
    NotFoundError.code: NotFoundError.http_status,
    MethodNotAllowedError.code: MethodNotAllowedError.http_status,
    RestoreError.code: RestoreError.http_status,
}


def status_for(error: LineControlError) -> int:
    """Return the response status that belongs to ``error``."""

    return ERROR_STATUS.get(error.code, error.http_status)
