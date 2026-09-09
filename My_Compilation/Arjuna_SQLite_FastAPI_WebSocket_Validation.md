# Project Arjuna — SQLite Write Speed, FastAPI Latency & WebSocket Resilience

Method note up front, because it shapes everything below: `Backend/main.py` cannot be imported
as committed (missing `get_next_telemetry_frame`/`reset_simulator` in `simulator.py` — established
in the previous report). To actually load-test the real routes and detectors rather than give up,
I made a **working copy** of `Backend/` and appended a disclosed, clearly-marked test-only shim
providing those two missing functions from the real `ComponentSimulator`, then ran the real
`uvicorn main:app` process and hit it over real loopback HTTP/WebSocket connections — not
`TestClient`, not mocks. Every number below is from that live process. This is a workaround for
testing purposes only; it doesn't fix the underlying bug, which still needs a real fix in the repo.

---

## 1. SQLite

**First finding: the deployed backend doesn't use SQLite at all.** `Backend/database.py` is
Supabase-only — there is no SQLite persistence path anywhere in `Backend/`. The only working
SQLite code in the whole repo is `simulation/simulator.py`'s `export_to_sqlite()`, a batch
CSV→SQLite export utility (also referenced by `Backend/test_member2.py`, which — consistent with
the pattern found in the previous report — imports `export_to_sqlite` from `Backend/simulator.py`
where it **doesn't exist**, so that test also fails to collect). Given the request, I benchmarked
two things: (a) the actual `export_to_sqlite` bulk-export utility as the closest real code to test,
and (b) the access pattern the system would need if SQLite ever replaced Supabase as the live
telemetry sink — a single-row insert every 100ms.

### 1a. Bulk CSV → SQLite export (`simulation/simulator.py::export_to_sqlite`)

| Rows | Wall time | Throughput |
|---|---|---|
| 1,000 | 20.9 ms | 47,934 rows/sec |
| 5,000 | 43.8 ms | 114,270 rows/sec |
| 20,000 | 147.3 ms | 135,757 rows/sec |
| 50,000 | 321.0 ms | 155,772 rows/sec |

Throughput improves with batch size (fixed per-call overhead amortizes) and plateaus around
~150K rows/sec — fine for its actual use case (offline export of a completed dataset), not
relevant to live-streaming performance.

### 1b. Simulated live per-frame write (the pattern that *would* matter if SQLite replaced Supabase)

Single-row `INSERT` + `commit()` per call, N=500, mimicking one call per 100ms WebSocket tick:

| Mode | mean | p50 | p95 | p99 | max |
|---|---|---|---|---|---|
| Default journal mode | 0.442 ms | 0.415 ms | 0.557 ms | 0.734 ms | 4.802 ms |
| WAL mode | 0.185 ms | 0.175 ms | 0.273 ms | 0.400 ms | 1.013 ms |

Both comfortably fit inside the 100 ms frame budget — even the worst observed single insert
(4.8 ms, default mode) is <5% of the budget. See `sqlite_perf.png`. **If persistence reliability is
a concern (the previous report flagged `database.py` has zero test coverage and no verified
Supabase-outage fallback), SQLite would be a fast, simple, dependency-free alternative for the live
path** — no network round-trip, no external service to be unreachable. One caveat: `sqlite3` calls
are synchronous/blocking, and `main.py`'s WebSocket loop is `async def` — a direct `conn.execute()`
call inside that loop would block the single asyncio event loop for however long the write takes.
At <5ms worst-case that's a minor, bounded stall, not a functional problem, but it should go
through `asyncio.to_thread()` or a dedicated writer thread rather than being called inline, to
avoid it compounding under concurrent WebSocket load (see §3).

---

## 2. FastAPI HTTP Latency

### 2a. Single-request baseline (real HTTP, loopback, live uvicorn process, N=200 each)

| Endpoint | mean | p50 | p95 | p99 | max |
|---|---|---|---|---|---|
| `GET /` | 1.08 ms | 1.05 ms | 1.26 ms | 2.13 ms | 4.03 ms |
| `GET /api/status` | 1.15 ms | 1.13 ms | 1.41 ms | 1.59 ms | 1.68 ms |
| `GET /api/history?limit=50` | 1.13 ms | 1.10 ms | 1.41 ms | 1.65 ms | 1.78 ms |
| `POST /api/inject-fault` | 1.52 ms | 1.49 ms | 1.81 ms | 1.98 ms | 2.47 ms |
| `POST /api/reset` | 1.17 ms | 1.14 ms | 1.38 ms | 1.70 ms | 1.77 ms |

Excellent single-request latency — all endpoints comfortably sub-2ms.

### 2b. Concurrent load — a methodology correction worth keeping visible

My first pass at concurrent load testing (50-way concurrency, new `httpx.Client()` per request)
showed throughput capped at ~34 req/sec with tail latency over 1.6 seconds — a scary number. Before
writing that up as a server-side bottleneck, I re-ran the identical test with a single
**connection-pooled** client instead of opening a fresh TCP connection per request, and the result
changed completely:

| Concurrency | Throughput | p50 | p95 |
|---|---|---|---|
| 5 | 614.8 req/s | 5.6 ms | 17.1 ms |
| 20 | 561.0 req/s | 21.2 ms | 86.8 ms |
| 50 | 878.0 req/s | 49.7 ms | 65.0 ms |
| 100 | 808.3 req/s | 104.9 ms | 121.9 ms |

**The ~34 req/sec figure was an artifact of my own test harness** (TCP handshake overhead per
request, not the server) — worth stating plainly rather than silently fixing, since it's exactly
the kind of number that looks alarming and would be wrong to report. The real picture (chart:
`rest_throughput.png`): the server sustains **500-900 req/sec**, with p50 latency scaling roughly
linearly with concurrency (5ms → 105ms from 5 to 100 concurrent clients). That scaling is
consistent with FastAPI's default behavior for **synchronous** route handlers — every REST route
in `main.py` (`root`, `inject_fault`, `reset_system`, `get_history`, `get_system_status`) is
defined as plain `def`, not `async def`, so each request runs in Starlette's bounded worker thread
pool rather than directly on the event loop. None of these handlers do anything that actually
requires blocking I/O in the hot path (state-dict reads, Pydantic model construction) — converting
them to `async def` would let them run directly on the event loop and likely remove this scaling
ceiling entirely, since there's no real work per call.

---

## 3. WebSocket Resilience Under Load

### 3a. Sustained frame rate vs. the 10 FPS target

Single connection, 8 seconds, real inter-frame timestamps:

```
frames received: 77 in ~8s -> actual rate: 9.62 FPS (target 10 FPS)
inter-frame interval: mean=105.28ms  p50=105.00ms  p95=107.54ms  max=108.51ms  min=104.07ms
```

This confirms a gap flagged (but not measured) in the first benchmarks report: the loop does
`asyncio.sleep(0.1)` **after** doing the frame's work (simulator step, Module A/B, CUSUM, JSON
send), so the true period is 100ms + processing time, not a flat 100ms. Measured overshoot is a
consistent, bounded ~5% (105ms actual vs 100ms nominal) — small, predictable, not alarming, but
worth knowing if anything downstream assumes exactly 10.0 Hz.

### 3b. Frame rate under concurrent connections — holds up well

| Concurrent clients | Per-client FPS (mean) |
|---|---|
| 1 | 9.67 |
| 5 | 9.83 |
| 10 | 9.83 |
| 20 | 9.67 |

No measurable degradation from 1 to 20 simultaneous dashboard connections — each connection runs
its own independent loop task, and the per-tick CPU cost (detector inference, well under 1ms per
the earlier edge-case report) is cheap enough that 20 concurrent loops don't meaningfully compete
for the event loop. Good result.

### 3c. Rapid connect/disconnect churn — clean

100 back-to-back connect → receive one frame → disconnect cycles completed in 0.93 seconds with
**zero errors**, and the server was fully healthy (`/api/status` → 200) immediately afterward. No
sign of connection-handling resource leaks or accumulating broken state.

### 3d. Slow-reader / backpressure — clean

Connected a client that never called `recv()` for 15 seconds (server would have attempted ~150
sends into a socket nobody was draining). Server RSS memory was **identical before and after**
(191.9MB → 191.9MB, 0.0MB delta) and remained fully responsive to REST calls afterward. This
indicates `websocket.send_json()` backpressure is being handled correctly at the transport level
(the per-connection loop naturally stalls waiting for socket buffer space, rather than the
application buffering unsent frames in memory) — a real resilience strength worth keeping.

### 3e. REST input validation fuzzing — robust, with one minor dead-code note

Malformed fault-injection bodies (missing field, wrong type, `null`, empty string, a
SQL-injection-shaped string) all correctly returned `422` with a clear Pydantic error, no crashes,
no 500s. One thing worth a quick look: the `event_type` field is typed `Literal["ELECTRICAL_SPIKE",
"ELECTRICAL_SHORT_CIRCUIT", "THERMAL_DRIFT"]`, and there's *also* a custom `@field_validator` that
normalizes casing via `v.upper()` before checking membership. Because Pydantic enforces the
`Literal` type constraint first, a lowercase value like `"electrical_spike"` is rejected at the
type-validation stage and **never reaches** the custom validator — so the case-normalization logic
is unreachable as written. Minor (strict-casing-only is a perfectly reasonable API choice), but if
case-insensitive input was the intent, the `Literal` needs to be relaxed to `str` for the custom
validator to ever run.

---

## Summary

| Area | Verdict |
|---|---|
| SQLite (bulk export) | Fast for its actual use case (~150K rows/sec at scale); not on the live path today |
| SQLite (simulated live 10Hz writes) | Sub-5ms worst case — would comfortably replace Supabase on performance grounds alone if reliability motivates the switch (needs `to_thread` to avoid blocking the loop) |
| FastAPI REST latency (single request) | Excellent — sub-2ms across all endpoints |
| FastAPI REST throughput (concurrent) | Real number is 500-900 req/s, not the ~34 req/s a naive per-request-connection test suggested; latency scaling under load is explained by sync `def` handlers going through the thread pool — converting to `async def` would likely remove the ceiling |
| WebSocket frame rate | ~9.62-9.83 FPS actual vs. 10 FPS nominal (small, consistent, explained overshoot) |
| WebSocket under concurrency | No degradation observed up to 20 simultaneous connections |
| WebSocket churn / backpressure | Clean on both — no leaks, no crashes, no unbounded buffering |
| REST input validation | Robust against malformed/hostile input; one small dead-code note on case normalization |

The one number in this report that materially matters for planning is **not** a resilience
failure — it's the REST throughput methodology correction (§2b), included specifically because an
uncorrected version of that number would have been the loudest, scariest, and wrongest thing in
this report.

*Live-tested against a locally patched copy of this cloned repo (uvicorn on loopback, no real
network, no concurrent hardware contention) — real-world numbers over an actual network or on the
target deployment hardware may differ; worth re-running this suite once `main.py`'s import bug is
fixed for real, so it can be tested without a workaround shim.*
