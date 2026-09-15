import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts';
import { getVehicle, getTelemetry, getPrediction } from '../services/api';

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

// Friendly display names for SHAP features
const FEATURE_NAMES = {
  volt: 'Voltage',
  rotate: 'Rotation',
  pressure: 'Pressure',
  vibration: 'Vibration',
  volt_mean3h: 'Voltage (3h avg)',
  rotate_mean3h: 'Rotation (3h avg)',
  pressure_mean3h: 'Pressure (3h avg)',
  vibration_mean3h: 'Vibration (3h avg)',
  volt_std3h: 'Voltage Std (3h)',
  rotate_std3h: 'Rotation Std (3h)',
  pressure_std3h: 'Pressure Std (3h)',
  vibration_std3h: 'Vibration Std (3h)',
  volt_mean24h: 'Voltage (24h avg)',
  rotate_mean24h: 'Rotation (24h avg)',
  pressure_mean24h: 'Pressure (24h avg)',
  vibration_mean24h: 'Vibration (24h avg)',
  volt_std24h: 'Voltage Std (24h)',
  rotate_std24h: 'Rotation Std (24h)',
  pressure_std24h: 'Pressure Std (24h)',
  vibration_std24h: 'Vibration Std (24h)',
  error_error1_count: 'Error Type 1',
  error_error2_count: 'Error Type 2',
  error_error3_count: 'Error Type 3',
  error_error4_count: 'Error Type 4',
  error_error5_count: 'Error Type 5',
  model_idx: 'Machine Model',
  age: 'Machine Age',
};

function TelemetryChart({ data, sensorKey, label, color }) {
  const formatted = data.map((d, i) => ({
    i,
    value: d[sensorKey],
    time: new Date(d.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
  }));

  return (
    <div className="card card-sm">
      <div className="chart-title">{label}</div>
      <ResponsiveContainer width="100%" height={130}>
        <LineChart data={formatted} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#4a5a7a' }} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 10, fill: '#4a5a7a' }} />
          <Tooltip
            contentStyle={{
              background: '#0e1628',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: '#8b9bbf' }}
            itemStyle={{ color }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function SHAPChart({ explanation }) {
  if (!explanation || Object.keys(explanation).length === 0) return null;

  const entries = Object.entries(explanation);
  const maxAbs = Math.max(...entries.map(([, v]) => Math.abs(v)));

  return (
    <div className="card">
      <div className="section-title" style={{ marginBottom: 20 }}>Why is this machine at risk?</div>
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
        Red bars increase failure risk · Green bars reduce failure risk
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

  useEffect(() => {
    Promise.all([getVehicle(id), getTelemetry(id), getPrediction(id)])
      .then(([m, t, p]) => { setMachine(m); setTelemetry(t); setPrediction(p); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

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

  const pct = Math.round((prediction?.failure_probability ?? 0) * 100);
  const riskLevel = prediction?.risk_level ?? machine?.risk_level ?? 'healthy';
  const riskColor = RISK_COLOR[riskLevel];

  return (
    <main className="page-content">
      <button className="back-btn" onClick={() => navigate('/fleet')}>
        ← Back to Fleet
      </button>

      {/* Header */}
      <div className="detail-header">
        <div>
          <div className="detail-title">{machine.machine_name}</div>
          <div className="detail-meta">
            {machine.model} &nbsp;·&nbsp; Age: {machine.age} years
          </div>
        </div>
        <span className={`badge badge-${riskLevel}`}>
          <span className="badge-dot" />
          {RISK_LABEL[riskLevel]}
        </span>
      </div>

      {/* Prediction gauge + action */}
      <div className="two-col" style={{ marginBottom: 24 }}>
        <div className="card" style={{ textAlign: 'center' }}>
          <div className="card-title" style={{ textAlign: 'left', marginBottom: 20 }}>
            Failure Probability
          </div>
          <div className="gauge-wrap">
            <div className={`gauge-value ${riskLevel}`}>{pct}%</div>
            <div className="progress-bar" style={{ width: '100%', height: 10 }}>
              <div
                className="progress-fill"
                style={{ width: `${pct}%`, background: riskColor, height: '100%' }}
              />
            </div>
            <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              {prediction?.recommended_action}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-title" style={{ marginBottom: 16 }}>Machine Info</div>
          {[
            ['Machine ID', machine.machine_id],
            ['Model', machine.model],
            ['Age', `${machine.age} years`],
            ['Risk Level', RISK_LABEL[riskLevel]],
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
      {telemetry.length > 0 && (
        <>
          <div className="section-title" style={{ marginBottom: 16 }}>Live Telemetry</div>
          <div className="charts-grid" style={{ marginBottom: 24 }}>
            {SENSOR_CONFIG.map(s => (
              <TelemetryChart
                key={s.key}
                data={telemetry}
                sensorKey={s.key}
                label={s.label}
                color={s.color}
              />
            ))}
          </div>
        </>
      )}

      {/* SHAP explainability */}
      {prediction?.explanation && (
        <SHAPChart explanation={prediction.explanation} />
      )}
    </main>
  );
}
