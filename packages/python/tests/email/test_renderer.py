"""Email renderer — when do we emit magic-link buttons vs link-out only?"""

from __future__ import annotations

from awaithumans.forms import (
    FormDefinition,
    display_text,
    long_text,
    short_text,
    single_select,
    switch,
)
from awaithumans.server.channels.email.renderer import build_notification_email


def _name(field, n):
    return field.model_copy(update={"name": n})


def _build(form, task_title="Approve this wire", task_payload=None, redact=False):
    return build_notification_email(
        to="alice@example.com",
        task_id="t-abc",
        task_title=task_title,
        task_payload=task_payload,
        redact_payload=redact,
        form=form,
        from_email="notifications@acme.com",
        from_name="Acme Tasks",
        reply_to=None,
        public_url="https://acme.example.com",
    )


# ─── Magic-link buttons ─────────────────────────────────────────────────


def test_switch_emits_two_buttons() -> None:
    form = FormDefinition(fields=[_name(switch(label="Approve?"), "approve")])
    msg = _build(form)
    # Both true_label and false_label land in the HTML.
    assert "Yes" in msg.html
    assert "No" in msg.html
    # Two magic-link URLs.
    assert msg.html.count("/api/channels/email/action/") == 2
    # Plain-text alternate mirrors the buttons.
    assert "Yes:" in msg.text
    assert "No:" in msg.text


def test_single_select_under_4_options_emits_buttons() -> None:
    form = FormDefinition(
        fields=[
            _name(
                single_select(
                    options=[("a", "Approve"), ("r", "Reject"), ("d", "Defer")],
                    label="Decision",
                ),
                "decision",
            )
        ]
    )
    msg = _build(form)
    for label in ("Approve", "Reject", "Defer"):
        assert label in msg.html
    assert msg.html.count("/api/channels/email/action/") == 3


def test_single_select_over_4_falls_back_to_link_out() -> None:
    form = FormDefinition(
        fields=[
            _name(
                single_select(
                    options=[(c, c.upper()) for c in "abcde"], label="Pick"
                ),
                "pick",
            )
        ]
    )
    msg = _build(form)
    assert "/api/channels/email/action/" not in msg.html
    assert "/tasks/t-abc" in msg.html  # link-out URL


# ─── Forms that can't use magic links ───────────────────────────────────


def test_long_text_only_form_is_link_out() -> None:
    form = FormDefinition(fields=[_name(long_text(label="Why?"), "why")])
    msg = _build(form)
    assert "/api/channels/email/action/" not in msg.html
    assert "/tasks/t-abc" in msg.html


def test_multi_input_form_is_link_out() -> None:
    """Even if one field is a switch, the presence of a second input
    prevents magic-link buttons. Completing multi-field forms is
    dashboard-only for v1."""
    form = FormDefinition(
        fields=[
            _name(switch(label="Approve?"), "approve"),
            _name(long_text(label="Reason"), "reason"),
        ]
    )
    msg = _build(form)
    assert "/api/channels/email/action/" not in msg.html
    assert "/tasks/t-abc" in msg.html


def test_display_text_doesnt_count_as_input() -> None:
    """display_text, section, divider are ignored by the single-input check."""
    form = FormDefinition(
        fields=[
            display_text("Review this"),
            _name(switch(label="OK?"), "ok"),
        ]
    )
    msg = _build(form)
    assert msg.html.count("/api/channels/email/action/") == 2


def test_no_form_is_link_out() -> None:
    msg = _build(None)
    assert "/api/channels/email/action/" not in msg.html


# ─── Payload rendering ──────────────────────────────────────────────────


def test_payload_rendered_when_not_redacted() -> None:
    form = FormDefinition(fields=[_name(switch(label="OK?"), "ok")])
    msg = _build(form, task_payload={"amount": 50000, "to": "Acme"})
    assert "amount" in msg.html
    assert "50000" in msg.html
    assert "Acme" in msg.html
    assert "amount" in msg.text


def test_payload_hidden_when_redacted() -> None:
    form = FormDefinition(fields=[_name(switch(label="OK?"), "ok")])
    msg = _build(form, task_payload={"amount": 50000}, redact=True)
    assert "50000" not in msg.html
    assert "redacted" in msg.html.lower()


def test_payload_html_escaped() -> None:
    """Values from developer payload must be HTML-escaped so `<script>` can't
    execute in an email client that renders HTML (some do)."""
    form = FormDefinition(fields=[_name(switch(label="OK?"), "ok")])
    msg = _build(form, task_payload={"note": "<script>alert('xss')</script>"})
    assert "<script>" not in msg.html
    assert "&lt;script&gt;" in msg.html


# ─── Message metadata ───────────────────────────────────────────────────


def test_subject_carries_task_title() -> None:
    form = FormDefinition(fields=[_name(switch(label="OK?"), "ok")])
    msg = _build(form, task_title="Approve $50k wire")
    assert "Approve $50k wire" in msg.subject


def test_tags_include_task_id() -> None:
    form = FormDefinition(fields=[_name(switch(label="OK?"), "ok")])
    msg = _build(form)
    assert msg.tags == {"task_id": "t-abc"}
