"""EmailSenderIdentity service — upsert / get / list / delete.

Transport config is encrypted at rest. Raw SQL peek confirms that
provider credentials (like an API key) never land on disk in plaintext.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from awaithumans.server.services.email_identity_service import (
    delete_identity,
    get_identity,
    identity_config,
    list_identities,
    upsert_identity,
)


@pytest.mark.asyncio
async def test_upsert_new_and_fetch(session) -> None:
    row = await upsert_identity(
        session,
        identity_id="acme-prod",
        display_name="Acme Production",
        from_email="notifications@acme.com",
        transport="resend",
        transport_config={"api_key": "re_prod_abc123"},
    )
    assert row.id == "acme-prod"
    assert row.from_email == "notifications@acme.com"

    # Decrypt via service helper.
    assert identity_config(row) == {"api_key": "re_prod_abc123"}


@pytest.mark.asyncio
async def test_transport_config_encrypted_on_disk(session) -> None:
    await upsert_identity(
        session,
        identity_id="acme-prod",
        display_name="Acme",
        from_email="x@acme.com",
        transport="resend",
        transport_config={"api_key": "re_prod_SENSITIVE"},
    )
    result = await session.execute(
        text(
            "SELECT transport_config FROM email_sender_identities WHERE id = 'acme-prod'"
        )
    )
    raw = result.scalar_one()
    assert "re_prod_SENSITIVE" not in raw
    assert "api_key" not in raw
    # Ciphertext is base64 of significantly longer than the plaintext.
    assert len(raw) > len('{"api_key":"re_prod_SENSITIVE"}')


@pytest.mark.asyncio
async def test_upsert_updates_in_place(session) -> None:
    await upsert_identity(
        session,
        identity_id="acme",
        display_name="A",
        from_email="old@a.com",
        transport="resend",
        transport_config={"api_key": "old"},
    )
    await upsert_identity(
        session,
        identity_id="acme",
        display_name="A-new",
        from_email="new@a.com",
        transport="resend",
        transport_config={"api_key": "new"},
    )
    row = await get_identity(session, "acme")
    assert row.from_email == "new@a.com"
    assert row.display_name == "A-new"
    assert identity_config(row) == {"api_key": "new"}


@pytest.mark.asyncio
async def test_list_and_delete(session) -> None:
    for i in range(3):
        await upsert_identity(
            session,
            identity_id=f"id-{i}",
            display_name=str(i),
            from_email=f"{i}@x.com",
            transport="noop",
            transport_config={},
        )
    rows = await list_identities(session)
    assert len(rows) == 3

    assert await delete_identity(session, "id-1") is True
    rows = await list_identities(session)
    assert {r.id for r in rows} == {"id-0", "id-2"}

    assert await delete_identity(session, "id-1") is False


@pytest.mark.asyncio
async def test_get_missing_returns_none(session) -> None:
    assert await get_identity(session, "nope") is None
