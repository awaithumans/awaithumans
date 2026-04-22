# Security policy

## Reporting a vulnerability

**Do not file a public issue.** Security reports should be emailed
privately to **security@awaithumans.dev**.

If the vulnerability is under active exploitation or you need
PGP-encrypted communication, note that in your first email and we'll
coordinate a more secure channel.

We aim to:

- Acknowledge receipt within **2 business days**.
- Provide an initial triage assessment within **5 business days**.
- Ship a fix and a coordinated disclosure within **30 days** for high
  and critical severity issues, faster when feasible.

## What to report

Anything that affects the confidentiality, integrity, or availability
of an `awaithumans` deployment — the SDK, server, dashboard, CLI, or
bundled adapters / channels. A non-exhaustive list of the kinds of
issues we want to hear about:

- Authentication or authorization bypass
- Session cookie / admin bearer token weaknesses
- SQL injection, command injection, path traversal
- Cross-site scripting, CSRF, clickjacking
- Slack signature verification weaknesses
- Secret exposure (encrypted columns, log leakage, response payloads)
- Timing side channels on auth paths
- Denial-of-service vectors against a single-tenant deployment
- Supply-chain issues in pinned dependencies
- Missing security headers or TLS misconfiguration defaults

## What is out of scope

- Self-inflicted misconfigurations (e.g. running without `PAYLOAD_KEY`
  in production, setting `CORS_ORIGINS=*` with credentialed requests,
  exposing the admin bearer token).
- Denial-of-service from an authenticated operator (operators are
  trusted by design — the dashboard admin surface is not a privilege
  escalation target).
- Rate-limit concerns on the login endpoint — v1 documents the
  absence of rate limiting; proper limiter lands in a post-launch
  hardening pass. A report pinning a specific amplification attack
  beyond online brute-force is in scope.
- Third-party services (Slack, Resend, Anthropic) — file with the
  vendor. We can relay if the issue is in how `awaithumans` calls
  into them.

## Disclosure

When a fix ships, we credit the reporter in the release notes unless
you prefer to stay anonymous. CVE assignment happens on request for
any fix with a meaningful security impact.

## What you can expect from us

- A response that takes the report seriously regardless of severity.
- A straight answer if we disagree with a classification, with our
  reasoning.
- No legal threats or takedowns for good-faith security research.
- Credit on disclosure if you want it.
