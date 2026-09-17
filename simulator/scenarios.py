"""
scenarios.py — Fault scenario definitions for the FleetGuard vehicle simulator.

Each scenario is a function that, given the current sensor readings and a
degradation level (0.0 = fresh, 1.0 = fully degraded), returns modified sensor
readings with realistic fault signatures applied.
"""

import random
import math
from typing import Dict


# ── Baselines (healthy operating ranges) ──────────────────────────────────────
BASELINE = {
    "volt":      170.0,
    "rotate":    450.0,
    "pressure":  100.0,
    "vibration": 40.0,
}

NOISE = {
    "volt":      5.0,
    "rotate":    20.0,
    "pressure":  5.0,
    "vibration": 3.0,
}


def _gauss(mean: float, std: float) -> float:
    return random.gauss(mean, std)


# ── Scenario functions ─────────────────────────────────────────────────────────

def scenario_normal(sensors: Dict[str, float], degradation: float) -> Dict[str, float]:
    """Healthy machine — Gaussian noise around baseline."""
    return {k: max(0.0, _gauss(BASELINE[k], NOISE[k])) for k in BASELINE}


def scenario_overheat(sensors: Dict[str, float], degradation: float) -> Dict[str, float]:
    """
    Pressure and vibration rise steadily as the machine overheats.
    Voltage drops slightly due to thermal load.
    """
    d = degradation
    return {
        "volt":      max(0.0, _gauss(BASELINE["volt"] - 20 * d, NOISE["volt"] * (1 + d))),
        "rotate":    max(0.0, _gauss(BASELINE["rotate"] - 30 * d, NOISE["rotate"])),
        "pressure":  max(0.0, _gauss(BASELINE["pressure"] + 60 * d, NOISE["pressure"] * (1 + 2 * d))),
        "vibration": max(0.0, _gauss(BASELINE["vibration"] + 40 * d, NOISE["vibration"] * (1 + 2 * d))),
    }


def scenario_voltage_spike(sensors: Dict[str, float], degradation: float) -> Dict[str, float]:
    """
    Erratic voltage fluctuations — spikes and drops simulating power supply issues.
    """
    spike = math.sin(degradation * math.pi * 6) * 60 * degradation
    return {
        "volt":      max(0.0, _gauss(BASELINE["volt"] + spike, NOISE["volt"] * (1 + 3 * degradation))),
        "rotate":    max(0.0, _gauss(BASELINE["rotate"], NOISE["rotate"])),
        "pressure":  max(0.0, _gauss(BASELINE["pressure"], NOISE["pressure"])),
        "vibration": max(0.0, _gauss(BASELINE["vibration"] + 10 * degradation, NOISE["vibration"])),
    }


def scenario_bearing_wear(sensors: Dict[str, float], degradation: float) -> Dict[str, float]:
    """
    Gradual vibration increase and rotation instability — classic bearing wear signature.
    """
    d = degradation
    return {
        "volt":      max(0.0, _gauss(BASELINE["volt"], NOISE["volt"])),
        "rotate":    max(0.0, _gauss(BASELINE["rotate"] - 50 * d, NOISE["rotate"] * (1 + 2 * d))),
        "pressure":  max(0.0, _gauss(BASELINE["pressure"] + 10 * d, NOISE["pressure"])),
        "vibration": max(0.0, _gauss(BASELINE["vibration"] + 80 * d, NOISE["vibration"] * (1 + 3 * d))),
    }


def scenario_degradation(sensors: Dict[str, float], degradation: float) -> Dict[str, float]:
    """
    Slow multi-sensor drift — all sensors gradually move out of range.
    """
    d = degradation
    return {
        "volt":      max(0.0, _gauss(BASELINE["volt"] - 30 * d, NOISE["volt"] * (1 + d))),
        "rotate":    max(0.0, _gauss(BASELINE["rotate"] - 60 * d, NOISE["rotate"] * (1 + d))),
        "pressure":  max(0.0, _gauss(BASELINE["pressure"] + 30 * d, NOISE["pressure"] * (1 + d))),
        "vibration": max(0.0, _gauss(BASELINE["vibration"] + 50 * d, NOISE["vibration"] * (1 + 2 * d))),
    }


def scenario_random_fault(sensors: Dict[str, float], degradation: float) -> Dict[str, float]:
    """
    A random sensor spikes suddenly then partially recovers — intermittent fault.
    """
    fault_sensor = random.choice(list(BASELINE.keys()))
    result = {k: max(0.0, _gauss(BASELINE[k], NOISE[k])) for k in BASELINE}
    if degradation > 0.3:
        result[fault_sensor] = max(0.0, result[fault_sensor] + random.uniform(40, 120) * degradation)
    return result


# ── Registry ──────────────────────────────────────────────────────────────────

SCENARIOS = {
    "normal":        scenario_normal,
    "overheat":      scenario_overheat,
    "voltage_spike": scenario_voltage_spike,
    "bearing_wear":  scenario_bearing_wear,
    "degradation":   scenario_degradation,
    "random_fault":  scenario_random_fault,
}

SCENARIO_LABELS = {
    "normal":        "Normal Operation",
    "overheat":      "Overheating",
    "voltage_spike": "Voltage Spike",
    "bearing_wear":  "Bearing Wear",
    "degradation":   "General Degradation",
    "random_fault":  "Random Fault",
}

# ── Demo mode script ──────────────────────────────────────────────────────────
# Maps machine_id → (start_tick, scenario_name)
# Tick cadence = 1 tick/second at 1x speed
DEMO_SCRIPT = [
    # (machine_id, start_tick, scenario)  — drama unfolds over ~90 seconds
    (1,  0,  "overheat"),
    (2,  5,  "bearing_wear"),
    (3,  10, "voltage_spike"),
    (4,  15, "degradation"),
    (5,  20, "overheat"),
    (6,  25, "bearing_wear"),
    (7,  30, "voltage_spike"),
    (8,  0,  "degradation"),
    (9,  0,  "random_fault"),
    (10, 0,  "bearing_wear"),
]
