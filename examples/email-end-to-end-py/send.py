"""End-to-end real-delivery email test (Python).

Mirror of `examples/email-end-to-end/send.ts` — exercises the same
real-mail loop (configure identity → fire task → wait for the human
to click the magic-link button in their inbox → resolve) but driven
from the Python SDK.

Pick a transport via env:

    AWAITHUMANS_TEST_TRANSPORT=resend RESEND_API_KEY=re_... \
      RECIPIENT_EMAIL=you@example.com \
      [FROM_EMAIL=onboarding@resend.dev] \
      python send.py

    AWAITHUMANS_TEST_TRANSPORT=smtp \
      SMTP_HOST=smtp.gmail.com SMTP_PORT=587 \
      SMTP_USER=you@gmail.com SMTP_PASSWORD=<app password> \
      RECIPIENT_EMAIL=you@example.com \
      FROM_EMAIL=you@gmail.com \
      python send.py

    # Hostinger Mail (port 465 / SSL):
    AWAITHUMANS_TEST_TRANSPORT=smtp \
      SMTP_HOST=smtp.hostinger.com SMTP_PORT=465 \
      SMTP_USER=you@yourdomain.com SMTP_PASSWORD=... \
      FROM_EMAIL=you@yourdomain.com \
      RECIPIENT_EMAIL=you@yourdomain.com \
      python send.py

The identity is upserted as `email-e2e-real-py` so re-runs with
new transport_config overwrite in place — no duplicate-id error.

Prerequisites:
  - `awaithumans dev` running in another terminal (the SDK reads
    URL + admin token from the discovery file, no env-var dance)
  - For Resend: a Resend account + API key. The
    `onboarding@resend.dev` sender works without domain verification.
  - For SMTP: a working SMTP host. Gmail needs an App Password
    (https://myaccount.google.com/apppasswords). Hostinger uses
    port 465 with the mailbox password (NOT the Hostinger account
    password).
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import httpx
from pydantic import BaseModel, Field

from awaithumans import await_human
from awaithumans.utils.discovery import resolve_admin_token, resolve_server_url

# ─── Resolve config ────────────────────────────────────────────────────

SERVER_URL = resolve_server_url().rstrip("/")
ADMIN_TOKEN = resolve_admin_token()

if not ADMIN_TOKEN:
    print(
        "Couldn't find an admin token. Run `awaithumans dev` first "
        "(writes ~/.awaithumans-dev.json), or export "
        "AWAITHUMANS_ADMIN_API_TOKEN.",
        file=sys.stderr,
    )
    sys.exit(1)

RECIPIENT = os.environ.get("RECIPIENT_EMAIL")
if not RECIPIENT:
    print("RECIPIENT_EMAIL is required — your real inbox.", file=sys.stderr)
    sys.exit(1)

TRANSPORT = os.environ.get("AWAITHUMANS_TEST_TRANSPORT", "resend")
IDENTITY_ID = "email-e2e-real-py"


# ─── Build transport_config from env ───────────────────────────────────


def build_transport_setup() -> dict[str, Any]:
    if TRANSPORT == "resend":
        api_key = os.environ.get("RESEND_API_KEY")
        if not api_key:
            print(
                "RESEND_API_KEY required when transport=resend.",
                file=sys.stderr,
            )
            sys.exit(1)
        return {
            "from_email": os.environ.get("FROM_EMAIL", "onboarding@resend.dev"),
            "transport": "resend",
            "transport_config": {"api_key": api_key},
        }

    if TRANSPORT == "smtp":
        host = os.environ.get("SMTP_HOST")
        from_email = os.environ.get("FROM_EMAIL")
        if not host or not from_email:
            print(
                "SMTP_HOST and FROM_EMAIL required when transport=smtp.",
                file=sys.stderr,
            )
            sys.exit(1)
        port = int(os.environ.get("SMTP_PORT", "587"))
        # Port 465 is implicit TLS (SSL on connect — what Hostinger,
        # Gmail SSL, and most "secure" SMTP setups use). Port 587 is
        # STARTTLS (plain connect, upgrade with STARTTLS — what
        # Gmail modern, O365, AWS SES, Mailgun use). aiosmtplib
        # rejects setting both modes — pick one based on port.
        # Override with SMTP_TLS_MODE=ssl|starttls if your server
        # uses a non-standard port.
        tls_mode = os.environ.get(
            "SMTP_TLS_MODE", "ssl" if port == 465 else "starttls"
        )
        use_tls = tls_mode == "ssl"
        return {
            "from_email": from_email,
            "transport": "smtp",
            "transport_config": {
                "host": host,
                "port": port,
                "username": os.environ.get("SMTP_USER"),
                "password": os.environ.get("SMTP_PASSWORD"),
                "use_tls": use_tls,
                "start_tls": not use_tls,
            },
        }

    print(
        f"Unknown transport '{TRANSPORT}'. Valid: resend, smtp. "
        "(The `file` and `logging` transports are dev-only — see "
        "examples/email-smoke-py for that.)",
        file=sys.stderr,
    )
    sys.exit(1)


# ─── Identity setup (idempotent upsert) ────────────────────────────────


_admin = httpx.Client(
    base_url=SERVER_URL,
    headers={
        "Authorization": f"Bearer {ADMIN_TOKEN}",
        "Content-Type": "application/json",
    },
    timeout=10,
)


def configure_identity(setup: dict[str, Any]) -> None:
    resp = _admin.post(
        "/api/channels/email/identities",
        json={
            "id": IDENTITY_ID,
            "display_name": "awaithumans e2e real (py)",
            "from_email": setup["from_email"],
            "from_name": "awaithumans test",
            "reply_to": None,
            "transport": setup["transport"],
            "transport_config": setup["transport_config"],
        },
    )
    if resp.status_code >= 400:
        print(
            f"identity setup failed ({resp.status_code}): {resp.text}",
            file=sys.stderr,
        )
        sys.exit(1)
    print(
        f"→ identity '{IDENTITY_ID}' configured "
        f"(transport={setup['transport']}, from={setup['from_email']})"
    )


# ─── Schemas ───────────────────────────────────────────────────────────


class TestNote(BaseModel):
    note: str
    sent_at: str


class ApprovalResponse(BaseModel):
    """Single boolean → server-side `extract_form` produces a Switch
    primitive, which is what the email renderer uses to decide whether
    to emit Approve/Reject magic-link buttons."""

    approved: bool = Field(..., description="Approve this test?")


# ─── Run ───────────────────────────────────────────────────────────────


async def main() -> None:
    print(f"→ server: {SERVER_URL}")
    print(f"→ recipient: {RECIPIENT}")
    print(f"→ transport: {TRANSPORT}")

    configure_identity(build_transport_setup())

    print("")
    print(
        "→ creating task — check your inbox in a few seconds and click "
        "the Approve button to complete it"
    )

    decision: ApprovalResponse = await await_human(
        task="Approve this real-delivery test (Python)",
        payload_schema=TestNote,
        payload=TestNote(
            note="If you received this email, awaithumans (Python) → real-mail integration works.",
            sent_at=__import__("datetime").datetime.now().isoformat(),
        ),
        response_schema=ApprovalResponse,
        # 30-minute window — generous so you have time to find the
        # email, click through, and walk back. The post-completion
        # updater will mark the message done either way.
        timeout_seconds=30 * 60,
        notify=[f"email+{IDENTITY_ID}:{RECIPIENT}"],
        idempotency_key=f"email-e2e-real-py:{int(__import__('time').time())}",
    )

    print("")
    if decision.approved:
        print("✓ Approved — task completed end-to-end via real email")
    else:
        print("✗ Rejected — task completed end-to-end via real email")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        _admin.close()
