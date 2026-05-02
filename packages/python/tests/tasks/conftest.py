"""Re-export the auth-package fixtures for task-route auth tests.

`tests/tasks/test_route_authorization.py` needs an isolated DB +
PAYLOAD_KEY + a seeded operator — same setup the auth tests use.
Pytest's fixture discovery is per-package, so we re-import the
fixtures here rather than duplicate the body.
"""

from __future__ import annotations

from tests.auth.conftest import (  # noqa: F401 — fixture re-export
    _isolated_db,
    _payload_key,
    _reset_rate_limit,
    operator_user,
)
