"""EmailSenderIdentity service — upsert / get / list / delete.

Transport config is encrypted at rest. Raw SQL peek confirms that
provider credentials (like an API key) never land on disk in plaintext.
"""

from __future__ import annotations

import secrets

import pytest
from cryptography.exceptions import InvalidTag
from sqlalchemy import text
from sqlalchemy.exc import InvalidRequestError

from awaithumans.server.core import encryption
from awaithumans.server.core.config import settings
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
        text("SELECT transport_config FROM email_sender_identities WHERE id = 'acme-prod'")
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


@pytest.mark.asyncio
async def test_list_survives_undecryptable_row(session) -> None:
    """A row whose transport_config was encrypted under a rotated/stale
    PAYLOAD_KEY must not crash the listing endpoint.

    Repro of the dashboard 500 on /api/channels/email/identities: one
    smoke-test row was left over from an earlier key, EncryptedString
    raised InvalidTag at row materialization, and the whole listing
    endpoint 500'd. After the fix, listing defers transport_config so
    the column is never decrypted; per-row ops that need the secret
    still fail loudly.
    """
    await upsert_identity(
        session,
        identity_id="good",
        display_name="Good",
        from_email="good@x.com",
        transport="noop",
        transport_config={"ok": True},
    )
    await upsert_identity(
        session,
        identity_id="stale-key",
        display_name="Stale Key",
        from_email="stale@x.com",
        transport="noop",
        transport_config={"will_be_overwritten": True},
    )

    # Re-encrypt one row's transport_config under a different key,
    # then restore the original so subsequent reads of the "good" row
    # still succeed. This mirrors the real-world rotation scenario.
    original_key = settings.PAYLOAD_KEY
    settings.PAYLOAD_KEY = secrets.token_urlsafe(32)
    encryption.reset_key_cache()
    rotated_blob = encryption.encrypt_str('{"rotated":true}')
    settings.PAYLOAD_KEY = original_key
    encryption.reset_key_cache()

    await session.execute(
        text("UPDATE email_sender_identities SET transport_config = :blob WHERE id = 'stale-key'"),
        {"blob": rotated_blob},
    )
    await session.commit()

    rows = await list_identities(session)
    ids = {r.id for r in rows}
    assert ids == {"good", "stale-key"}

    # The deferred column must not be accessible — touching it should
    # raise rather than silently lazy-load. This enforces the contract
    # that listing is a public-fields-only view.
    stale_row = next(r for r in rows if r.id == "stale-key")
    with pytest.raises(InvalidRequestError):
        _ = stale_row.transport_config

    # Per-row fetch still loads transport_config and surfaces the
    # decryption failure loudly — callers that need the secret learn
    # immediately that this row is unusable.
    with pytest.raises(InvalidTag):
        await get_identity(session, "stale-key")

    # The healthy row still round-trips through get_identity unaffected.
    good = await get_identity(session, "good")
    assert good is not None
    assert identity_config(good) == {"ok": True}
