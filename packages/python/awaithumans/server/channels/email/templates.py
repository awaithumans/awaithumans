"""HTML + plain-text email templates.

Inlined CSS for cross-client compatibility (Gmail strips `<style>`,
Outlook ignores modern layout). Single-column table layout so mobile
clients render sanely.

Three template surfaces:

- `notification_html()` / `notification_text()` — the task review email
- `confirmation_page_html()` — the magic-link "Are you sure?" page
- `completed_page_html()` — after the user submits (or on already-terminal)

Templates take pre-escaped `str` fields. The renderer in renderer.py
does escaping; this file is just assembly.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape


@dataclass
class ButtonSpec:
    label: str
    url: str
    # "primary" | "danger" | "neutral" — drives button color.
    style: str = "neutral"


_COLORS = {
    "primary": ("#00E676", "#0A0A0A"),  # bg, fg
    "danger": ("#F87171", "#0A0A0A"),
    "neutral": ("#E5E7EB", "#0A0A0A"),
}


def _button_html(button: ButtonSpec) -> str:
    bg, fg = _COLORS.get(button.style, _COLORS["neutral"])
    return (
        f'<a href="{escape(button.url, quote=True)}" '
        f'style="display:inline-block;padding:12px 22px;background:{bg};'
        f'color:{fg};text-decoration:none;border-radius:6px;'
        f'font-weight:600;font-size:14px;margin:0 8px 8px 0;">{escape(button.label)}</a>'
    )


def notification_html(
    *,
    task_title: str,
    payload_lines: list[tuple[str, str]],
    redacted: bool,
    buttons: list[ButtonSpec],
    review_url: str,
) -> str:
    """The primary email: task title, payload preview, buttons, link-out footer."""
    payload_html = ""
    if redacted:
        payload_html = (
            '<p style="color:#555;font-size:13px;">'
            "<em>Payload redacted.</em></p>"
        )
    elif payload_lines:
        rows = "".join(
            f'<tr><td style="color:#6B7280;font-size:13px;padding:3px 12px 3px 0;'
            f'vertical-align:top;"><strong>{escape(key)}</strong></td>'
            f'<td style="color:#111827;font-size:13px;padding:3px 0;word-break:break-word;">{escape(val)}</td></tr>'
            for key, val in payload_lines
        )
        payload_html = (
            '<table role="presentation" cellspacing="0" cellpadding="0" border="0" '
            'style="margin:16px 0;">{rows}</table>'
        ).format(rows=rows)

    buttons_html = "".join(_button_html(b) for b in buttons)
    buttons_section = (
        f'<div style="margin:24px 0;">{buttons_html}</div>' if buttons else ""
    )

    return f"""\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{escape(task_title)}</title>
</head>
<body style="margin:0;padding:24px;background:#F3F4F6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" width="560"
         style="background:#FFFFFF;border-radius:10px;padding:32px;max-width:560px;">
    <tr>
      <td>
        <p style="color:#6B7280;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;margin:0 0 8px;">
          Review requested
        </p>
        <h1 style="margin:0 0 8px;font-size:20px;font-weight:600;color:#0A0A0A;line-height:1.4;">
          {escape(task_title)}
        </h1>
        {payload_html}
        {buttons_section}
        <p style="margin:20px 0 0;color:#6B7280;font-size:12px;line-height:1.5;">
          Or <a href="{escape(review_url, quote=True)}" style="color:#059669;">open the full task in the dashboard</a>.
          You're receiving this because your team asked awaithumans to send review requests here.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def notification_text(
    *,
    task_title: str,
    payload_lines: list[tuple[str, str]],
    redacted: bool,
    buttons: list[ButtonSpec],
    review_url: str,
) -> str:
    """Plain-text alternate. Deliverability helper + accessibility."""
    out: list[str] = [
        "REVIEW REQUESTED",
        "",
        task_title,
        "",
    ]
    if redacted:
        out.append("Payload redacted.")
    elif payload_lines:
        for k, v in payload_lines:
            out.append(f"  {k}: {v}")
    if buttons:
        out.append("")
        out.append("Respond:")
        for b in buttons:
            out.append(f"  {b.label}: {b.url}")
    out.append("")
    out.append(f"Or open the dashboard: {review_url}")
    return "\n".join(out)


def confirmation_page_html(
    *,
    task_title: str,
    action_label: str,
    post_url: str,
    cancel_url: str,
) -> str:
    """The 'Are you sure?' page the magic link lands on (GET)."""
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>Confirm: {escape(action_label)}</title>
  <style>
    body {{ margin:0; background:#0A0A0A; color:#F5F5F5; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
            min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px; }}
    .card {{ background:#111111; border:1px solid #222; border-radius:12px; padding:32px; max-width:440px; width:100%; }}
    h1 {{ margin:0 0 8px; font-size:18px; font-weight:600; }}
    p.task {{ margin:0 0 24px; color:#9CA3AF; font-size:14px; line-height:1.5; }}
    .row {{ display:flex; gap:12px; }}
    button, a.cancel {{ flex:1; padding:12px 16px; border-radius:8px; font-size:14px; font-weight:600;
                        border:none; cursor:pointer; text-align:center; text-decoration:none; }}
    button.primary {{ background:#00E676; color:#0A0A0A; }}
    a.cancel {{ background:#1F1F1F; color:#E5E7EB; border:1px solid #333; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Confirm: {escape(action_label)}</h1>
    <p class="task">{escape(task_title)}</p>
    <form method="POST" action="{escape(post_url, quote=True)}" class="row">
      <a class="cancel" href="{escape(cancel_url, quote=True)}">Cancel</a>
      <button class="primary" type="submit">{escape(action_label)}</button>
    </form>
  </div>
</body>
</html>
"""


def completed_page_html(*, message: str) -> str:
    """Shown after POST succeeds or when the task is already terminal."""
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Done</title>
  <style>
    body {{ margin:0; background:#0A0A0A; color:#F5F5F5; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
            min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px; }}
    .card {{ background:#111111; border:1px solid #222; border-radius:12px; padding:32px; max-width:440px; text-align:center; }}
    h1 {{ margin:0 0 12px; font-size:20px; }}
    p {{ margin:0; color:#9CA3AF; font-size:14px; line-height:1.5; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Thanks</h1>
    <p>{escape(message)}</p>
  </div>
</body>
</html>
"""
