# awaithumans v0.1.3 — patch release

Three bug-fix PRs reported by early testers, landing two days after [v0.1.2](https://github.com/awaithumans/awaithumans/releases/tag/v0.1.2). No API changes; safe drop-in upgrade.

## Highlights

- 🌍 **Email-handoff URLs no longer expire instantly for East-of-UTC users.** A naive-datetime → local-time conversion was shifting URL expiries by the local-UTC offset. A UTC+1 user saw a fresh 10-minute task issue a link born 50 minutes expired. ([#107](https://github.com/awaithumans/awaithumans/pull/107))
- 🧩 **`AWAITHUMANS_URL` in a shared `.env` no longer crashes the server on boot.** The SDK-side and server-side namespaces share a prefix; pydantic-settings' dotenv source used to enforce `extra="forbid"` by default. Now silently ignored, with a startup `WARNING` listing unknown keys so typos still get caught. ([#108](https://github.com/awaithumans/awaithumans/pull/108))
- 📝 **First-touch DX: clearer install + CLI error.** Bare `pip install awaithumans` followed by `awaithumans dev` now exits with a what → why → fix → docs message pointing at the `[server]` extra, instead of a raw `ImportError` traceback. ([#106](https://github.com/awaithumans/awaithumans/pull/106))
- 🤝 **Python and TypeScript stay mono-versioned at `0.1.3`** — even though the TypeScript SDK has no code changes this round, the version number tracks Python.

## Upgrade

### Python

```bash
pip install --upgrade "awaithumans[server]==0.1.3"
# or whichever extras you use:
#   pip install --upgrade "awaithumans[temporal]==0.1.3"
#   pip install --upgrade "awaithumans[langgraph]==0.1.3"
#   pip install --upgrade "awaithumans[verifier-claude]==0.1.3"
```

### TypeScript

```bash
npm install awaithumans@0.1.3
# Or with peers if you're using the adapters:
#   npm install awaithumans@0.1.3 @temporalio/workflow @temporalio/client
#   npm install awaithumans@0.1.3 @langchain/langgraph
```

### Docker

```bash
docker pull ghcr.io/awaithumans/awaithumans:0.1.3
# Or use the floating tag:
docker pull ghcr.io/awaithumans/awaithumans:latest
```

## What changed

### Fixed

- **Email-handoff URL `e` parameter coerced to UTC before signing.** SQLite + SQLModel stores `task.timeout_at` tz-naive; `int(task.timeout_at.timestamp())` was treating the naive value as local time, shifting the expiry by the local-UTC offset. For users east of UTC this killed every freshly-issued email link. Fix extracted to a shared `awaithumans.utils.time.to_utc_unix` helper used by both the email and Slack handoff paths. Regression test runs under `TZ=Africa/Lagos`. ([#107](https://github.com/awaithumans/awaithumans/pull/107))

- **`Settings()` ignores unknown `AWAITHUMANS_*` env keys** instead of raising `extra_forbidden`. Pydantic-settings' dotenv source enforced `extra="forbid"` by default; the env-var source did not. Asymmetric crash behavior killed any `awaithumans dev` whose `.env` contained an SDK-side key like `AWAITHUMANS_URL`. Now silently ignored with a one-shot startup `WARNING` listing unrecognized keys, so typos still surface. ([#108](https://github.com/awaithumans/awaithumans/pull/108))

- **CLI bare-install error rewritten** to follow the what → why → fix → docs pattern with an actionable docs URL, instead of the previous one-liner. ([#106](https://github.com/awaithumans/awaithumans/pull/106))

### Docs

- **`docs/sdk/python.mdx` install matrix restructured** to lead with the two main paths (run a server vs call a server) and explain how to stack extras like `[server,temporal,verifier-claude]`. ([#106](https://github.com/awaithumans/awaithumans/pull/106))
- **`docs/troubleshooting.mdx`** gains a `### cli-missing-server-extra` section so the new CLI error message links to a real anchor. ([#106](https://github.com/awaithumans/awaithumans/pull/106))
- **`docs/self-hosting/configuration.mdx`** opens with a new "Two namespaces under one prefix" section documenting the SDK/server split and the new silent-ignore + warning policy. ([#108](https://github.com/awaithumans/awaithumans/pull/108))

## What didn't change

- **No API changes** — every public function signature in v0.1.2 still works identically in v0.1.3.
- **No breaking changes** — `pip install --upgrade` and `npm install awaithumans@latest` are safe drop-in upgrades.
- **No TypeScript SDK source changes** — TS bump is mono-version sync only.

## Verify the upgrade landed

After upgrading the Python package:

```bash
python -c "import awaithumans; print(awaithumans.__version__)"
# → 0.1.3

awaithumans dev
# In another terminal, on a UTC+ machine: create a task with
# timeout_seconds=600 and click the "Open task" link in the email.
# You should land on the task page, not a 400 "Sign-in link is
# invalid or expired" error.
```

After upgrading the TS package:

```bash
node -e "console.log(require('awaithumans/package.json').version)"
# → 0.1.3
```

## Links

- 📚 [Documentation](https://docs.awaithumans.dev)
- 🆕 [What's new](https://docs.awaithumans.dev/changelog)
- 🔒 Security disclosures: **security@awaithumans.dev**
- 💬 [Discord](https://discord.gg/Kewdh7vjdc) · [GitHub Discussions](https://github.com/awaithumans/awaithumans/discussions)
- 🐛 [v0.1.2 → v0.1.3 full diff](https://github.com/awaithumans/awaithumans/compare/v0.1.2...v0.1.3)
