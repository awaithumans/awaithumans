"""EmailSenderIdentity CRUD.

Transport config is stored as a JSON string in the `transport_config`
column. That column is `EncryptedString`, so the JSON blob never lands
on disk in plaintext. Service code reads and writes Python dicts; we
handle the JSON encoding here so callers don't have to.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.server.db.models import EmailSenderIdentity


async def upsert_identity(
    session: AsyncSession,
    *,
    identity_id: str,
    display_name: str,
    from_email: str,
    transport: str,
    transport_config: dict[str, Any],
    from_name: str | None = None,
    reply_to: str | None = None,
    verified: bool = False,
    verified_at: datetime | None = None,
) -> EmailSenderIdentity:
    """Create or update an identity. Idempotent by `identity_id`."""
    existing = await get_identity(session, identity_id)
    now = datetime.now(timezone.utc)
    config_json = json.dumps(transport_config, sort_keys=True, separators=(",", ":"))

    if existing is None:
        row = EmailSenderIdentity(
            id=identity_id,
            display_name=display_name,
            from_email=from_email,
            from_name=from_name,
            reply_to=reply_to,
            transport=transport,
            transport_config=config_json,
            verified=verified,
            verified_at=verified_at,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row

    existing.display_name = display_name
    existing.from_email = from_email
    existing.from_name = from_name
    existing.reply_to = reply_to
    existing.transport = transport
    existing.transport_config = config_json
    existing.verified = verified
    existing.verified_at = verified_at
    existing.updated_at = now
    session.add(existing)
    await session.commit()
    await session.refresh(existing)
    return existing


async def get_identity(
    session: AsyncSession, identity_id: str
) -> EmailSenderIdentity | None:
    result = await session.execute(
        select(EmailSenderIdentity).where(EmailSenderIdentity.id == identity_id)
    )
    return result.scalar_one_or_none()


async def list_identities(session: AsyncSession) -> list[EmailSenderIdentity]:
    result = await session.execute(select(EmailSenderIdentity))
    return list(result.scalars().all())


async def delete_identity(session: AsyncSession, identity_id: str) -> bool:
    result = await session.execute(
        delete(EmailSenderIdentity).where(EmailSenderIdentity.id == identity_id)
    )
    await session.commit()
    return result.rowcount > 0


def identity_config(identity: EmailSenderIdentity) -> dict[str, Any]:
    """Decrypt + parse the transport_config JSON back into a dict."""
    return json.loads(identity.transport_config)
