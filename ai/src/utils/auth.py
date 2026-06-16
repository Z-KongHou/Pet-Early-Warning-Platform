"""Per-request token context — stores the raw Authorization header so
downstream clients can forward it to the backend for JWT validation.

The Python side never parses JWT; the backend is the single authority.
"""

from __future__ import annotations

import contextvars

_current_token: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_token", default=None
)


def set_current_token(authorization: str | None) -> None:
    """Store the raw Authorization header value (e.g. 'Bearer eyJ...') for this request."""
    _current_token.set(authorization)


def get_current_token() -> str | None:
    return _current_token.get()
