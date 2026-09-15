import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getFleetOverview, getVehicles } from '../services/api';

const RISK_ICON = { healthy: '🟢', at_risk: '🟡', critical: '🔴' };
const RISK_LABEL = { healthy: 'Healthy', at_risk: 'At Risk', critical: 'Critical' };

function StatCard({ label, value, sub, color }) {
  return (
    <div className="card card-sm">
      <div className="card-title">{label}</div>
      <div className="stat-value" style={color ? { color } : {}}>{value}</div>
      {sub && <div className="stat-label">{sub}</div>}
    </div>
  );
}

function RiskBadge({ level }) {
  return (
    <span className={`badge badge-${level}`}>
      <span className="badge-dot" />
      {RISK_LABEL[level] ?? level}
    </span>
  );
}

function MachineCard({ machine, onClick }) {
  const pct = Math.round(machine.failure_probability * 100);
  return (
    <div className={`machine-card ${machine.risk_level}`} onClick={onClick}>
      <div className="machine-card-name">{machine.machine_name}</div>
      <div className="machine-card-model">{machine.model} · Age {machine.age}y</div>
      <div className={`machine-card-risk ${machine.risk_level}`}>{pct}%</div>
      <div className="stat-label">failure risk</div>
      <div className="progress-bar" style={{ marginTop: 10 }}>
        <div
          className="progress-fill"
          style={{
            width: `${pct}%`,
            background: machine.risk_level === 'critical' ? 'var(--critical)'
              : machine.risk_level === 'at_risk' ? 'var(--at-risk)'
              : 'var(--healthy)',
          }}
        />
      </div>
    </div>
  );
}

export default function FleetDashboard() {
  const navigate = useNavigate();
  const [overview, setOverview] = useState(null);
  const [machines, setMachines] = useState([]);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([getFleetOverview(), getVehicles()])
      .then(([ov, ms]) => { setOverview(ov); setMachines(ms); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="loading-wrap">
      <div className="spinner" />
      <span>Loading fleet data…</span>
    </div>
  );

  if (error) return (
    <div className="error-wrap">
      <div style={{ fontSize: '2rem' }}>⚠️</div>
      <div>Could not reach the API: {error}</div>
      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        Make sure the backend is running on port 8000
      </div>
    </div>
  );

  const filtered = filter === 'all' ? machines : machines.filter(m => m.risk_level === filter);
  const avgPct = Math.round((overview?.avg_risk ?? 0) * 100);

  return (
    <main className="page-content">
      {/* Stats */}
      <div className="stats-grid">
        <StatCard label="Total Machines" value={overview.total} />
        <StatCard label="Healthy" value={overview.healthy_count} color="var(--healthy)" />
        <StatCard label="At Risk" value={overview.at_risk_count} color="var(--at-risk)" />
        <StatCard label="Critical" value={overview.critical_count} color="var(--critical)" />
        <div className="card card-sm" style={{ gridColumn: 'span 1' }}>
          <div className="card-title">Avg Failure Risk</div>
          <div className="stat-value">{avgPct}%</div>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{
                width: `${avgPct}%`,
                background: avgPct >= 70 ? 'var(--critical)' : avgPct >= 40 ? 'var(--at-risk)' : 'var(--healthy)',
              }}
            />
          </div>
        </div>
      </div>

      <div className="two-col" style={{ alignItems: 'start' }}>
        {/* Machine grid */}
        <div style={{ gridColumn: '1 / -1' }}>
          <div className="section-header">
            <span className="section-title">Fleet Machines</span>
            <span className="section-count">{filtered.length} shown</span>
          </div>

          <div className="filter-bar">
            {['all', 'critical', 'at_risk', 'healthy'].map(f => (
              <button
                key={f}
                className={`filter-btn ${filter === f ? 'active' : ''}`}
                onClick={() => setFilter(f)}
              >
                {f === 'all' ? 'All' : RISK_LABEL[f]}
              </button>
            ))}
          </div>

          <div className="machines-grid">
            {filtered.map(m => (
              <MachineCard
                key={m.machine_id}
                machine={m}
                onClick={() => navigate(`/machine/${m.machine_id}`)}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Alerts panel */}
      {overview.recent_alerts?.length > 0 && (
        <div className="card" style={{ marginTop: 24 }}>
          <div className="section-header">
            <span className="section-title">Active Alerts</span>
            <span className="section-count">{overview.recent_alerts.length} alerts</span>
          </div>
          {overview.recent_alerts.map(a => (
            <div
              key={a.machine_id}
              className="alert-item"
              style={{ cursor: 'pointer' }}
              onClick={() => navigate(`/machine/${a.machine_id}`)}
            >
              <span className="alert-icon">{RISK_ICON[a.risk_level]}</span>
              <div className="alert-body">
                <div className="alert-name">{a.machine_name}</div>
                <div className="alert-msg">{a.message}</div>
              </div>
              <span className={`alert-prob ${a.risk_level}`}>
                {Math.round(a.failure_probability * 100)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
