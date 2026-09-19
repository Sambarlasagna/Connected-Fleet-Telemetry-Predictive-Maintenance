import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';
import { getVehicle, getTelemetry, getPrediction, getSimulationStatus } from '../services/api';

const RISK_COLOR = {
  healthy: 'var(--healthy)',
  at_risk: 'var(--at-risk)',
  critical: 'var(--critical)',
};
const RISK_LABEL = { healthy: 'Healthy', at_risk: 'At Risk', critical: 'Critical' };

const SENSOR_CONFIG = [
  { key: 'volt',      label: 'Voltage (V)',    color: '#6366f1' },
  { key: 'rotate',    label: 'Rotation (RPM)', color: '#06b6d4' },
  { key: 'pressure',  label: 'Pressure (PSI)', color: '#f59e0b' },
  { key: 'vibration', label: 'Vibration',      color: '#ef4444' },
];

const FEATURE_NAMES = {
  volt: 'Voltage', rotate: 'Rotation', pressure: 'Pressure', vibration: 'Vibration',
  volt_mean3h: 'Voltage (3h avg)', rotate_mean3h: 'Rotation (3h avg)',
  pressure_mean3h: 'Pressure (3h avg)', vibration_mean3h: 'Vibration (3h avg)',
  volt_std3h: 'Voltage Std (3h)', rotate_std3h: 'Rotation Std (3h)',
  pressure_std3h: 'Pressure Std (3h)', vibration_std3h: 'Vibration Std (3h)',
  volt_mean24h: 'Voltage (24h avg)', rotate_mean24h: 'Rotation (24h avg)',
  pressure_mean24h: 'Pressure (24h avg)', vibration_mean24h: 'Vibration (24h avg)',
  volt_std24h: 'Voltage Std (24h)', rotate_std24h: 'Rotation Std (24h)',
  pressure_std24h: 'Pressure Std (24h)', vibration_std24h: 'Vibration Std (24h)',
  error_error1_count: 'Error Type 1', error_error2_count: 'Error Type 2',
  error_error3_count: 'Error Type 3', error_error4_count: 'Error Type 4',
  error_error5_count: 'Error Type 5',
  model_idx: 'Machine Model', age: 'Machine Age',
};

function TelemetryChart({ data, sensorKey, label, color, live }) {
  const formatted = data.map((d, i) => ({
    i,
    value: typeof d[sensorKey] === 'number' ? parseFloat(d[sensorKey].toFixed(2)) : d[sensorKey],
    time: new Date(d.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
  }));

  return (
    <div className="card card-sm" style={{ position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <div className="chart-title" style={{ margin: 0 }}>{label}</div>
        {live && (
          <span style={{
            fontSize: '0.65rem', background: 'rgba(16,185,129,0.15)',
            color: '#10b981', border: '1px solid rgba(16,185,129,0.3)',
            padding: '1px 6px', borderRadius: 4, fontWeight: 600,
          }}>LIVE</span>
        )}
        {formatted.length > 0 && (
          <span style={{ marginLeft: 'auto', fontSize: '0.8rem', color: color, fontWeight: 700 }}>
            {formatted[formatted.length - 1].value}
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={130}>
        <LineChart data={formatted} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#4a5a7a' }} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 10, fill: '#4a5a7a' }} />
          <Tooltip
            contentStyle={{
              background: '#0e1628', border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 8, fontSize: 12,
            }}
            labelStyle={{ color: '#8b9bbf' }}
            itemStyle={{ color }}
          />
          <Line
            type="monotone" dataKey="value" stroke={color}
            strokeWidth={2} dot={false} activeDot={{ r: 4 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function SHAPChart({ explanation }) {
  if (!explanation || Object.keys(explanation).length === 0) return null;

  const entries = Object.entries(explanation).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const maxAbs = Math.max(...entries.map(([, v]) => Math.abs(v)));

  return (
    <div className="card">
      <div className="section-title" style={{ marginBottom: 20 }}>
        Why is this machine at risk?
      </div>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 16 }}>
        Based on SHAP (SHapley Additive exPlanations) — the top factors driving the ML prediction
      </div>
      {entries.map(([feat, val]) => {
        const pct = maxAbs > 0 ? (Math.abs(val) / maxAbs) * 100 : 0;
        const positive = val > 0;
        return (
          <div key={feat} className="shap-row">
            <div className="shap-label">{FEATURE_NAMES[feat] ?? feat}</div>
            <div className="shap-bar-wrap">
              <div
                className="shap-bar"
                style={{
                  width: `${pct}%`,
                  background: positive ? 'var(--critical)' : 'var(--healthy)',
                  transition: 'width 0.4s ease',
                }}
              />
            </div>
            <div
              className="shap-val"
              style={{ color: positive ? 'var(--critical)' : 'var(--healthy)' }}
            >
              {positive ? '+' : ''}{(val * 100).toFixed(1)}%
            </div>
          </div>
        );
      })}
      <div style={{ marginTop: 16, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
        🔴 Increases failure risk &nbsp;·&nbsp; 🟢 Reduces failure risk
      </div>
    </div>
  );
}

function RiskGauge({ pct, riskLevel, riskColor, action }) {
  return (
    <div className="card" style={{ textAlign: 'center' }}>
      <div className="card-title" style={{ textAlign: 'left', marginBottom: 20 }}>
        Failure Probability
      </div>
      <div className="gauge-wrap">
        {/* Big percentage */}
        <div style={{
          fontSize: '3rem', fontWeight: 800, lineHeight: 1,
          color: riskColor, marginBottom: 12,
          transition: 'color 0.5s ease',
        }}>
          {pct}%
        </div>
        {/* Progress bar */}
        <div className="progress-bar" style={{ width: '100%', height: 12, marginBottom: 12, borderRadius: 6, overflow: 'hidden' }}>
          <div
            className="progress-fill"
            style={{
              width: `${pct}%`, background: riskColor,
              height: '100%', transition: 'width 0.6s ease, background 0.5s ease',
            }}
          />
        </div>
        {/* Risk badge */}
        <div style={{
          display: 'inline-block', padding: '4px 16px', borderRadius: 20,
          background: `${riskColor}22`, border: `1px solid ${riskColor}55`,
          color: riskColor, fontSize: '0.85rem', fontWeight: 600, marginBottom: 12,
        }}>
          {RISK_LABEL[riskLevel] ?? riskLevel}
        </div>
        {action && (
          <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {action}
          </div>
        )}
      </div>
    </div>
  );
}

export default function MachineDetail() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [machine, setMachine]       = useState(null);
  const [telemetry, setTelemetry]   = useState([]);
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState(null);
  const [simRunning, setSimRunning] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const pollRef = useRef(null);

  // Initial load
  useEffect(() => {
    Promise.all([getVehicle(id), getTelemetry(id), getPrediction(id), getSimulationStatus()])
      .then(([m, t, p, sim]) => {
        setMachine(m);
        setTelemetry(t);
        setPrediction(p);
        setSimRunning(sim.is_running && sim.active_machines.includes(parseInt(id)));
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  // Live poll while simulation is active for this machine
  const poll = useCallback(async () => {
    try {
      const [m, t, p, sim] = await Promise.all([
        getVehicle(id), getTelemetry(id), getPrediction(id), getSimulationStatus(),
      ]);
      setMachine(m);
      setTelemetry(t);
      setPrediction(p);
      const active = sim.is_running && sim.active_machines.includes(parseInt(id));
      setSimRunning(active);
      setLastUpdated(new Date());
      if (!active) clearInterval(pollRef.current);
    } catch (_) {}
  }, [id]);

  useEffect(() => {
    if (simRunning) {
      pollRef.current = setInterval(poll, 3000);
    }
    return () => clearInterval(pollRef.current);
  }, [simRunning, poll]);

  if (loading) return (
    <div className="loading-wrap">
      <div className="spinner" />
      <span>Loading machine data…</span>
    </div>
  );

  if (error) return (
    <div className="error-wrap">
      <div style={{ fontSize: '2rem' }}>⚠️</div>
      <div>{error}</div>
    </div>
  );

  const pct       = Math.round((prediction?.failure_probability ?? 0) * 100);
  const riskLevel = prediction?.risk_level ?? machine?.risk_level ?? 'healthy';
  const riskColor = RISK_COLOR[riskLevel] ?? 'var(--text-muted)';
  const machineId = parseInt(id);

  return (
    <main className="page-content">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <button className="back-btn" style={{ margin: 0 }} onClick={() => navigate('/fleet')}>
          ← Back to Fleet
        </button>
        {simRunning && (
          <span style={{
            display: 'flex', alignItems: 'center', gap: 6,
            fontSize: '0.75rem', color: '#10b981',
            background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.25)',
            padding: '4px 10px', borderRadius: 6,
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%', background: '#10b981',
              animation: 'pulse 1.5s infinite',
            }} />
            Live simulation active
            {lastUpdated && (
              <span style={{ color: 'var(--text-muted)', marginLeft: 4 }}>
                · Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            )}
          </span>
        )}
        {!simRunning && (
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Start simulation on the fleet dashboard to see live updates
          </span>
        )}
      </div>

      {/* Header */}
      <div className="detail-header">
        <div>
          <div className="detail-title">{machine.machine_name}</div>
          <div className="detail-meta">
            {machine.model} &nbsp;·&nbsp; Age: {machine.age} years
            &nbsp;·&nbsp; ID: {machine.machine_id}
          </div>
        </div>
        <span className={`badge badge-${riskLevel}`}>
          <span className="badge-dot" />
          {RISK_LABEL[riskLevel]}
        </span>
      </div>

      {/* Gauge + Machine info */}
      <div className="two-col" style={{ marginBottom: 24 }}>
        <RiskGauge
          pct={pct}
          riskLevel={riskLevel}
          riskColor={riskColor}
          action={prediction?.recommended_action}
        />

        <div className="card">
          <div className="card-title" style={{ marginBottom: 16 }}>Machine Info</div>
          {[
            ['Machine ID',  machine.machine_id],
            ['Model',       machine.model],
            ['Age',         `${machine.age} years`],
            ['Risk Level',  RISK_LABEL[riskLevel]],
            ['Failure Prob', `${pct}%`],
            ['Simulation',  simRunning
              ? (machineId <= 10 ? '🟢 Active (machine 1–10)' : '⚪ Not in active set')
              : '⚪ Stopped'],
          ].map(([k, v]) => (
            <div key={k} style={{
              display: 'flex', justifyContent: 'space-between',
              padding: '8px 0', borderBottom: '1px solid var(--border)',
              fontSize: '0.875rem',
            }}>
              <span style={{ color: 'var(--text-secondary)' }}>{k}</span>
              <span style={{ fontWeight: 600 }}>{v}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Telemetry charts */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <div className="section-title" style={{ margin: 0 }}>
          {simRunning && machineId <= 10 ? '⚡ Live Telemetry' : 'Telemetry'}
        </div>
        {telemetry.length > 0 && (
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            {telemetry.length} readings
          </span>
        )}
      </div>

      {telemetry.length > 0 ? (
        <div className="charts-grid" style={{ marginBottom: 24 }}>
          {SENSOR_CONFIG.map(s => (
            <TelemetryChart
              key={s.key}
              data={telemetry}
              sensorKey={s.key}
              label={s.label}
              color={s.color}
              live={simRunning && machineId <= 10}
            />
          ))}
        </div>
      ) : (
        <div className="card" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 32, marginBottom: 24 }}>
          No telemetry data available for this machine yet.
        </div>
      )}

      {/* SHAP */}
      {prediction?.explanation && (
        <SHAPChart explanation={prediction.explanation} />
      )}
    </main>
  );
}
