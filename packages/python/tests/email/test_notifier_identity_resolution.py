"""Solo-identity fallback in the email notifier.

Covers the UX shortcut introduced so dashboard-configured operators don't
silently lose sends when their code follows the quickstart `email:` form.
The precedence under test is documented on `_resolve_identity`:

  1. explicit `email+<id>:...` → that identity (or None + warn if missing)
  2. bare `email:...` + env transport set → None (caller uses env)
  3. bare `email:...` + env unset + 1 identity in DB → that identity
  4. bare `email:...` + env unset + >1 identity → None (skip + warn)
"""

from __future__ import annotations

import pytest

from awaithumans.server.channels.email.notifier import _resolve_identity
from awaithumans.server.core.config import settings
from awaithumans.server.services.email_identity_service import (
    identity_config,
    upsert_identity,
)


@pytest.fixture(autouse=True)
def _clear_email_transport() -> None:
    """Most cases want the env transport unset — set per-test when needed."""
    original = settings.EMAIL_TRANSPORT
    settings.EMAIL_TRANSPORT = None
    yield
    settings.EMAIL_TRANSPORT = original


@pytest.mark.asyncio
async def test_explicit_identity_id_resolves_directly(session) -> None:
    await upsert_identity(
        session,
        identity_id="acme",
        display_name="Acme",
        from_email="a@acme.com",
        transport="noop",
        transport_config={"flag": "explicit"},
    )
    row = await _resolve_identity(session, "acme")
    assert row is not None
    assert row.id == "acme"
    # transport_config is loaded (not deferred) so callers can build a transport.
    assert identity_config(row) == {"flag": "explicit"}


@pytest.mark.asyncio
async def test_explicit_identity_id_missing_returns_none(session) -> None:
    """Operator typed a bad slug — we don't silently fall through to the
    solo fallback (that would mask config errors). Return None, log."""
    await upsert_identity(
        session,
        identity_id="only-one",
        display_name="Only",
        from_email="o@x.com",
        transport="noop",
        transport_config={},
    )
    assert await _resolve_identity(session, "does-not-exist") is None


@pytest.mark.asyncio
async def test_bare_email_with_env_transport_uses_env(session) -> None:
    """When AWAITHUMANS_EMAIL_TRANSPORT is set, bare `email:` defers to
    env-derived config. The solo fallback must not override an explicit
    operator-configured env default."""
    settings.EMAIL_TRANSPORT = "noop"
    await upsert_identity(
        session,
        identity_id="solo",
        display_name="Solo",
        from_email="s@x.com",
        transport="noop",
        transport_config={},
    )
    assert await _resolve_identity(session, None) is None


@pytest.mark.asyncio
async def test_bare_email_with_solo_identity_resolves_to_it(session) -> None:
    """The UX fix: dashboard-only setup + docs quickstart code path."""
    await upsert_identity(
        session,
        identity_id="awaithumans",
        display_name="AwaitHumans",
        from_email="hello@awaithumans.dev",
        transport="noop",
        transport_config={"k": "v"},
    )
    row = await _resolve_identity(session, None)
    assert row is not None
    assert row.id == "awaithumans"
    # Re-fetched via get_identity, so transport_config is loaded
    # (list_identities defers it; that's intentional).
    assert identity_config(row) == {"k": "v"}


@pytest.mark.asyncio
async def test_bare_email_with_multiple_identities_skips(session) -> None:
    """When >1 identity is configured and no env default is set, bare
    `email:` is ambiguous — we don't pick arbitrarily."""
    for i in range(2):
        await upsert_identity(
            session,
            identity_id=f"team-{i}",
            display_name=str(i),
            from_email=f"{i}@x.com",
            transport="noop",
            transport_config={},
        )
    assert await _resolve_identity(session, None) is None


@pytest.mark.asyncio
async def test_bare_email_with_zero_identities_returns_none(session) -> None:
    """No identities + no env transport = nothing to route to."""
    assert await _resolve_identity(session, None) is None
