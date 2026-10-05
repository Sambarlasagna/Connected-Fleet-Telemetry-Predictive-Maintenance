from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram, Gauge
import time

from app.routes import fleet, vehicles, predictions, simulation, mlflow_info, monitoring

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

# ── Prometheus HTTP metrics (manual middleware — no instrumentator needed) ──────
_http_requests = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "handler", "status_code"],
)
_http_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "handler"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)
_http_inprogress = Gauge(
    "http_requests_inprogress",
    "HTTP requests currently in progress",
    ["method", "handler"],
)


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    handler = request.url.path
    method  = request.method
    _http_inprogress.labels(method=method, handler=handler).inc()
    start = time.perf_counter()
    try:
        response = await call_next(request)
        duration = time.perf_counter() - start
        _http_requests.labels(method=method, handler=handler, status_code=response.status_code).inc()
        _http_duration.labels(method=method, handler=handler).observe(duration)
        return response
    finally:
        _http_inprogress.labels(method=method, handler=handler).dec()


@app.get("/metrics", include_in_schema=False)
def metrics():
    """Prometheus scrape endpoint — standard HTTP metrics."""
    return PlainTextResponse(
        content=generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )

app.include_router(fleet.router,       prefix="/api", tags=["Fleet"])
app.include_router(vehicles.router,    prefix="/api", tags=["Vehicles"])
app.include_router(predictions.router, prefix="/api", tags=["Predictions"])
app.include_router(simulation.router,  prefix="/api", tags=["Simulation"])
app.include_router(mlflow_info.router, prefix="/api", tags=["MLflow"])
app.include_router(monitoring.router,  prefix="/api", tags=["Monitoring"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "FleetGuard API", "version": "2.0.0"}
