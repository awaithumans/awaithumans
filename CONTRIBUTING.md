# Contributing to awaithumans

Thanks for your interest in contributing. This doc covers the discipline
we follow so parallel work doesn't step on itself. Project structure,
coding standards, and architecture live in [`CLAUDE.md`](./CLAUDE.md).

---

## Database migrations

We use Alembic. The single biggest source of chaos in collaborative
schema work is **two branches each adding a migration against the same
parent head** — when both merge, Alembic refuses to run until someone
hand-writes a merge migration. The rules below exist to make that
situation either impossible (CI catches it) or cheap to fix (rebase,
not resolve).

These rules are load-bearing. CI enforces the first one automatically;
please treat the rest as non-negotiable.

### 1. Single head is a CI invariant

`alembic heads` must return exactly one line at all times on `main`.
A GitHub Actions check runs on every PR — if your branch produces a
second head, CI goes red and the PR can't merge. The fix when this
happens:

```bash
# pull the new main
git fetch origin && git rebase origin/main

# blow away your migration file (it pointed at the old head)
rm packages/python/alembic/versions/<your_migration>.py

# regenerate against the new head
cd packages/python
alembic revision --autogenerate -m "your message"

# review the diff, commit, force-push your branch
```

This takes ~30 seconds once you've done it once. The CI check is
there so you discover the conflict when you open the PR, not when
you deploy.

### 2. Additive changes by default

Most PRs add columns or tables. Adding rarely conflicts with other
adds, so most PRs sail through.

Destructive changes — renames, drops, type changes — are the
troublemakers. The rule: **split destructive changes across three
PRs**, in this order:

1. **Add-new** — add the new column/table. Writes go to both old and new.
2. **Migrate-reads** — update all read sites to use the new column. Old column is now unread but still written.
3. **Drop-old** — drop the old column/table.

This is also the zero-downtime production practice — one discipline
gives you both safe deploys and conflict-resistant schema work.

### 3. Always autogenerate locally, never in CI

```bash
cd packages/python
alembic revision --autogenerate -m "add users table"
```

Review the generated file before committing. Autogenerate in CI
produces non-reproducible migrations and hides what you actually
changed. The migration file should be committed in the same PR as
the model change it captures.

### 4. Migration files use date-based names

Migration filenames are `YYYYMMDD_HHMM_slug.py`, not the default
`<random-hex>_slug.py`. Our `alembic.ini` sets
`file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(slug)s`
to enforce this.

Why: visual conflicts are obvious, chronology is trivial to read,
and you can eyeball the order without running Alembic. The revision
ID inside the file stays a random hex — only the filename is
date-prefixed.

### 5. One logical change per migration

Don't bundle "add users table + rename tasks column + drop foo" into
one migration. Small migrations rebase cleanly; big ones don't.
If your PR needs multiple migration files, that's fine — just make
each one a coherent unit.

### Running migrations

```bash
# apply all pending migrations
cd packages/python
alembic upgrade head

# show current revision
alembic current

# show the migration history
alembic history

# generate a new migration from model changes
alembic revision --autogenerate -m "describe the change"
```

In dev, `awaithumans dev` runs `alembic upgrade head` automatically
on startup so first-time contributors don't have to remember.

### When things go wrong

If you hit "multiple heads" locally:

```bash
# see what heads exist
alembic heads

# if they're legitimate and both need to merge, create a merge migration
alembic merge -m "merge heads" <head1> <head2>
```

Merge migrations should be **rare**. If you find yourself reaching
for `alembic merge` more than once every few months, something is
wrong with how PRs are being sequenced — surface it in a weekly
sync rather than papering over it with merges.

---

## Other contributing rules

TODO: expand this section. For now, see `CLAUDE.md` for the coding
guide, `CODE_QUALITY.md` for code review standards, and
[`README.md`](./README.md) for getting started.
