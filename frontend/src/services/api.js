import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({ baseURL: API_BASE });

// ── Fleet ──────────────────────────────────────────────────────────────────────
export const getFleetOverview = () => api.get('/api/fleet').then(r => r.data);
export const getVehicles      = () => api.get('/api/vehicles').then(r => r.data);

// ── Vehicles ───────────────────────────────────────────────────────────────────
export const getVehicle   = (id) => api.get(`/api/vehicles/${id}`).then(r => r.data);
export const getTelemetry = (id) => api.get(`/api/vehicles/${id}/telemetry`).then(r => r.data);
export const getPrediction = (id) => api.get(`/api/vehicles/${id}/prediction`).then(r => r.data);

// ── Simulation ─────────────────────────────────────────────────────────────────
export const getSimulationStatus = () =>
  api.get('/api/simulation/status').then(r => r.data);

export const startSimulation = (scenario = 'bearing_wear', speed = 1.0, demo = false) =>
  api.post('/api/simulation/start', { scenario, speed, demo }).then(r => r.data);

export const stopSimulation = () =>
  api.post('/api/simulation/stop').then(r => r.data);

export const resetSimulation = () =>
  api.post('/api/simulation/reset').then(r => r.data);
