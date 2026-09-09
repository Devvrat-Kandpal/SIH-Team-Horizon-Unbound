# Visual Regression & Live Multi-Client Verification (Phases 4–5)

**Date**: 2026-09-09 · **Method**: live uvicorn instance (real physics, real Supabase
ingestion active — HTTP 201s observed during the run) + scripted two-client
WebSocket session.

## Phase 4 — Static frontend integrity (automated portion)

| Check | Result |
|---|---|
| `GET /` (index.html) | 200, 27,657 bytes |
| `GET /chart_v4.js` (bundled chart lib) | 200, 205,214 bytes |
| Frontend asset references resolve | PASS |

Note: static route rejects HTTP HEAD (405); GET probes used instead. No missing
assets, no CDN dependencies.

## Phase 5 — Live two-client coherence (external verification CLOSED)

Scripted against a real server (not TestClient):

| Step | Expected (documented single-chamber design) | Observed |
|---|---|---|
| Client B: `set_scenario=thermal_drift` (WS, operator role) | Client A observes drift | ✅ PASS |
| Client A: `reset` (WS, operator role) | Client B observes return to nominal | ✅ PASS |

Matches `tests/test_multi_client_interference.py` (TestClient) — the coherence
behavior is verified both in-process and against a live uvicorn server.
Model B / Phase 6 scope evidence: `reports/degradation_model_comparison.md`.

## Phase 4 — MANUAL browser checklist (requires human; not automatable here)

To be executed by the team before the SIH demo; record ✗/✎ next to each:

1. Open the dashboard in Chrome/Edge at 1920×1080 and 1366×768.
2. Nominal: charts render, dual-axis labels/units visible, frames update ~1.25 Hz.
3. Outlier → drift → short: chart curves respond; alert feed populates with
   fault-type labels; criticality indicator matches server.
4. Reset: charts keep flowing (commit f411134), alert feed clears (b28c72a),
   no stale anomaly state.
5. CSV/JSON export buttons produce files from the session buffer.
6. Invalid API key: connection rejected, UI shows offline/error state.
7. Two browser windows: both mirror the same chamber (Phase 5 behavior).
8. No console errors during a full scenario cycle.

**Status**: automated portion PASS; manual portion UNVERIFIED (requires browser).
