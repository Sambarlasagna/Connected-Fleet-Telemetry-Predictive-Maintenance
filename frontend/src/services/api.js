const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

import axios from 'axios';

const api = axios.create({ baseURL: API_BASE });

export const getFleetOverview = () => api.get('/api/fleet').then(r => r.data);
export const getVehicles = () => api.get('/api/vehicles').then(r => r.data);
export const getVehicle = (id) => api.get(`/api/vehicles/${id}`).then(r => r.data);
export const getTelemetry = (id) => api.get(`/api/vehicles/${id}/telemetry`).then(r => r.data);
export const getPrediction = (id) => api.get(`/api/vehicles/${id}/prediction`).then(r => r.data);
