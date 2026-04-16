"""Shared channel routing parser."""

from __future__ import annotations

from awaithumans.server.channels.routing import parse_route, routes_for_channel


def test_email_default_identity() -> None:
    r = parse_route("email:alice@example.com")
    assert r is not None
    assert r.channel == "email"
    assert r.identity is None
    assert r.target == "alice@example.com"


def test_email_explicit_identity() -> None:
    r = parse_route("email+acme-prod:alice@example.com")
    assert r is not None
    assert r.channel == "email"
    assert r.identity == "acme-prod"
    assert r.target == "alice@example.com"


def test_email_plus_tag_in_target_is_preserved() -> None:
    """`+` inside the target is fine — only the prefix delimiter matters."""
    r = parse_route("email:alice+tag@example.com")
    assert r is not None
    assert r.target == "alice+tag@example.com"
    assert r.identity is None


def test_email_identity_and_plus_tag_target() -> None:
    r = parse_route("email+acme:alice+tag@example.com")
    assert r is not None
    assert r.identity == "acme"
    assert r.target == "alice+tag@example.com"


def test_slack_default() -> None:
    r = parse_route("slack:#approvals")
    assert r is not None
    assert r.channel == "slack"
    assert r.identity is None
    assert r.target == "#approvals"


def test_slack_team_identity() -> None:
    r = parse_route("slack+T123456:#approvals")
    assert r is not None
    assert r.channel == "slack"
    assert r.identity == "T123456"


def test_invalid_strings_return_none() -> None:
    assert parse_route("") is None
    assert parse_route("just-text") is None
    assert parse_route(":@only-target") is None
    assert parse_route("email+:target") is None  # empty identity
    assert parse_route("+foo:target") is None  # empty channel


def test_routes_for_channel_filters_and_parses() -> None:
    notify = [
        "email:a@x.com",
        "slack:#ops",
        "email+acme:b@x.com",
        "garbage",
        "slack+T1:#approvals",
    ]
    emails = routes_for_channel(notify, "email")
    assert [(r.identity, r.target) for r in emails] == [
        (None, "a@x.com"),
        ("acme", "b@x.com"),
    ]
    slacks = routes_for_channel(notify, "slack")
    assert [(r.identity, r.target) for r in slacks] == [
        (None, "#ops"),
        ("T1", "#approvals"),
    ]


def test_routes_for_channel_handles_none_notify() -> None:
    assert routes_for_channel(None, "email") == []
    assert routes_for_channel([], "email") == []
