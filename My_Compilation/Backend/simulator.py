"""
simulator.py — SIH 26170: Physically-Grounded Virtual Burn-In Chamber Simulator
Simulates space-grade semiconductor telemetry with thermal RC dynamics, Arrhenius
leakage coupling, power supply compliance limits, bus regulation, and ADC quantization.

Burn-in baseline is calibrated to the MIL-STD-883 static steady-state burn-in
condition (125°C), consistent with NASA EEE-INST-002 screening practice for
flight-grade EEE parts. Each simulated component also carries a criticality_level
    (1 = low criticality, 2 = standard, 3 = mission-critical),
mirroring the tiered reliability-level framework used in EEE-INST-002 Table 2A,
so downstream anomaly detectors can apply mission-criticality-weighted thresholds.
"""

import argparse
import csv
import logging
import math
import random
import re
from datetime import UTC, datetime
from typing import Any, Dict, Tuple

logger = logging.getLogger("simulator")


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


class ComponentSimulator:
    """
    Stateful physics engine modeling a space-grade silicon component during
    MIL-STD-883 / EEE-INST-002 static steady-state burn-in.

    Physics Models Implemented:
      - Exponential Arrhenius leakage current: I_leak(T) = I0 * exp(Ea / kB * (1/T0 - 1/T))
      - First-order thermal RC lag: dT/dt = (P_diss - (T - T_amb)/R_th) / C_th
      - Bus load regulation: V_rail = V_source - I_total * R_source
      - Power Supply OCP/Constant Current Mode: I_out = min(I_demand, I_limit)
      - Foldback voltage collapse under current-limit conditions (short-circuit physics)
      - Gaussian sensor noise & 12-bit ADC discrete quantization

    Reliability Framework:
      - Static burn-in temperature baseline (125°C) per MIL-STD-883 Method 1015
        static burn-in condition for hybrid microcircuits / flight EEE parts.
      - criticality_level (1/2/3) mirrors NASA EEE-INST-002 Table 2A reliability
        tiers: Level 1 = low-criticality applications, Level 2 = standard, and
        Level 3 = highest criticality for flight or human-rated hardware.
    """

    def __init__(self, criticality_level: int = 2) -> None:
        # Nominal Baseline Operating Point
        self.T_amb: float = 25.0  # Ambient Room Temp (°C)
        self.T_junction: float = 125.0  # Initial Junction Temp — MIL-STD-883 static burn-in (°C)
        self.V_source: float = 5.0  # Ideal DC Supply (V)
        self.I_nominal: float = 1.15  # Functional baseline load (A) — 1.15A base + 0.05A leakage = 1.20A nominal

        # Semiconductor Physical Constants
        self.Ea_kB: float = 4000.0  # Activation energy term (Ea / kB in Kelvin)
        self.I_leak_base: float = 0.05  # Baseline leakage current at 125°C reference (A)
        self.R_th: float = 16.667  # Thermal Resistance (°C/W) — calibrated for 125°C steady-state at 6.0W
        self.C_th: float = 1.5  # Thermal Capacitance (J/°C)

        # Power Bench & Hardware Constraints
        self.R_source: float = 0.02  # Supply output impedance (Ohms)
        self.I_limit: float = 8.0  # Over-Current Protection limit (A)
        self.R_short: float = 0.05  # Resistance during catastrophic short (Ohms)

        # Sensor & ADC Specs (12-bit ADCs)
        self.adc_bits: int = 12
        self.v_max: float = 10.0
        self.t_max: float = 175.0  # Junction destruction ceiling — typical Si absolute max rating (°C)
        self.i_max: float = 15.0

        # Reliability / Mission Criticality Metadata
        self.criticality_level: int = criticality_level  # 1 (low) - 3 (mission-critical)

        # State Tracking
        self.destroyed: bool = False  # Tracks if component has melted down

    def _quantize(self, val: float, max_val: float) -> float:
        """Applies 12-bit ADC quantization step size."""
        step = max_val / (2**self.adc_bits - 1)
        quantized_steps = round(val / step)
        return round(quantized_steps * step, 4)

    def _arrhenius_leakage(self, temp_c: float) -> float:
        """Computes temperature-dependent leakage current using the Arrhenius relation.
        Reference point (T0) is 125°C, matching the static burn-in baseline."""
        t_kelvin = temp_c + 273.15
        t0_kelvin = 125.0 + 273.15
        return self.I_leak_base * math.exp(self.Ea_kB * (1.0 / t0_kelvin - 1.0 / t_kelvin))

    def quantize(self, val: float, max_val: float) -> float:
        """Public alias for 12-bit ADC quantization."""
        return self._quantize(val, max_val)

    def step_telemetry(self, scenario: str = "nominal", dt: float = 1.0) -> Dict[str, Any]:
        """Convenience method returning a comprehensive telemetry dictionary."""
        mode = "short" if "short" in scenario.lower() else "drift" if "drift" in scenario.lower() else "normal"
        t, v, i = self.step(dt=dt, mode=mode)
        iddq, pd = self.compute_iddq_and_prop_delay(t, v, mode=mode)
        status = "ANOMALY" if (mode != "normal" or iddq > 50.0 or v < 3.0) else "NOMINAL"
        return {
            "temperature": t,
            "voltage": v,
            "current": i,
            "iddq_uA": iddq,
            "prop_delay": pd,
            "status": status,
        }

    def step(
        self,
        dt: float = 1.0,
        mode: str = "normal",
        drift_time: float = 0.0,
        drift_rate: float = 0.05,
        degradation_factor: float = 1.0,
        scenario: str = None,
    ) -> Tuple[float, float, float]:
        """
        Advances the simulation by dt seconds.
        Modes: 'normal', 'drift' (thermal degradation), 'short' (electrical short).
        """
        if scenario:
            mode = "short" if "short" in scenario.lower() else "drift" if "drift" in scenario.lower() else "normal"

        if mode not in ("normal", "drift", "short"):
            raise ValueError(f"Unknown mode: {mode!r}. Must be 'normal', 'drift', or 'short'.")

        # Euler Integration Sub-stepping to prevent numerical explosion
        num_sub_steps = 10
        sub_dt = dt / num_sub_steps

        v_actual = 0.0
        i_actual = 0.0

        for _ in range(num_sub_steps):
            # 1. Determine load impedance & baseline demand
            if mode == "short" or self.destroyed:
                # Electrical short circuit collapse (Triggered manually or by thermal meltdown)
                r_load = self.R_short
                i_demand = self.V_source / (r_load + self.R_source)
                i_actual = min(i_demand, self.I_limit)
                if i_actual < i_demand:
                    # OCP/foldback engaged: supply cannot deliver i_demand,
                    # so voltage collapses to whatever the load resistance allows
                    v_actual = i_actual * r_load
                else:
                    v_actual = max(0.0, self.V_source - (i_actual * self.R_source))
            else:
                # Normal or Thermal Drift mode
                i_leakage = self._arrhenius_leakage(self.T_junction)
                i_demand = self.I_nominal + i_leakage
                i_actual = min(i_demand, self.I_limit)
                v_actual = max(0.0, self.V_source - (i_actual * self.R_source))

            # 4. Thermal Dynamics (dT/dt = (P_in - P_out) / C_th)
            p_dissipated = v_actual * i_actual
            r_effective = self.R_th * (1.0 + drift_rate * drift_time) if mode == "drift" else self.R_th
            p_dissipated_heat = (self.T_junction - self.T_amb) / r_effective

            dT_dt = (p_dissipated - p_dissipated_heat) / self.C_th
            self.T_junction += dT_dt * sub_dt

            # 5. The Physical Fix: Cap at destruction threshold
            if self.T_junction >= self.t_max:
                self.T_junction = self.t_max
                self.destroyed = True

        # 6. Additive Gaussian Sensor Noise
        t_measured = self.T_junction + random.gauss(0, 0.15)
        v_measured = v_actual + random.gauss(0, 0.01)
        i_measured = i_actual + random.gauss(0, 0.005)

        # 7. ADC Quantization
        t_final = self._quantize(max(0.0, t_measured), self.t_max)
        v_final = self._quantize(max(0.0, v_measured), self.v_max)
        i_final = self._quantize(max(0.0, i_measured), self.i_max)

        return t_final, v_final, i_final

    def compute_iddq_and_prop_delay(
        self, temp: float, volt: float, mode: str = "normal", drift_time: float = 0.0
    ) -> Tuple[float, float]:
        """Computes standby current Iddq (in uA) and CMOS propagation delay (in ns) physically coupled to temperature and voltage."""
        # Arrhenius thermal scaling for Iddq: ~10 uA nominal at 125°C
        t_kelvin = temp + 273.15
        t0_kelvin = 125.0 + 273.15
        thermal_ratio = math.exp(self.Ea_kB * (1.0 / t0_kelvin - 1.0 / t_kelvin))

        if mode == "short":
            iddq_val = random.uniform(85.0, 130.0)
            pd_val = random.uniform(9.0, 11.0)
        elif mode == "drift":
            drift_factor = 1.0 + 0.005 * drift_time
            iddq_val = 10.0 * thermal_ratio * drift_factor + random.gauss(0, 0.4)
            pd_val = 4.50 + 0.008 * (temp - 125.0) - 0.05 * (volt - 5.0) + 0.02 * drift_time + random.gauss(0, 0.03)
        else:
            # Nominal lot variation (Gaussian jitter ~1.17 uA std)
            iddq_val = 10.0 * thermal_ratio + random.gauss(0, 1.15)
            pd_val = 4.50 + 0.008 * (temp - 125.0) - 0.05 * (volt - 5.0) + random.uniform(-0.08, 0.08)

        iddq_val = round(max(5.0, min(150.0, iddq_val)), 2)
        pd_val = round(max(3.0, min(15.0, pd_val)), 3)
        return iddq_val, pd_val

    def reset(self) -> None:
        """Resets component thermal state back to the MIL-STD-883 burn-in baseline."""
        self.T_junction = 125.0
        self.destroyed = False


# ─────────────────────────────────────────────────────────────
# Global instance for legacy interface compatibility
# ─────────────────────────────────────────────────────────────
_global_sim = ComponentSimulator()


def get_live_telemetry(mode: str = "normal", seconds_elapsed: int = 0) -> Dict[str, str | float | int]:
    """Returns a single real-time telemetry frame formatted for WebSocket transmission."""
    if mode != "short" and _global_sim.destroyed:
        _global_sim.reset()

    temp, volt, curr = _global_sim.step(dt=1.0, mode=mode, drift_time=seconds_elapsed)
    iddq, pd_val = _global_sim.compute_iddq_and_prop_delay(temp, volt, mode=mode, drift_time=seconds_elapsed)
    return {
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "voltage": volt,
        "current": curr,
        "temperature": temp,
        "iddq": iddq,
        "prop_delay": pd_val,
        "criticality_level": _global_sim.criticality_level,
    }


def generate_dataset(
    filename: str = "sample_data.csv",
    n_normal: int = 10000,
    n_drift: int = 1000,
    n_short: int = 200,
    criticality_level: int = 2,
    seed: int = None,
) -> None:
    """Generates sequential offline time-series datasets with continuous contiguous fault regions."""
    if seed is not None:
        random.seed(seed)
        logger.info("Random seed set to %d for reproducibility", seed)

    logger.info("Generating dataset -> %s", filename)
    sim = ComponentSimulator(criticality_level=criticality_level)
    start_time = datetime(2026, 3, 30, 0, 0, 0, tzinfo=UTC)

    try:
        with open(filename, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["timestamp", "voltage", "current", "temperature", "iddq", "prop_delay", "criticality_level", "label"]
            )

            current_time = start_time
            step_idx = 0

            # 1. Contiguous Nominal Operation
            logger.info("Writing %d contiguous normal rows...", n_normal)
            for _ in range(n_normal):
                t, v, i = sim.step(dt=1.0, mode="normal")
                iq, pd_val = sim.compute_iddq_and_prop_delay(t, v, mode="normal")
                ts_str = current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                writer.writerow([ts_str, v, i, t, iq, pd_val, sim.criticality_level, "normal"])
                current_time += float_to_timedelta(1.0)
                step_idx += 1

            # 2. Contiguous Thermal Runaway Sequence (Ideal for CUSUM evaluation)
            # Uses a slow, physically realistic drift_rate so degradation stays gradual
            # and non-destructive; loop breaks early if destruction is reached anyway,
            # preventing short-circuit rows from being silently mislabeled as drift.
            logger.info("Writing %d contiguous drift rows...", n_drift)
            for drift_sec in range(n_drift):
                t, v, i = sim.step(dt=1.0, mode="drift", drift_time=drift_sec, drift_rate=0.0008)
                if sim.destroyed:
                    logger.warning(
                        "Component destroyed at drift_sec=%d — truncating drift phase early "
                        "to avoid mislabeling short-circuit rows as drift_anomaly.",
                        drift_sec,
                    )
                    break
                iq, pd_val = sim.compute_iddq_and_prop_delay(t, v, mode="drift", drift_time=drift_sec)
                ts_str = current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                writer.writerow([ts_str, v, i, t, iq, pd_val, sim.criticality_level, "drift_anomaly"])
                current_time += float_to_timedelta(1.0)
                step_idx += 1

            # Reset state back to nominal before triggering short
            sim.reset()

            # 3. Sudden Catastrophic Short Event
            logger.info("Writing %d contiguous short-circuit rows...", n_short)
            for _ in range(n_short):
                t, v, i = sim.step(dt=1.0, mode="short")
                iq, pd_val = sim.compute_iddq_and_prop_delay(t, v, mode="short")
                ts_str = current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                writer.writerow([ts_str, v, i, t, iq, pd_val, sim.criticality_level, "short_anomaly"])
                current_time += float_to_timedelta(1.0)
                step_idx += 1

            # 4. Hidden Ground Truth Records (0h, 24h, 96h, 168h)
            logger.info("Writing hidden ground truth records for 0h, 24h, 96h, 168h...")
            sim.reset()
            for target_h, label in [(0, "0h"), (24, "24h"), (96, "96h"), (168, "168h")]:
                t, v, i = sim.step(dt=1.0, mode="drift", drift_time=target_h, drift_rate=0.0008)
                iq, pd_val = sim.compute_iddq_and_prop_delay(t, v, mode="drift", drift_time=target_h)
                ts_str = (current_time + float_to_timedelta(target_h * 3600)).strftime("%Y-%m-%dT%H:%M:%S.%f")[
                    :-3
                ] + "Z"
                writer.writerow([ts_str, v, i, t, iq, pd_val, sim.criticality_level, f"{label}_record"])
                step_idx += 1

    except OSError as exc:
        logger.error("Failed writing dataset to %s: %s", filename, exc)
        raise

    logger.info("Dataset generation complete: %d total rows written.", step_idx)


def export_to_sqlite(
    csv_filename: str = "sample_data.csv", db_filename: str = "burn_in.db", table_name: str = "telemetry"
) -> None:
    """Exports generated CSV telemetry into a local SQLite database table (burn_in.db)."""
    import sqlite3

    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
        raise ValueError(f"Invalid table name '{table_name}': must be alphanumeric/underscores only.")
    logger.info("Exporting %s to SQLite database -> %s (table: %s)", csv_filename, db_filename, table_name)
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()
    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            voltage REAL NOT NULL,
            current REAL NOT NULL,
            temperature REAL NOT NULL,
            iddq REAL NOT NULL,
            prop_delay REAL NOT NULL,
            criticality_level INTEGER NOT NULL,
            label TEXT NOT NULL
        )
    """)

    with open(csv_filename) as f:
        reader = csv.DictReader(f)
        rows = [
            (
                row["timestamp"],
                float(row["voltage"]),
                float(row["current"]),
                float(row["temperature"]),
                float(row.get("iddq", 10.0)),
                float(row.get("prop_delay", 4.5)),
                int(row["criticality_level"]),
                row["label"],
            )
            for row in reader
        ]

    cursor.executemany(
        f"""
        INSERT INTO {table_name} (timestamp, voltage, current, temperature, iddq, prop_delay, criticality_level, label)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()
    logger.info("SQLite export complete: %d rows inserted into %s.", len(rows), db_filename)


def float_to_timedelta(seconds: float):
    from datetime import timedelta

    return timedelta(seconds=seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SIH 26170 Physics-based Telemetry Simulator")
    parser.add_argument("--output", "-o", default="sample_data.csv", help="Output CSV path")
    parser.add_argument("--sqlite", "-s", default="burn_in.db", help="Output SQLite DB path (set empty string to skip)")
    parser.add_argument("--normal", type=int, default=10000, help="Normal steps count")
    parser.add_argument("--drift", type=int, default=1000, help="Contiguous thermal drift steps")
    parser.add_argument("--short", type=int, default=200, help="Short circuit event steps")
    parser.add_argument(
        "--criticality",
        type=int,
        default=2,
        choices=[1, 2, 3],
        help="Mission criticality tier per EEE-INST-002 Table 2A (1=highest reliability, 3=lowest)",
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible dataset generation")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    configure_logging(args.log_level)
    generate_dataset(
        filename=args.output,
        n_normal=args.normal,
        n_drift=args.drift,
        n_short=args.short,
        criticality_level=args.criticality,
        seed=args.seed,
    )
    if args.sqlite:
        export_to_sqlite(csv_filename=args.output, db_filename=args.sqlite)
