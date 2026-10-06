"""
scenarios.py — Fault scenario definitions for the FleetGuard vehicle simulator.

Each scenario is a function that, given the current sensor readings and a
degradation level (0.0 = fresh, 1.0 = fully degraded), returns modified sensor
readings with realistic fault signatures applied.

Scenarios are tuned to produce visible risk changes within 30-60 ticks at 1x
(or 6-12 ticks at 5x speed) — suitable for live demos.
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
    Overheating — pressure and vibration rise, volt drops sharply, rotation slows.
    Tuned so rotate_mean24h and volt_mean24h (top model features) are strongly affected.
    """
    d = degradation
    return {
        "volt":      max(0.0, _gauss(BASELINE["volt"]      - 80  * d, NOISE["volt"]      * (1 + d))),
        "rotate":    max(0.0, _gauss(BASELINE["rotate"]    - 150 * d, NOISE["rotate"]    * (1 + 2 * d))),
        "pressure":  max(0.0, _gauss(BASELINE["pressure"]  + 100 * d, NOISE["pressure"]  * (1 + 2 * d))),
        "vibration": max(0.0, _gauss(BASELINE["vibration"] + 100 * d, NOISE["vibration"] * (1 + 3 * d))),
    }


def scenario_voltage_spike(sensors: Dict[str, float], degradation: float) -> Dict[str, float]:
    """
    Erratic voltage — spikes and drops simulating power supply failure.
    Volt swings wildly; rotation drops as power becomes unstable.
    """
    d = degradation
    spike = math.sin(d * math.pi * 8) * 60 * d
    return {
        "volt":      max(0.0, _gauss(BASELINE["volt"] + spike - 60 * d, NOISE["volt"] * (1 + 5 * d))),
        "rotate":    max(0.0, _gauss(BASELINE["rotate"] - 130 * d, NOISE["rotate"] * (1 + 3 * d))),
        "pressure":  max(0.0, _gauss(BASELINE["pressure"] - 20 * d, NOISE["pressure"] * (1 + d))),
        "vibration": max(0.0, _gauss(BASELINE["vibration"] + 70 * d, NOISE["vibration"] * (1 + 2 * d))),
    }


def scenario_bearing_wear(sensors: Dict[str, float], degradation: float) -> Dict[str, float]:
    """
    Bearing failure — vibration spikes hard, rotation deteriorates, volt drops.
    Tuned to strongly affect rotate_mean24h (top model feature) and vibration_mean24h.
    """
    d = degradation
    return {
        "volt":      max(0.0, _gauss(BASELINE["volt"]      - 40  * d, NOISE["volt"])),
        "rotate":    max(0.0, _gauss(BASELINE["rotate"]    - 160 * d, NOISE["rotate"]    * (1 + 3 * d))),
        "pressure":  max(0.0, _gauss(BASELINE["pressure"]  + 20  * d, NOISE["pressure"] * (1 + d))),
        "vibration": max(0.0, _gauss(BASELINE["vibration"] + 160 * d, NOISE["vibration"] * (1 + 4 * d))),
    }


def scenario_degradation(sensors: Dict[str, float], degradation: float) -> Dict[str, float]:
    """
    Slow multi-sensor drift — all sensors gradually move out of healthy range.
    """
    d = degradation
    return {
        "volt":      max(0.0, _gauss(BASELINE["volt"]      - 60  * d, NOISE["volt"]      * (1 + d))),
        "rotate":    max(0.0, _gauss(BASELINE["rotate"]    - 120 * d, NOISE["rotate"]    * (1 + d))),
        "pressure":  max(0.0, _gauss(BASELINE["pressure"]  + 60  * d, NOISE["pressure"]  * (1 + d))),
        "vibration": max(0.0, _gauss(BASELINE["vibration"] + 80  * d, NOISE["vibration"] * (1 + 2 * d))),
    }


def scenario_random_fault(sensors: Dict[str, float], degradation: float) -> Dict[str, float]:
    """
    A random sensor spikes suddenly — intermittent fault that triggers alerts.
    """
    result = {k: max(0.0, _gauss(BASELINE[k], NOISE[k])) for k in BASELINE}
    # Start faulting early (degradation > 0.1) and hit hard
    if degradation > 0.1:
        fault_sensor = random.choice(list(BASELINE.keys()))
        result[fault_sensor] = max(0.0, result[fault_sensor] + random.uniform(80, 180) * degradation)
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
# Maps (machine_id, start_tick, scenario_name)
# At 1x: 1 tick/s — drama unfolds over ~90s
# At 5x: 5 ticks/s — drama unfolds in ~18s
DEMO_SCRIPT = [
    (1,  0,  "overheat"),
    (2,  3,  "bearing_wear"),
    (3,  6,  "voltage_spike"),
    (4,  9,  "degradation"),
    (5,  12, "overheat"),
    (6,  15, "bearing_wear"),
    (7,  18, "voltage_spike"),
    (8,  0,  "degradation"),
    (9,  0,  "random_fault"),
    (10, 0,  "bearing_wear"),
]
