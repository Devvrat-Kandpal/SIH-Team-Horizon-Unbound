"""Backend/physics_constants.py -- Project ARJUNA (SIH 26170)

Single authoritative source of truth for ALL physical constants and unit conventions.

Design intent (consolidated audit M-02, M-04, M-06, M-09, M-10, M-16, M-17):
  - Every quantity is defined in exactly one place, with an EXPLICIT unit.

  - I_leak_base is the true semiconductor leakage current (10 uA at 125 C),
    DISTINCT from I_static_blocks (0.04999 A = ~49.99 mA static bias/termination
    current). These are different physical quantities; the ~5000x ratio between
    them is intentional and not a bug (audit M-08 documentation correction).

  - Two Iddq noise domains (see M-09/M-10):
      LOT domain   (sigma_lot=1.15 uA): cross-component die-to-die wafer spread,
        printed into generated CSVs and used for training the Isolation Forest.
      LIVE SENSOR  (sigma_sensor=0.15 uA): per-tick measurement noise applied by
        the deployed server's real-time telemetry. The nominal live clamp
        [9.0, 11.5] uA is a pre-screened healthy-channel bound that deliberately
        suppresses lot position so the deployed CUSUM detects drift from a part's
        own baseline (auto-baseline, not lot shift).

All downstream modules (simulator.py, server.py, criticality_config.py, tests,
frontend docs) must IMPORT these constants rather than hard-code matching values
(M-02, M-04).
"""

from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────────────
# Nominal baseline operating point
# ──────────────────────────────────────────────────────────────────────────────
T_AMB_C: float =25.0        # Ambient chamber temperature [C]
T_BURNIN_C: float =125.0    # MIL-STD-883 static burn-in junction temperature [C]
V_SOURCE_V: float =5.0       # Ideal DC supply rail [V]
I_FUNCTIONAL_A: float =1.15    # Dynamic functional load current [A] -- rail component
I_STATIC_BLOCKS_A: float =0.04999   # Static bias/termination current [A] -- NOT leakage
I_TOTAL_NOMINAL_A: float =1.20      # = functional + static + ~10 uA leakage [A]

# ──────────────────────────────────────────────────────────────────────────────
# Semiconductor physical constants
# ──────────────────────────────────────────────────────────────────────────────
# Activation energy as an Ea/kB term in kelvin; the Arrhenius exponent uses (1/T0 - 1/T).
# 4000 K corresponds to approx 0.345 eV (Ea = kB * 4000 K, kB = 8.617333e-5 eV/K).
# Heating 25 -> 125 C yields an acceleration factor of approx 29x, NOT the
#   historically misreported ">100x" (that value came from documentation-only Ea = 0.70 eV).
# Consolidated audit M-06 adopts ONE value: the simulation code's approx 0.345 eV (~29x).
Ea_kB_KELVIN: float =4000.0
EA_EV: float =0.345        # documentation-only equivalent of Ea_kB (4000 K * 8.617e-5 ~ 0.345 eV)

I_LEAK_BASE_A: float =10e-6    # True DUT leakage at 125 C reference (10 uA)
R_TH_C_PER_W: float =16.667    # Thermal resistance [C/W], calibrated for 125 C at ~6.0 W
C_TH_J_PER_C: float =1.5       # Thermal capacitance[J/C]
# ──────────────────────────────────────────────────────────────────────────────
# Power bench & hardware constraints
# ──────────────────────────────────────────────────────────────────────────────
R_SOURCE_OHM: float =0.02     # Supply output impedance [Ohm]
I_LIMIT_A: float =8.0        # Over-Current Protection OCP current limit [A]
R_SHORT_OHM: float =0.05      # Resistance during catastrophic die short [Ohm]

# ──────────────────────────────────────────────────────────────────────────────
# Sensor & ADC specs (12-bit ADCs)
# ──────────────────────────────────────────────────────────────────────────────
ADC_BITS: int =12
V_MAX_V: float =10.0        # ADC voltage full-scale [V]
T_MAX_C: float =175.0      # Junction destruction ceiling and ADC full-scale [C]
I_MAX_A: float =15.0      # ADC current full-scale [A]

# ──────────────────────────────────────────────────────────────────────────────
# Iddq noise domains (documented two-domain model -- audit M-09/M-10)
# ──────────────────────────────────────────────────────────────────────────────
SIGMA_LOT_IDDQ_UA: float =1.15       # cross-component die-to-die wafer lot spread [uA]
SIGMA_SENSOR_IDDQ_UA: float =0.15     # per-tick live sensor measurement noise [uA]
IDDQ_NOMINAL_LOT_MEAN_UA: float =10.0    # nominal healthy lot mean Iddq [uA]
IDDQ_LIVE_CLAMP_MIN_UA: float =9.0     # pre-screened healthy-channel clamp lower bound [uA]
IDDQ_LIVE_CLAMP_MAX_UA: float =11.5    # pre-screened healthy-channel clamp upper bound [uA]
IDDQ_DATASHEET_LIMIT_UA: float =50.0    # datasheet absolute static screening limit [uA]

# Iddq range guard used by compute_iddq_and_prop_delay
IDDQ_MIN_UA: float =5.0
IDDQ_MAX_UA: float =150.0

# ──────────────────────────────────────────────────────────────────────────────
# Degradation (drift) model -- CANDIDATE vs VALIDATED framing (audit M-16)
# ──────────────────────────────────────────────────────────────────────────────
# The linear r_effective = R_th * (1 + R_TH_DRIFT_RATE_PER_H * t) model is a KNOWN SIMPLIFICATION,
#   not a validated semiconductor aging law. A more physical, accumulated, Arrhenius-activated
#   degradation state is a CANDIDATE improvement (needs calibration + comparison + validation);
#   this toggle compares the two models side-by-side without silently changing behaviour.
DEGRADATION_MODEL: str ="linear"   # "linear" (legacy) or "accumulated_arrhenius" (candidate)
# Iddq creep law (hours-based, common to dataset / GT / live server -- audit M-02/M-04):
#   iddq_drift = IDDQ_NOMINAL_LOT_MEAN_UA * (1 + IDDQ_DRIFT_RATE_UA_PER_H * burn_in_h / mean)
#   at a CONSTANT 125 C the endpoint is ~85.6 uA at 168 h: 10 * (1 + 0.45*168/10).
IDDQ_DRIFT_RATE_UA_PER_H: float =0.45
# Thermal-resistance creep (hours-based, mild, survivable to 168 h -- audit M-01/M-15):
#   r_effective = R_th * (1 + R_TH_DRIFT_RATE_PER_H * burn_in_h)
#   so at 168 h R_th grows only ~1.34x, keeping junction temp below the 175 C ceiling.
R_TH_DRIFT_RATE_PER_H: float =0.002
TRAINING_DRIFT_SPAN_H: float =24.0
# Training drift-region burn-in span (hours) spanned by the contiguous drift rows (audit M-03/M-05):
#   a 24 h early-creep window acts as the benchmarked drift span; the rows cover that 24 h range.
#   CAUTION: in the coupled burn-in curve, junction T rises with Rth creep, so the Arrhenius
# Accumulated Arrhenius degradation candidate constants -- placeholders requiring calibration;
#   these are NOT yet validated physical coefficients.
DEGRAD_INITIAL_C: float =1.0              # degradation state initial value [dimensionless]
# A0 calibration (post-audit fix): solved so the candidate reproduces the VALIDATED linear
#   model's 168 h endpoint at the documented 125 C steady-state design point:
#   linear: D(168h) = 1 + R_TH_DRIFT_RATE_PER_H*168 = 1.336  (Delta_D = 0.336)
#   candidate: Delta_D = A0 * exp(-Ea_kb/398.15) * 604800 s = 0.336
#              => A0 = 0.336 / (604800 * exp(-4000/398.15)) ~= 1.286e-2 [per s]
#   CAUTION: this is a matched-ENDPOINT calibration at constant 125 C. In the coupled model the
#   candidate is temperature-activated (positive feedback: higher T -> faster D growth), so its
#   trajectory will exceed the linear one as junction T rises above 125 C. Default model remains
#   "linear"; the candidate still requires full downstream re-validation before becoming default.
DEGRAD_ARRHENIUS_A0_S: float =1.286e-2   # pre-exponential degradation rate [per s], endpoint-calibrated
DEGRAD_ARRHENIUS_EA_KB: float = Ea_kB_KELVIN   # ASSUMED: Reuses leakage Ea_kB without empirical validation
#   factor multiplies the creep and the endpoint is IDDQ_MAX_UA-clamped (150 uA), not 85.6 uA.
# ──────────────────────────────────────────────────────────────────────────────
# Canonical timebase (audit M-02/M-03/M-05/M-13/M-15)
# ──────────────────────────────────────────────────────────────────────────────
# t_physical_s : physical time in SECONDS [SI].
# t_burnin_h   : burn-in time in HOURS (0-168], labelled on axes, used by Module B regression.
# t_demo_s     : demonstration wall-clock SECONDS (frontend clock), distinct from physical time.
# The physical time <-> burn-in hours conversion is ALWAYS:
#   t_physical_s = t_burnin_h * 3600.0
DEMO_ACCELERATION_FACTOR: float =1.0
# NOTE: legacy demo default used a 10x thermal acceleration (QA_PAIRS.md). Consolidating onto
#   a single canonical factor eliminated the component-level train/serve skew (M-03). The live demo
#   now advances burn-in hours EXPLICITLY so Module B regresses on ACTUAL burn-in time.


# ──────────────────────────────────────────────────────────────────────────────
# Convenience helpers (canonical unit conversions)
# ──────────────────────────────────────────────────────────────────────────────
def seconds_to_burnin_hours(t_physical_s: float)-> float:
    """Canonical conversion: physical seconds to burn-in hours."""
    return t_physical_s / 3600.0


def burnin_hours_to_seconds(t_burnin_h: float)-> float:
    """Canonical conversion: burn-in hours to physical seconds."""
    return t_burnin_h * 3600.0
