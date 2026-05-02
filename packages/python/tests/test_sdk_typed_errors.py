"""Cross-language error parity for the Python SDK.

Each error class mirrors a TypeScript SDK class one-for-one (see
packages/typescript-sdk/src/errors.ts). This file pins:

  - The codes match what the TS SDK emits — string codes are the
    wire contract; users `except TaskNotFoundError as e` AND check
    `e.code == "TASK_NOT_FOUND"` interchangeably.
  - Each new class is importable from the package root, so SDK users
    don't have to reach into `awaithumans.errors` for the typed catch.

CLAUDE.md §7 makes cross-language code parity a hard rule. A
regression that drifts the codes apart should fail this test file
before shipping."""

from __future__ import annotations

from awaithumans import (
    AwaitHumansError,
    PollError,
    ServerUnreachableError,
    TaskCancelledError,
    TaskCreateError,
    TaskNotFoundError,
)


def test_task_not_found_code_and_inheritance() -> None:
    err = TaskNotFoundError("task-123")
    assert err.code == "TASK_NOT_FOUND"
    assert "task-123" in str(err)
    assert isinstance(err, AwaitHumansError)


def test_task_cancelled_code_and_inheritance() -> None:
    err = TaskCancelledError("Approve refund")
    assert err.code == "TASK_CANCELLED"
    assert "Approve refund" in str(err)
    assert isinstance(err, AwaitHumansError)


def test_task_create_error_truncates_long_body() -> None:
    long_body = "x" * 5000
    err = TaskCreateError(503, long_body)
    assert err.code == "TASK_CREATE_FAILED"
    # Body cap mirrors the TS SDK's 500-char slice — important so
    # huge HTML 502 pages from misconfigured proxies don't blow up
    # the user's terminal.
    assert err.hint.count("x") <= 500


def test_poll_error_includes_task_id() -> None:
    err = PollError("task-abc", 502, "Bad Gateway")
    assert err.code == "POLL_FAILED"
    assert "task-abc" in str(err)
    assert "Bad Gateway" in err.hint


def test_server_unreachable_includes_url_and_cause() -> None:
    err = ServerUnreachableError("http://localhost:3001", ConnectionRefusedError(61))
    assert err.code == "SERVER_UNREACHABLE"
    assert "http://localhost:3001" in str(err)
    # The cause's repr should be visible so the user can debug.
    assert "61" in err.hint or "ConnectionRefused" in err.hint


def test_all_classes_importable_from_package_root() -> None:
    """Sanity check: typed errors are part of the public surface."""
    import awaithumans

    for name in (
        "TaskNotFoundError",
        "TaskCancelledError",
        "TaskCreateError",
        "PollError",
        "ServerUnreachableError",
    ):
        assert hasattr(awaithumans, name), f"{name} missing from package root"
