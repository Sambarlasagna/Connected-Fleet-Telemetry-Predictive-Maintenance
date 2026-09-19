from pydantic import BaseModel
from typing import Optional, Dict, List, Any


class MachineBase(BaseModel):
    machine_id: int
    machine_name: str
    model: str
    age: int
    risk_level: str
    failure_probability: float


class MachineDetail(MachineBase):
    pass


class TelemetryPoint(BaseModel):
    timestamp: str
    volt: float
    rotate: float
    pressure: float
    vibration: float


class PredictionResponse(BaseModel):
    machine_id: int
    failure_probability: float
    risk_level: str
    recommended_action: str
    explanation: Dict[str, float]


class AlertResponse(BaseModel):
    machine_id: int
    machine_name: str
    risk_level: str
    failure_probability: float
    message: str


class FleetOverview(BaseModel):
    total: int
    healthy_count: int
    at_risk_count: int
    critical_count: int
    avg_risk: float
    recent_alerts: List[AlertResponse]


# ── Simulation schemas ─────────────────────────────────────────────────────────

class SimulationStartRequest(BaseModel):
    scenario: str = "bearing_wear"   # default scenario for all active machines
    speed: float = 1.0               # 1.0, 2.0, or 5.0
    demo: bool = False               # if True, use the scripted interview demo


class SimulationStatusResponse(BaseModel):
    is_running: bool
    is_demo: bool
    scenario: str
    speed: float
    tick_count: int
    active_machines: List[int]
    started_at: Optional[str]
    vehicle_degradations: Dict[int, float]


class SimulationResetResponse(BaseModel):
    success: bool
    message: str
