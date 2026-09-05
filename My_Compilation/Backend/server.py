import asyncio
import json
import logging
import math
import random
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

logger = logging.getLogger("project_arjuna.backend")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# Add Member directories to Python path
CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
BACKEND_DIR = ROOT_DIR / "Backend"
MODEL_DIR = ROOT_DIR / "Model"
SIM_DIR = ROOT_DIR / "simulation"
FRONTEND_DIR = ROOT_DIR / "Frontend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from Backend.criticality_config import CRITICALITY_CONFIG
    from Backend.cusum_drift import DriftDetector
    from Backend.database import get_recent_telemetry, insert_telemetry, log_event, telemetry_store
    from Backend.isolation_forest import LinearRegressionDriftPredictor, MultivariateAnomalyDetector
    from Backend.schemas import FaultInjectionRequest
    from Backend.security import ALLOWED_ORIGINS, get_security_status, verify_operator_access, verify_websocket_auth
    from Backend.simulator import ComponentSimulator
except ImportError:
    from cusum_drift import DriftDetector
    from database import get_recent_telemetry, insert_telemetry, log_event, telemetry_store
    from isolation_forest import LinearRegressionDriftPredictor, MultivariateAnomalyDetector
    from schemas import FaultInjectionRequest
    from security import ALLOWED_ORIGINS, get_security_status, verify_operator_access, verify_websocket_auth
    from simulator import ComponentSimulator

    from criticality_config import CRITICALITY_CONFIG

# Global Model & State
# NOTE: These are lazily-initialized process globals, set in get_or_train_model() during
# app lifespan. The explicit `None` sentinel is intentional (module load time); pyright is
# told to ignore the false "None not assignable" / "None has no attribute" diagnostics.
model: MultivariateAnomalyDetector = None  # type: ignore[assignment]
drift_predictor: LinearRegressionDriftPredictor = None  # type: ignore[assignment]
current_scenario = "nominal"
burn_in_hours = 0

# DESIGN NOTE — Single-DUT shared chamber state (intentional):
# All WebSocket clients share one virtual burn-in chamber state (current_scenario,
# burn_in_hours, _server_criticality_level). This models a single-DUT test bench where
# every observer/operator sees the SAME chamber — a deliberate single-source-of-truth
# design so fault injections, resets, and criticality changes are globally coherent.
# Per-session / multi-DUT isolation is a future enhancement and is NOT implemented.

# Server-side criticality level — single source of truth.
# All WebSocket sessions read from this; the frontend is always synced back via telemetry.
_server_criticality_level: int = 2
_requested_scenario: str = "nominal"
_reset_generation: int = 0
_rest_control_generation: int = 0
_last_telemetry: dict = {}
STATE_FILE = BACKEND_DIR / "app_state_backup.json"
persistence_queue: asyncio.Queue | None = None
persistence_worker_task: asyncio.Task | None = None
persist_dropped_count = 0

VALID_SCENARIOS = {"nominal", "isro_outlier", "thermal_drift", "electrical_short"}
TEAM_FAULT_SCENARIOS = {
    "ELECTRICAL_SPIKE": "isro_outlier",
    "SPIKE": "isro_outlier",
    "ELECTRICAL_SHORT_CIRCUIT": "electrical_short",
    "SHORT": "electrical_short",
    "SHORT_CIRCUIT": "electrical_short",
    "ELECTRICAL_SHORT": "electrical_short",
    "THERMAL_DRIFT": "thermal_drift",
    "DRIFT": "thermal_drift",
}


async def _persistence_worker() -> None:
    while True:
        kind, payload = await persistence_queue.get()  # type: ignore[attr-defined]
        try:
            if kind == "telemetry":
                await asyncio.to_thread(insert_telemetry, payload)
            elif kind == "event":
                await asyncio.to_thread(log_event, *payload)
        except Exception:
            logger.exception("Persistence operation failed; live telemetry continues")
        finally:
            persistence_queue.task_done()  # type: ignore[attr-defined]


async def _enqueue_persistence(kind: str, payload) -> None:
    global persist_dropped_count
    if persistence_queue is None:
        if kind == "telemetry":
            await asyncio.to_thread(insert_telemetry, payload)
        else:
            await asyncio.to_thread(log_event, *payload)
        return
    try:
        persistence_queue.put_nowait((kind, payload))
    except asyncio.QueueFull:
        try:
            persistence_queue.get_nowait()
            persistence_queue.task_done()
        except asyncio.QueueEmpty:
            pass
        persistence_queue.put_nowait((kind, payload))
        persist_dropped_count += 1


def _load_compatibility_state() -> None:
    global _requested_scenario, _last_telemetry
    if not STATE_FILE.exists():
        return
    try:
        saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        scenario = saved.get("scenario", "nominal")
        if scenario in VALID_SCENARIOS:
            _requested_scenario = scenario
        _last_telemetry = saved.get("last_telemetry", {})
    except (OSError, json.JSONDecodeError, TypeError):
        pass


def _save_compatibility_state() -> None:
    try:
        STATE_FILE.write_text(
            json.dumps(
                {
                    "scenario": _requested_scenario,
                    "last_telemetry": _last_telemetry,
                }
            ),
            encoding="utf-8",
        )
    except OSError:
        pass


def get_or_train_model():
    global model, drift_predictor
    model_path = MODEL_DIR / "isolation_forest_model.joblib"
    sample_csv = MODEL_DIR / "sample_data.csv"

    if not model_path.exists():
        logger.info("Serialized model not found. Training on %s", sample_csv)
        if not sample_csv.exists():
            try:
                from Backend.simulator import generate_dataset
            except ImportError:
                from simulator import generate_dataset

            generate_dataset(str(sample_csv), n_normal=10000, n_drift=0, n_short=0)

        detector = MultivariateAnomalyDetector(contamination=0.001, n_estimators=40)
        detector.train(str(sample_csv))
        detector.save_model(str(model_path))
        model = detector
    else:
        logger.info("Loading trained model from %s", model_path)
        model = MultivariateAnomalyDetector.load_model(str(model_path))

    # Initialise Module B with the real lot statistics from the trained model
    lot_mean = model.lot_stats.get("mean_iddq", 10.0)
    lot_std = model.lot_stats.get("std_iddq", 1.17)
    drift_predictor = LinearRegressionDriftPredictor(
        lot_mean_iddq=lot_mean, lot_std_iddq=lot_std
    )
    logger.info(
        "Drift predictor ready (lot mean %.2f uA, sigma %.2f uA)", lot_mean, lot_std
    )
    logger.info("Isolation Forest model ready")
    return model


@asynccontextmanager
async def lifespan(app: FastAPI):
    global persistence_queue, persistence_worker_task
    _load_compatibility_state()
    get_or_train_model()
    persistence_queue = asyncio.Queue(maxsize=1000)
    persistence_worker_task = asyncio.create_task(_persistence_worker())
    try:
        yield
    finally:
        _save_compatibility_state()
        if persistence_queue:
            try:
                await asyncio.wait_for(persistence_queue.join(), timeout=2.0)
            except TimeoutError:
                logger.warning("Persistence queue did not drain before shutdown")
        if persistence_worker_task:
            persistence_worker_task.cancel()
            try:
                await persistence_worker_task
            except asyncio.CancelledError:
                pass
        persistence_worker_task = None
        persistence_queue = None


app = FastAPI(
    title="Project ARJUNA (SIH 26170) - Integration Server",
    description="Live WebSocket bridge connecting Member 1 (Frontend UI) and Member 3 (Multivariate ML Model)",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API Health & Lot Stats
@app.get("/api/health")
async def health_check():
    global model
    return {
        "status": "healthy",
        "project": "ARJUNA-SIH-26170",
        "service": "Project ARJUNA Integration Server",
        "standard": "ECSS-Q-ST-60-02C Space Product Assurance",
        "model_loaded": model is not None and model.is_trained,
        "current_scenario": current_scenario,
        "criticality_level": _server_criticality_level,
        "lot_stats": model.lot_stats if model else {},
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/api/status")
async def status_check():
    """Team-compatible operational status view."""
    active_fault = _last_telemetry.get("fault_type")
    if active_fault == "NORMAL":
        active_fault = None
    return {
        "backend_status": "ONLINE",
        "system_status": _last_telemetry.get(
            "system_status", "ANOMALY" if active_fault else "NOMINAL"
        ),
        "operational": True,
        "active_fault": active_fault,
        "current_scenario": _requested_scenario,
        "model_loaded": model is not None and model.is_trained,
        "inject_spike": _requested_scenario == "isro_outlier",
        "inject_short": _requested_scenario == "electrical_short",
        "inject_drift": _requested_scenario == "thermal_drift",
        "burn_in_hours": _last_telemetry.get("burn_in_hours", 0.0),
        "criticality_level": _server_criticality_level,
        "persistence": telemetry_store.get_status(),
        "security": get_security_status(),
    }


@app.get("/api/history")
async def telemetry_history(limit: int = 100, fault_type: str | None = None):
    """Return recent Supabase telemetry or the offline local history fallback with optional fault filtering."""
    return get_recent_telemetry(limit=max(1, min(limit, 1000)), fault_type=fault_type)


@app.get("/telemetry/history")
async def legacy_telemetry_history(limit: int = 100, fault_type: str | None = None):
    return await telemetry_history(limit, fault_type)


@app.get("/api/events")
async def system_events(limit: int = 50):
    """Return recent audit and system events from persistence."""
    return telemetry_store.recent_events(limit=max(1, min(limit, 200)))


def _set_requested_scenario(scenario: str) -> None:
    global _requested_scenario, _rest_control_generation
    if scenario not in VALID_SCENARIOS:
        raise ValueError(f"Unsupported scenario: {scenario}")
    _requested_scenario = scenario
    _rest_control_generation += 1
    _save_compatibility_state()


@app.post("/api/inject-fault")
async def inject_fault(request: Request):
    """Team-compatible REST fault control mapped to My's scenarios with operator security validation."""
    await verify_operator_access(request)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=422, content={"error": "Invalid JSON body"})
    if not isinstance(body, dict):
        return JSONResponse(
            status_code=422, content={"error": "event_type is required"}
        )
    try:
        fault = FaultInjectionRequest(**body)
        event_type = fault.get_event_type()
    except Exception as ve:
        return JSONResponse(status_code=400, content={"error": str(ve)})

    scenario = TEAM_FAULT_SCENARIOS.get(event_type)
    if not scenario:
        return JSONResponse(
            status_code=400, content={"error": f"Unknown fault type: {event_type}"}
        )
    _set_requested_scenario(scenario)
    await _enqueue_persistence(
        "event", (event_type, "HIGH", f"Fault injection requested: {event_type}")
    )
    return {
        "ok": True,
        "active_fault": event_type,
        "fault_type": event_type,
        "scenario": scenario,
    }


@app.post("/api/reset")
async def reset_system(request: Request):
    global _requested_scenario, _reset_generation, _rest_control_generation
    await verify_operator_access(request)
    _requested_scenario = "nominal"
    _reset_generation += 1
    _rest_control_generation += 1
    _save_compatibility_state()
    await _enqueue_persistence("event", ("RESET", "INFO", "System reset requested"))
    return {"ok": True, "status": "RESET_REQUESTED", "scenario": "nominal"}


@app.post("/scenario/fault")
async def legacy_fault(request: Request):
    return await inject_fault(request)


@app.post("/system/reset")
async def legacy_reset(request: Request):
    return await reset_system(request)


@app.get("/api/lot-stats")
async def get_lot_stats():
    global model
    if model is None:
        model = get_or_train_model()
    if not model or not model.is_trained:
        return JSONResponse(status_code=503, content={"error": "Model not loaded"})
    return model.lot_stats


# ─────────────────────────────────────────────────────────────
# CRITICALITY LEVEL API — server is the single source of truth
# ─────────────────────────────────────────────────────────────


@app.get("/api/criticality")
async def get_criticality():
    """Returns the current server-side criticality level (1/2/3).
    Frontend fetches this on page load and after reconnect to stay in sync.
    Prevents silent reset to default 2 after WebSocket reconnection."""
    cfg = CRITICALITY_CONFIG[_server_criticality_level]
    return {
        "criticality_level": _server_criticality_level,
        "label": cfg["fault_label"],
        "description": cfg["description"],
        "cusum_threshold": cfg["cusum_threshold"],
        "if_score_threshold": cfg["if_score_threshold"],
    }


@app.post("/api/set-criticality")
async def set_criticality(request: Request):
    """Sets the server-side criticality level. Only 1, 2, or 3 are accepted.
    Rejects everything else with HTTP 422. Protected by operator access validation."""
    global _server_criticality_level
    await verify_operator_access(request)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=422,
            content={
                "error": "Request body must be valid JSON with 'criticality_level' key."
            },
        )
    if not isinstance(body, dict):
        return JSONResponse(
            status_code=422,
            content={
                "error": "Request body must be a JSON object with 'criticality_level'."
            },
        )
    level = body.get("criticality_level")
    # Strict validation — must be a Python int in {1, 2, 3}. Reject floats, strings, None, NaN.
    if not isinstance(level, int) or isinstance(level, bool) or level not in (1, 2, 3):
        return JSONResponse(
            status_code=422,
            content={
                "error": f"Invalid criticality_level={level!r}. Must be integer 1, 2, or 3.",
                "valid_values": [1, 2, 3],
                "convention": "1=low-criticality, 2=standard, 3=mission-critical",
            },
        )
    _server_criticality_level = level
    cfg = CRITICALITY_CONFIG[level]
    logger.info(
        "Criticality level updated to %s (%s); CUSUM threshold=%s, IF score gate=%s",
        level,
        cfg["fault_label"],
        cfg["cusum_threshold"],
        cfg["if_score_threshold"],
    )
    return {
        "ok": True,
        "criticality_level": level,
        "label": cfg["fault_label"],
        "description": cfg["description"],
        "cusum_threshold": cfg["cusum_threshold"],
        "if_score_threshold": cfg["if_score_threshold"],
    }


# Serve Member-1 Static Dashboard with strict No-Cache Headers
def no_cache_file(path, media_type=None):
    res = FileResponse(path, media_type=media_type)
    res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    res.headers["Pragma"] = "no-cache"
    res.headers["Expires"] = "0"
    return res


@app.get("/")
async def serve_dashboard():
    return no_cache_file(str(FRONTEND_DIR / "index.html"), media_type="text/html")


@app.get("/styles.css")
async def serve_css():
    return no_cache_file(str(FRONTEND_DIR / "styles.css"), media_type="text/css")


@app.get("/script.js")
async def serve_js():
    return no_cache_file(str(FRONTEND_DIR / "script.js"), media_type="text/javascript")


@app.get("/chart_v4.js")
async def serve_chart():
    return no_cache_file(
        str(FRONTEND_DIR / "chart_v4.js"), media_type="application/javascript"
    )


@app.get("/space.jpg")
async def serve_logo():
    return no_cache_file(str(FRONTEND_DIR / "space.jpg"), media_type="image/jpeg")


# =========================================================
# REAL-TIME WEBSOCKET TELEMETRY & ML EVALUATION BRIDGE
# =========================================================
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            "WebSocket client connected; active=%s", len(self.active_connections)
        )

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(
            "WebSocket client disconnected; active=%s", len(self.active_connections)
        )

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


@app.websocket("/ws")
@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    global model, _last_telemetry, _requested_scenario, _rest_control_generation
    auth_ctx = await verify_websocket_auth(websocket)
    if auth_ctx is None:
        return

    if model is None:
        model = get_or_train_model()
    await manager.connect(websocket)

    current_scenario = _requested_scenario
    observed_rest_control_generation = _rest_control_generation
    burn_in_hours = 0.0
    tick_count = 0
    last_scenario = "nominal"

    lot_mean = (
        model.lot_stats.get("mean_iddq", 10.0) if model and model.lot_stats else 10.0
    )
    lot_std = (
        model.lot_stats.get("std_iddq", 1.17) if model and model.lot_stats else 1.17
    )
    drift_predictor = LinearRegressionDriftPredictor(
        lot_mean_iddq=lot_mean, lot_std_iddq=lot_std
    )

    # ComponentSimulator and CUSUM are initialised with the current server criticality level.
    # criticality_level is read from the global at each tick so live updates propagate.
    component_sim = ComponentSimulator(criticality_level=_server_criticality_level)
    cusum_detector = DriftDetector(
        metric_name="Iddq",
        mean=lot_mean,
        std=lot_std,
        criticality_level=_server_criticality_level,
        # Per-DUT auto-baseline: reference is re-calibrated to THIS component's own
        # first readings (robust median, 15-tick INITIALIZING phase), so natural
        # lot spread cannot accumulate as false drift. Drift is then measured from
        # the part itself — standard HTOL practice (t=0 self-characterization).
        auto_baseline=True,
        baseline_window=15,
    )

    # State variables for simulation stream
    sim_v = 5.0
    sim_c = 1.20
    sim_t = 125.0
    sim_iddq = 10.0
    sim_pd = 4.5

    is_running = True

    # Task to listen for incoming client commands (e.g. scenario triggers)
    async def receive_commands():
        global _requested_scenario
        nonlocal is_running, current_scenario, burn_in_hours, sim_v, sim_c, sim_t, sim_iddq, sim_pd
        try:
            while is_running:
                data_text = await websocket.receive_text()
                try:
                    payload = json.loads(data_text)
                    action = payload.get("action")
                    if action == "set_scenario":
                        requested = payload.get("scenario", "nominal")
                        if requested in VALID_SCENARIOS:
                            current_scenario = requested
                        logger.info("Scenario switched to %s", current_scenario)
                    elif action == "reset":
                        current_scenario = "nominal"
                        burn_in_hours = 0.0
                        component_sim.reset()
                        # Re-sync criticality from server global before reset — ensures
                        # CUSUM threshold reflects any changes made via /api/set-criticality
                        component_sim.criticality_level = _server_criticality_level
                        cusum_detector.update_criticality(_server_criticality_level)
                        cusum_detector.reset()
                        if drift_predictor:
                            drift_predictor.reset()
                        sim_v = 5.0
                        sim_c = 1.20
                        sim_t = 125.0
                        sim_iddq = 10.0
                        sim_pd = 4.5
                        logger.info("Chamber telemetry reset")
                except json.JSONDecodeError:
                    pass
        except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
            is_running = False
        except Exception:
            is_running = False

    receiver_task = asyncio.create_task(receive_commands())

    try:
        while is_running:
            tick_count += 1

            # REST controls update the active WebSocket without changing the
            # simulator or detector implementation.
            if observed_rest_control_generation != _rest_control_generation:
                current_scenario = _requested_scenario
                observed_rest_control_generation = _rest_control_generation

            # Live-sync criticality from server global on every tick.
            # This ensures that /api/set-criticality takes effect within 0.8s without
            # requiring a WebSocket reconnect or explicit reset command.
            active_criticality = _server_criticality_level
            if component_sim.criticality_level != active_criticality:
                component_sim.criticality_level = active_criticality
                cusum_detector.update_criticality(active_criticality)
                logger.info("Live criticality sync -> level %s", active_criticality)

            # Reset drift predictor and simulator state when scenario changes (new component under test)
            if current_scenario != last_scenario:
                drift_predictor.reset()
                component_sim.reset()
                cusum_detector.reset()
                sim_iddq = 10.0
                sim_pd = 4.5
                if current_scenario == "isro_outlier":
                    burn_in_hours = 24.0
                elif current_scenario == "electrical_short":
                    burn_in_hours = 96.0
                else:
                    burn_in_hours = 0.0
                last_scenario = current_scenario

            # 1. Generate Raw Sensor Telemetry using Member 2's Physics Engine
            # Each tick = 0.8s real time. We simulate COMPRESSED burn-in hours:
            # 1 tick → 0.4 simulated hours so the demo reaches meaningful
            # burn-in milestones quickly (24h in ~60s, 168h in ~6.5min).
            HOURS_PER_TICK = 0.4

            # Always advance time forward regardless of scenario
            burn_in_hours = min(168.0, burn_in_hours + HOURS_PER_TICK)

            if current_scenario == "nominal":
                sim_t, sim_v, sim_c = component_sim.step(dt=1.0, mode="normal")
                # Couple Iddq and propagation delay to junction temperature and supply voltage via Arrhenius & CMOS physics
                t_kelvin = sim_t + 273.15
                t0_kelvin = 125.0 + 273.15
                thermal_ratio = math.exp(
                    component_sim.Ea_kB * (1.0 / t0_kelvin - 1.0 / t_kelvin)
                )
                sim_iddq = round(10.0 * thermal_ratio + random.gauss(0, 0.15), 2)
                # H1 Clamp: Enforces a physically defensible lot-population bound representing
                # a pre-screened HTOL lot (±15% around nominal 10µA).
                sim_iddq = max(9.0, min(11.5, sim_iddq))
                sim_pd = round(
                    4.50
                    + 0.008 * (sim_t - 125.0)
                    - 0.05 * (sim_v - 5.0)
                    + random.uniform(-0.04, 0.04),
                    3,
                )

            elif current_scenario == "isro_outlier":
                # ISRO prompt: 45 uA leakage in 10 uA lot - caught at 24h check
                sim_t, sim_v, sim_c = component_sim.step(dt=1.0, mode="normal")
                t_kelvin = sim_t + 273.15
                t0_kelvin = 125.0 + 273.15
                thermal_ratio = math.exp(
                    component_sim.Ea_kB * (1.0 / t0_kelvin - 1.0 / t_kelvin)
                )
                sim_iddq = round(45.2 * thermal_ratio + random.uniform(-0.5, 0.5), 2)
                sim_pd = round(
                    4.50 + 0.008 * (sim_t - 125.0) - 0.05 * (sim_v - 5.0) + 0.1, 3
                )

            elif current_scenario == "thermal_drift":
                # Latent creep - MODULE B core scenario: Iddq climbs with thermal creep
                # Uses Member 2's thermal RC drift model with explicit accelerated scaling.
                # NOTE: DEMO_ACCELERATION_FACTOR is an intentional, documented demonstration mode
                # to visibly compress 168h of thermal state into a 6-minute live presentation.
                # Module B's regression axis (burn_in_hours) remains uncompressed for scientific integrity.
                DEMO_ACCELERATION_FACTOR = 10.0
                sim_t, sim_v, sim_c = component_sim.step(
                    dt=1.0,
                    mode="drift",
                    drift_time=burn_in_hours * DEMO_ACCELERATION_FACTOR,
                    drift_rate=0.005,
                )
                t_kelvin = sim_t + 273.15
                t0_kelvin = 125.0 + 273.15
                thermal_ratio = math.exp(
                    component_sim.Ea_kB * (1.0 / t0_kelvin - 1.0 / t_kelvin)
                )
                drift_creep = 0.45 * burn_in_hours
                sim_iddq = round(
                    min(
                        80.0,
                        (10.0 + drift_creep) * thermal_ratio + random.gauss(0, 0.05),
                    ),
                    2,
                )
                sim_pd = round(
                    min(
                        6.5,
                        4.50
                        + 0.008 * (sim_t - 125.0)
                        - 0.05 * (sim_v - 5.0)
                        + 0.015 * burn_in_hours,
                    ),
                    3,
                )

            elif current_scenario == "electrical_short":
                # Severe OCP foldback voltage collapse + current surge modeled by Member 2
                sim_t, sim_v, sim_c = component_sim.step(dt=1.0, mode="short")
                sim_iddq, sim_pd = component_sim.compute_iddq_and_prop_delay(
                    sim_t, sim_v, mode="short"
                )

            # 2. RUN MEMBER 3's MODULE A: MULTIVARIATE ISOLATION FOREST INFERENCE
            # Pass active_criticality so the criticality-aware score gate is applied.
            # Do NOT pass it as a data feature — only as a decision parameter.
            ml_result = model.detect_spike(
                current=sim_c,
                voltage=sim_v,
                temp=sim_t,
                iddq=sim_iddq,
                prop_delay=sim_pd,
                criticality_level=active_criticality,
            )

            # 3. RUN MEMBER 3's MODULE B: LATENT DRIFT PREDICTOR
            # Pass real burn_in_hours (0–168) as the time axis — physically meaningful
            drift_result = drift_predictor.update(burn_in_hours, sim_iddq)

            # 4. RUN MEMBER 4's CUSUM TIME-SERIES DRIFT DETECTOR
            cusum_alert = cusum_detector.evaluate_drift(sim_iddq)
            cusum_status = cusum_detector.get_status()

            # 5. Fault type classification from multivariate signature
            # Short circuit: simulator physics → very high current (>4A) AND voltage collapse (<2V)
            # These thresholds come directly from simulator.py:
            #   R_short=0.05Ω, V_source=5V → I_demand = 5/0.05+0.02 = ~95A → clamped to I_limit=8A
            #   v_actual = 8 * 0.05 = 0.40V under OCP
            # An electrical spike is a sudden multivariate outlier without the V/I signature of a short.
            is_anomaly_flag = bool(ml_result.get("is_anomaly", False))
            raw_score = float(ml_result.get("raw_score", 0.0))
            cusum_drift_flag = bool(cusum_alert)
            short_signature = (
                is_anomaly_flag and raw_score < 0.0 and sim_c > 4.0 and sim_v < 2.0
            )

            if short_signature:
                fault_type = "ELECTRICAL_SHORT_CIRCUIT"
            elif (
                is_anomaly_flag
                and cusum_drift_flag
                and current_scenario == "thermal_drift"
            ):
                fault_type = "THERMAL_DRIFT"
            elif is_anomaly_flag:
                fault_type = "ELECTRICAL_SPIKE"
            else:
                fault_type = "NORMAL"

            # 6. Construct Unified Telemetry + AI Response Payload (Modules A, B + Member 2 & 4)
            p_val = ml_result.get("power", round(sim_v * sim_c, 4))
            r_val = ml_result.get(
                "dynamic_resistance", round(sim_v / (sim_c + 1e-6), 3)
            )
            z_val = ml_result.get("iddq_zscore", 0.0)

            telemetry_payload = {
                "timestamp": datetime.now(UTC).isoformat(),
                # Raw telemetry (from Member 2's Physics Engine)
                "voltage": round(sim_v, 4),
                "current": round(sim_c, 4),
                "temperature": round(sim_t, 2),
                "iddq_uA": round(sim_iddq, 2),
                "prop_delay": round(sim_pd, 3),
                "criticality_level": int(active_criticality),
                # MODULE A: Isolation Forest outputs
                "power_w": round(p_val, 4),
                "dynamic_res_ohm": round(r_val, 3),
                "iddq_zscore": round(z_val, 2),
                "is_anomaly": is_anomaly_flag,
                "anomaly_score": float(ml_result.get("anomaly_score", 0.032)),
                "raw_score": float(ml_result.get("raw_score", 0.182)),
                "detection_source": str(ml_result.get("detection_source", "none")),
                "fault_type": fault_type,
                "lot_mean_iddq": float(ml_result.get("lot_mean_iddq", 10.0)),
                "lot_std_iddq": float(ml_result.get("lot_std_iddq", 1.17)),
                "qa_justification": str(
                    ml_result.get("qa_justification", "QA STATUS [PASSED]")
                ),
                # MODULE B: Drift Predictor outputs
                "drift_slope_ua_h": float(drift_result.get("drift_slope_ua_h", 0.0)),
                "forecast_168h_uA": float(
                    drift_result.get("forecast_168h_uA", sim_iddq)
                ),
                "forecast_168h_label": str(
                    drift_result.get("forecast_168h_label", "COLLECTING DATA")
                ),
                "drift_status": str(drift_result.get("drift_status", "INITIALIZING")),
                "drift_r2": float(drift_result.get("drift_r2", 0.0)),
                "early_reject_b": bool(drift_result.get("early_reject_b", False)),
                "hours_to_violation": drift_result.get("hours_to_violation"),
                "n_observations": int(drift_result.get("n_observations", 0)),
                # MEMBER 4: CUSUM Drift outputs (includes criticality_level + threshold)
                "cusum_score": float(round(cusum_status["cusum"], 4)),
                "cusum_threshold": float(cusum_status["threshold"]),
                "cusum_drift_detected": bool(cusum_alert),
                # Session metadata
                "scenario": current_scenario,
                "burn_in_hours": round(burn_in_hours, 2),
                "system_status": "NOMINAL" if fault_type == "NORMAL" else "ANOMALY",
                "structured_evidence": ml_result.get("structured_evidence"),
            }

            _last_telemetry = telemetry_payload
            await _enqueue_persistence("telemetry", telemetry_payload)
            if tick_count % 50 == 0:
                _save_compatibility_state()

            # 7. Stream to Member 1 Frontend
            await websocket.send_json(telemetry_payload)
            await asyncio.sleep(0.8)

    except (WebSocketDisconnect, RuntimeError):
        pass
    except Exception as e:
        logger.exception("WebSocket pipeline error: %s", e)
    finally:
        is_running = False
        manager.disconnect(websocket)
        receiver_task.cancel()
        _save_compatibility_state()
        current_scenario = "nominal"
        burn_in_hours = 0


if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
