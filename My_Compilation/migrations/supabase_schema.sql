-- ==============================================================================
-- PROJECT ARJUNA (SIH 26170): PRODUCTION SUPABASE DATABASE SCHEMA
-- ECSS-Q-ST-60-02C Space Product Assurance Telemetry & Event Persistence
-- ==============================================================================
-- INSTRUCTIONS FOR SETUP IN SUPABASE:
-- 1. Open your Supabase Project Dashboard (https://supabase.com/dashboard)
-- 2. Click on the "SQL Editor" icon (>_) in the left navigation sidebar.
-- 3. Click "New query", paste the entire content of this script, and click "Run".
-- 4. Verify tables "telemetry_logs" and "system_events" appear under Table Editor.
-- ==============================================================================

-- 1. TELEMETRY LOGS TABLE
-- Stores individual high-frequency burn-in chamber telemetry frames
CREATE TABLE IF NOT EXISTS public.telemetry_logs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    voltage DOUBLE PRECISION NOT NULL,
    current DOUBLE PRECISION NOT NULL,
    temperature DOUBLE PRECISION NOT NULL,
    iddq_uA DOUBLE PRECISION NOT NULL DEFAULT 10.0,
    prop_delay DOUBLE PRECISION DEFAULT 4.50,
    anomaly_score DOUBLE PRECISION NOT NULL DEFAULT 0.03,
    isolation_anomaly BOOLEAN NOT NULL DEFAULT FALSE,
    drift_anomaly BOOLEAN NOT NULL DEFAULT FALSE,
    fault_type TEXT NOT NULL DEFAULT 'NORMAL',
    criticality_level SMALLINT NOT NULL DEFAULT 2 CHECK (criticality_level IN (1, 2, 3)),
    system_status TEXT NOT NULL DEFAULT 'NOMINAL' CHECK (system_status IN ('NOMINAL', 'ANOMALY', 'WARNING')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. SYSTEM EVENTS TABLE
-- Stores audit logs, fault injections, chamber resets, and criticality adjustments
CREATE TABLE IF NOT EXISTS public.system_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'INFO' CHECK (severity IN ('INFO', 'WARNING', 'HIGH', 'CRITICAL')),
    message TEXT NOT NULL,
    criticality_level SMALLINT DEFAULT 2 CHECK (criticality_level IN (1, 2, 3))
);

-- ==============================================================================
-- 3. HIGH-THROUGHPUT PERFORMANCE INDEXES
-- Essential for real-time querying, history pagination, and judge demonstrations
-- ==============================================================================

CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp 
    ON public.telemetry_logs (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_telemetry_status 
    ON public.telemetry_logs (system_status);

CREATE INDEX IF NOT EXISTS idx_telemetry_fault 
    ON public.telemetry_logs (fault_type);

CREATE INDEX IF NOT EXISTS idx_telemetry_criticality 
    ON public.telemetry_logs (criticality_level);

CREATE INDEX IF NOT EXISTS idx_events_created 
    ON public.system_events (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_events_type 
    ON public.system_events (event_type);

-- ==============================================================================
-- 4. ROW-LEVEL SECURITY (RLS) POLICIES
-- Protects data integrity while enabling seamless backend streaming & frontend queries
-- ==============================================================================

ALTER TABLE public.telemetry_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_events ENABLE ROW LEVEL SECURITY;

-- Allow public read access (for judges, dashboards, and evaluation queries)
DROP POLICY IF EXISTS "Allow public read access to telemetry" ON public.telemetry_logs;
CREATE POLICY "Allow public read access to telemetry"
    ON public.telemetry_logs FOR SELECT
    TO anon, authenticated
    USING (true);

DROP POLICY IF EXISTS "Allow public read access to events" ON public.system_events;
CREATE POLICY "Allow public read access to events"
    ON public.system_events FOR SELECT
    TO anon, authenticated
    USING (true);

-- Allow backend ingestion (Restricts INSERT to authenticated or service_role)
-- NOTE: For production, the FastAPI backend must use the service_role key to insert.
DROP POLICY IF EXISTS "Allow ingestion into telemetry" ON public.telemetry_logs;
CREATE POLICY "Allow ingestion into telemetry"
    ON public.telemetry_logs FOR INSERT
    TO authenticated, service_role
    WITH CHECK (true);

DROP POLICY IF EXISTS "Allow ingestion into events" ON public.system_events;
CREATE POLICY "Allow ingestion into events"
    ON public.system_events FOR INSERT
    TO authenticated, service_role
    WITH CHECK (true);

-- ==============================================================================
-- 5. AUTOMATED DATA RETENTION CLEANUP (MAINTENANCE FUNCTION)
-- Optional maintenance function to purge old telemetry while keeping latest records
-- ==============================================================================

CREATE OR REPLACE FUNCTION public.cleanup_old_telemetry(days_to_keep INT DEFAULT 14)
RETURNS INT AS $$
DECLARE
    deleted_count INT;
BEGIN
    DELETE FROM public.telemetry_logs
    WHERE timestamp < NOW() - (days_to_keep || ' days')::INTERVAL;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Verification commentary
COMMENT ON TABLE public.telemetry_logs IS 'Project ARJUNA: Real-time High-Temperature Operating Life (HTOL) burn-in sensor logs';
COMMENT ON TABLE public.system_events IS 'Project ARJUNA: Audit log of fault injections, chamber resets, and criticality transitions';

