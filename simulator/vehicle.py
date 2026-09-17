"""
vehicle.py — Per-machine state machine for the FleetGuard simulator.

Each VehicleState tracks:
  - Current live sensor readings
  - The active fault scenario
  - Degradation level (0.0 = fresh, 1.0 = fully failed)
  - A rolling 3h/24h feature buffer (simplified as a deque) for ML inference
"""

import random
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Optional

from simulator.scenarios import SCENARIOS, BASELINE, NOISE


# How many ticks to keep per buffer window
# At 1 tick/second: 3h = 10800, 24h = 86400 — too heavy for in-memory.
# We use a compressed approximation: last N readings.
SHORT_WINDOW = 60    # ~3h compressed to 60 ticks
LONG_WINDOW  = 240   # ~24h compressed to 240 ticks


class VehicleState:
    """
    Represents a single machine in the simulation.
    Tracks sensor state and computes rolling feature vectors.
    """

    def __init__(
        self,
        machine_id: int,
        model_idx: int,
        age: int,
        scenario: str = "normal",
        degradation_rate: float = 0.005,
    ):
        self.machine_id       = machine_id
        self.model_idx        = model_idx
        self.age              = age
        self.scenario         = scenario
        self.degradation      = 0.0
        self.degradation_rate = degradation_rate  # per tick
        self.tick_count       = 0

        # Initialize sensors near baseline with small noise
        self.sensors: Dict[str, float] = {
            k: max(0.0, random.gauss(BASELINE[k], NOISE[k] * 0.3))
            for k in BASELINE
        }

        # Rolling buffers for feature engineering
        self._short_buf: Dict[str, deque] = {k: deque(maxlen=SHORT_WINDOW) for k in BASELINE}
        self._long_buf:  Dict[str, deque] = {k: deque(maxlen=LONG_WINDOW)  for k in BASELINE}

        # Seed buffers with baseline values
        for _ in range(SHORT_WINDOW):
            for k in BASELINE:
                self._short_buf[k].append(BASELINE[k])
        for _ in range(LONG_WINDOW):
            for k in BASELINE:
                self._long_buf[k].append(BASELINE[k])

    # ── Tick ──────────────────────────────────────────────────────────────────

    def tick(self) -> Dict:
        """Advance one simulation timestep. Returns the new sensor readings."""
        self.tick_count += 1

        # Apply scenario function
        fn = SCENARIOS.get(self.scenario, SCENARIOS["normal"])
        new_sensors = fn(self.sensors, self.degradation)
        self.sensors = new_sensors

        # Update rolling buffers
        for k in BASELINE:
            self._short_buf[k].append(new_sensors[k])
            self._long_buf[k].append(new_sensors[k])

        # Advance degradation
        self.degradation = min(1.0, self.degradation + self.degradation_rate)

        return dict(new_sensors)

    # ── Feature vector for ML inference ───────────────────────────────────────

    def feature_vector(self) -> Dict[str, float]:
        """
        Build the 27-feature vector the Random Forest expects.
        Mirrors the features in FEATURE_COLS from export_model.py.
        """
        feats: Dict[str, float] = {}

        for k in BASELINE:
            feats[k] = self.sensors[k]

            sb = list(self._short_buf[k])
            lb = list(self._long_buf[k])

            feats[f"{k}_mean3h"]  = _mean(sb)
            feats[f"{k}_std3h"]   = _std(sb)
            feats[f"{k}_mean24h"] = _mean(lb)
            feats[f"{k}_std24h"]  = _std(lb)

        # Error counts — approximate via degradation level
        for i in range(1, 6):
            feats[f"error_error{i}_count"] = round(self.degradation * random.uniform(0, 3))

        feats["model_idx"] = float(self.model_idx)
        feats["age"]       = float(self.age)

        return feats

    # ── Telemetry row ─────────────────────────────────────────────────────────

    def telemetry_row(self, ts: Optional[datetime] = None) -> Dict:
        """Build a dict suitable for inserting into the telemetry table."""
        if ts is None:
            ts = datetime.now(timezone.utc)
        return {
            "machine_id": self.machine_id,
            "timestamp":  ts,
            **{k: round(v, 4) for k, v in self.sensors.items()},
        }

    def set_scenario(self, scenario: str, reset_degradation: bool = False):
        """Switch to a new scenario mid-simulation."""
        self.scenario = scenario
        if reset_degradation:
            self.degradation = 0.0


# ── Helper statistics ──────────────────────────────────────────────────────────

def _mean(values) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return (sum((x - m) ** 2 for x in values) / len(values)) ** 0.5
