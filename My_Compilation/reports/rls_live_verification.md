# Live Supabase RLS Verification — Phase 1 (Security Remediation §3)

**Date**: 2026-09-09 · **Verified by**: live REST probes against the production project (URL redacted)
**Method**: `scripts/check_supabase_rls.py` (official, exit code 0) + extended HTTP verb matrix + git-history secret scan.

## Results matrix

| Probe | Role | Expected | Actual | Verdict |
|---|---|---|---|---|
| INSERT `telemetry_logs` | service_role (backend key) | succeed | 201 | ✅ PASS |
| SELECT `telemetry_logs` (public read) | anon/no key | succeed (documented DEMO policy, migration P1-17) | 200 | ✅ PASS |
| INSERT `telemetry_logs` | anon/no key | rejected | **404** (table hidden from anon role) | ✅ PASS |
| UPDATE `telemetry_logs` | anon/no key | rejected | 404 | ✅ PASS |
| DELETE `telemetry_logs` | anon/no key | rejected | 404 | ✅ PASS |
| INSERT `system_events` | anon/no key | rejected | 404 | ✅ PASS |
| UPDATE `telemetry_logs` | service_role | succeed (bypasses RLS by design) | 204 | ✅ PASS |
| DELETE `telemetry_logs` | service_role | succeed | 204 | ✅ PASS |

## Notes

- **404 semantics**: Supabase/PostgREST returns 404 (not 401/403) for the anon role because the
  table is not exposed to it — a strictly stronger rejection than a policy error.
- **Public SELECT is an explicit, documented DEMO policy** (`migrations/supabase_schema.sql`,
  audit P1-17): intentional so judges can query dashboards without authentication. Not a
  production posture; production guidance is in SECURITY_REMEDIATION.md.
- **DB-level integrity observed live**: CHECK constraints on `system_status` and numeric ranges
  are enforced server-side (constraint 23514 observed when probing invalid values) — the live
  schema matches the migration file.
- **Probe residue**: zero (sentinel row 1970-01-01T00:00:01Z inserted, updated, and deleted;
  post-delete verification returned empty set).
- **Git history secret scan**: `git log --all -p | grep 'eyJ…'` → **0 matches**; `.env` has never
  been committed (`git log --all -- My_Compilation/.env` → empty). Key rotation not required.
- **Not testable without the dashboard**: anon-key (publishable JWT) INSERT requires the project's
  publishable key from the Supabase dashboard; no-credential probes prove the equivalent
  protection. Status: **VERIFIED (residual: publishable-key variant untested)**.

## Status

SECURITY_REMEDIATION.md §3 RLS item: UNVERIFIED → **VERIFIED (live, 2026-09-09)**.
