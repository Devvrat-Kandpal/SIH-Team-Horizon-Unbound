""""
tests/test_supabase_rls.py — Project ARJUNA (SIH 26170)

Static security-scan regression tests for the Supabase migration only
(P0-04, P0-05, P1-17). No live database is required: we assert the *shipped*
SQL contains the hardened policy statements so a regression cannot silently
re-introduce the open INSERT or unsecured SECURITY DEFINER function.

If a live Supabase is ever available, these should be supplemented with real
policy-enforcement tests (see scripts/check_supabase_rls.py).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "migrations" / "supabase_schema.sql"
SQL = MIGRATION.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION.exists(), "migrations/supabase_schema.sql is missing"


def test_telemetry_insert_is_service_role_only():
    """Arbitrary authenticated users must NOT be able to INSERT telemetry (P0-05)."""
    assert "Allow backend ingestion into telemetry" in SQL
    # The telemetry INSERT policy must target only service_role.
    assert "TO service_role" in SQL
    # Hard fail: 'authenticated' must not appear in the telemetry INSERT policy block.
    insert_block = SQL.split("Allow backend ingestion into telemetry", 1)[1].split(";", 1)[0]
    assert "authenticated" not in insert_block, (
        "telemetry INSERT policy must not grant 'authenticated' (P0-05)"
    )


def test_cleanup_function_is_locked_down():
    """SECURITY DEFINER cleanup function must be locked down (P0-04)."""
    assert "REVOKE ALL ON FUNCTION public.cleanup_old_telemetry(INT) FROM PUBLIC;" in SQL
    assert "SET search_path = pg_catalog, public;" in SQL
    assert "GRANT EXECUTE ON FUNCTION public.cleanup_old_telemetry(INT) TO service_role;" in SQL


def test_public_select_is_explicitly_demo_policy():
    """Public SELECT is retained ONLY as an explicit demo policy (P1-17)."""
    assert "DEMO POLICY" in SQL
    # public SELECT policies remain (demo), but INSERT is locked to service_role.
    assert "Allow public read access to telemetry" in SQL
