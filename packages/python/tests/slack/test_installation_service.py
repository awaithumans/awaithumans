"""SlackInstallation service — upsert / get / list / delete."""

from __future__ import annotations

import pytest

from awaithumans.server.services.slack_installation_service import (
    delete_installation,
    get_installation,
    list_installations,
    upsert_installation,
)


@pytest.mark.asyncio
async def test_upsert_new_then_fetch(session) -> None:
    row = await upsert_installation(
        session,
        team_id="T123",
        team_name="Acme",
        bot_token="xoxb-aaa",
        bot_user_id="U_BOT",
        scopes="chat:write,im:write",
        enterprise_id=None,
        installed_by_user_id="U_USER",
    )
    assert row.team_id == "T123"
    fetched = await get_installation(session, "T123")
    assert fetched is not None
    assert fetched.bot_token == "xoxb-aaa"
    assert fetched.scopes == "chat:write,im:write"


@pytest.mark.asyncio
async def test_upsert_existing_overwrites(session) -> None:
    await upsert_installation(
        session,
        team_id="T123",
        team_name="Acme",
        bot_token="xoxb-old",
        bot_user_id="U_BOT",
        scopes="chat:write",
    )
    await upsert_installation(
        session,
        team_id="T123",
        team_name="Acme Renamed",
        bot_token="xoxb-new",
        bot_user_id="U_BOT",
        scopes="chat:write,im:write",
    )
    fetched = await get_installation(session, "T123")
    assert fetched is not None
    assert fetched.bot_token == "xoxb-new"
    assert fetched.team_name == "Acme Renamed"
    assert fetched.scopes == "chat:write,im:write"


@pytest.mark.asyncio
async def test_list_returns_all(session) -> None:
    await upsert_installation(
        session,
        team_id="T1",
        team_name="A",
        bot_token="x1",
        bot_user_id="U1",
        scopes="chat:write",
    )
    await upsert_installation(
        session,
        team_id="T2",
        team_name="B",
        bot_token="x2",
        bot_user_id="U2",
        scopes="chat:write",
    )
    rows = await list_installations(session)
    assert {r.team_id for r in rows} == {"T1", "T2"}


@pytest.mark.asyncio
async def test_delete_removes_row(session) -> None:
    await upsert_installation(
        session,
        team_id="T1",
        team_name="A",
        bot_token="x1",
        bot_user_id="U1",
        scopes="chat:write",
    )
    assert await delete_installation(session, "T1") is True
    assert await get_installation(session, "T1") is None
    # Deleting non-existent returns False.
    assert await delete_installation(session, "T1") is False


@pytest.mark.asyncio
async def test_get_missing_returns_none(session) -> None:
    assert await get_installation(session, "T_NOPE") is None
