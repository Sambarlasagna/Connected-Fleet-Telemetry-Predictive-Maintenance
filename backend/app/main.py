from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import fleet, vehicles, predictions, simulation

app = FastAPI(
    title="FleetGuard API",
    description="Real-time predictive maintenance platform for connected vehicle fleets.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fleet.router,       prefix="/api", tags=["Fleet"])
app.include_router(vehicles.router,    prefix="/api", tags=["Vehicles"])
app.include_router(predictions.router, prefix="/api", tags=["Predictions"])
app.include_router(simulation.router,  prefix="/api", tags=["Simulation"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "FleetGuard API", "version": "2.0.0"}
