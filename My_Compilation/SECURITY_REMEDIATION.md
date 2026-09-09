# Project ARJUNA — Security Remediation Runbook (S1–S4, T5, T6)

Status legend: **[ACTION REQUIRED]** you must do this outside the repository ·
**[DOCUMENTED]** handled by this runbook · **[UNVERIFIED]** requires live environment.

---

## 1. Rotate the exposed Supabase key — **[ACTION REQUIRED]** (S1)

A real Supabase publishable key and project reference were previously committed
in `.env.example` (since sanitized to placeholders). **Treat the old key as
compromised** — sanitize-and-commit does not un-leak it.

1. Open the Supabase Dashboard → your project → **Settings → API Keys**.
2. **Rotate/revoke** the leaked publishable key (`sb_publishable_…` was present
   in the repository file).
3. Issue a new publishable key for demo read paths and store it ONLY in a local
   `.env` file (which is git-ignored — verify `.gitignore` contains `.env`).
4. Never place the `service_role` secret key in any tracked file or frontend
   bundle.

## 2. Scrub the key from Git history — **[ACTION REQUIRED]** (S2)

Rotating makes the leaked key useless, but history scrubbing is still good
hygiene if this repository becomes public or is shared.

> ⚠️ History rewrite changes every commit hash. Coordinate with all
> collaborators and force-push. **This must only be done by the repository
> owner** — never run against a shared repo without agreement.

Recommended (git-filter-repo):
```powershell
pip install git-filter-repo
git clone --no-local <repo-url> clean-repo   # or run in a fresh mirror clone
cd clean-repo
git filter-repo --replace-text expressions.txt
# expressions.txt contains one line per secret, e.g.:
#   sb_publishable_XXXX==>REDACTED
git push --force --all
git push --force --tags
```
Alternative: BFG Repo-Cleaner (`bfg --replace-text`).

Then verify no trace remains:
```powershell
git log --all -p -S "sb_publishable_"          # should return nothing
```

## 3. RLS architecture vs. key class — **[DOCUMENTED / UNVERIFIED]** (S3, S4)

Facts from the code (no live verification performed):

| Layer | Fact |
|---|---|
| `migrations/supabase_schema.sql` | `telemetry_logs`/`system_events` allow INSERT only to `service_role` (authoritative backend writer; P0-05). Arbitrary `authenticated` end-users have **no** INSERT; SELECT is public (explicit demo policy). |
| `Backend/database.py` | Ingests with whatever key `SUPABASE_KEY` provides. |
| Consequence | A **publishable/anon-class key cannot insert** — PostgREST returns 401/403 and the store falls back to the in-memory buffer. Since the S5 fix, this fallback now logs a throttled `PERSISTENCE FALLBACK` warning and sets `last_error` (visible via `/api/status` persistence state), so it is no longer silent. |
| Correct production config | Backend `.env` must carry a **service_role key** (server-side only) for inserts. Publishable/anon keys are appropriate only for direct dashboard reads. |

**Live verification (T5/T6)** — run after supplying real credentials in `.env`:
```powershell
python scripts/check_supabase_rls.py
```
The script is opt-in: it runs ONLY when `SUPABASE_URL` and `SUPABASE_KEY` are
set, and performs two checks:
1. Insert with the configured key. Expected: **SUCCEEDS** with `service_role`,
   **FAILS with 401/403** with anon/publishable (proving RLS is enforced).
2. Anonymous SELECT on `telemetry_logs`. Expected: **SUCCEEDS** (read is
   intentionally public) — confirms the policy matches the documented model.

## 4. Production-like integration checklist (T6)

- [ ] `SUPABASE_ENABLED=true`, `SUPABASE_URL`, `SUPABASE_KEY` (service_role) in backend `.env` only
- [ ] `scripts/check_supabase_rls.py` passes both checks
- [ ] `/api/status` shows `persistence.last_error = null` while streaming
- [ ] Deliberately set a wrong key and confirm the `PERSISTENCE FALLBACK`
      warning appears and `/api/status` reports `last_error` (S5 drill)
- [ ] `ENVIRONMENT=production` + default keys → server must refuse to start
      (already regression-tested: `tests/test_security.py`)

## 5. What was already fixed in-repo

- `.env.example` sanitized (real values → placeholders); `SUPABASE_ENABLED`
  default aligned to `false`.
- Persistence failures surfaced (`Backend/database.py` throttled WARNING +
  non-2xx `last_error`) with regression tests (`tests/test_supabase.py`).
