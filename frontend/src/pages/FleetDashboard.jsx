import { useEffect, useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getFleetOverview, getVehicles,
  getSimulationStatus, startSimulation, stopSimulation, resetSimulation,
} from '../services/api';

const RISK_ICON  = { healthy: '🟢', at_risk: '🟡', critical: '🔴' };
const RISK_LABEL = { healthy: 'Healthy', at_risk: 'At Risk', critical: 'Critical' };

const SCENARIOS = [
  { value: 'bearing_wear',  label: 'Bearing Wear' },
  { value: 'overheat',      label: 'Overheating' },
  { value: 'voltage_spike', label: 'Voltage Spike' },
  { value: 'degradation',   label: 'General Degradation' },
  { value: 'random_fault',  label: 'Random Fault' },
  { value: 'normal',        label: 'Normal Operation' },
];

// ── Sub-components ─────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, color }) {
  return (
    <div className="card card-sm">
      <div className="card-title">{label}</div>
      <div className="stat-value" style={color ? { color } : {}}>{value}</div>
      {sub && <div className="stat-label">{sub}</div>}
    </div>
  );
}

function MachineCard({ machine, onClick, isSimActive }) {
  const pct = Math.round(machine.failure_probability * 100);
  const barColor = machine.risk_level === 'critical' ? 'var(--critical)'
    : machine.risk_level === 'at_risk' ? 'var(--at-risk)'
    : 'var(--healthy)';

  return (
    <div
      className={`machine-card ${machine.risk_level}${isSimActive ? ' sim-active' : ''}`}
      onClick={onClick}
    >
      <div className="machine-card-name">{machine.machine_name}</div>
      <div className="machine-card-model">{machine.model} · Age {machine.age}y</div>
      <div className={`machine-card-risk ${machine.risk_level}`}>{pct}%</div>
      <div className="stat-label">failure risk</div>
      <div className="progress-bar" style={{ marginTop: 10 }}>
        <div className="progress-fill" style={{ width: `${pct}%`, background: barColor }} />
      </div>
    </div>
  );
}

// ── Simulation Control Panel ───────────────────────────────────────────────────

function SimulationPanel({ simStatus, onStart, onStop, onReset, busy }) {
  const [scenario, setScenario] = useState('bearing_wear');
  const [speed, setSpeed]       = useState(1.0);

  const isRunning = simStatus?.is_running;
  const isDemo    = simStatus?.is_demo;

  return (
    <div className="card sim-panel">
      <div className="sim-panel-header">
        <div className="sim-panel-title">
          Simulation Control
          {isRunning && (
            <span className="live-badge">
              <span className="live-dot" /> LIVE
            </span>
          )}
        </div>

        {isRunning && (
          <div className="sim-stats">
            <span>Ticks: <strong>{simStatus.tick_count}</strong></span>
            <span style={{ marginLeft: 12 }}>
              Mode: <strong>{isDemo ? 'DEMO' : simStatus.scenario}</strong>
            </span>
            <span style={{ marginLeft: 12 }}>
              Speed: <strong>{simStatus.speed}x</strong>
            </span>
          </div>
        )}
      </div>

      {!isRunning && (
        <div className="sim-controls">
          {/* Scenario selector */}
          <div className="sim-control-group">
            <label className="sim-label">Fault Scenario</label>
            <select
              className="sim-select"
              value={scenario}
              onChange={e => setScenario(e.target.value)}
              disabled={busy}
            >
              {SCENARIOS.map(s => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>

          {/* Speed selector */}
          <div className="sim-control-group">
            <label className="sim-label">Speed</label>
            <div className="speed-btns">
              {[1.0, 2.0, 5.0].map(s => (
                <button
                  key={s}
                  className={`speed-btn ${speed === s ? 'active' : ''}`}
                  onClick={() => setSpeed(s)}
                  disabled={busy}
                >
                  {s}x
                </button>
              ))}
            </div>
          </div>

          {/* Action buttons */}
          <div className="sim-actions">
            <button
              id="btn-start-sim"
              className="btn-sim btn-start"
              onClick={() => onStart(scenario, speed, false)}
              disabled={busy}
            >
              ▶ Start Simulation
            </button>
            <button
              id="btn-demo-mode"
              className="btn-sim btn-demo"
              onClick={() => onStart(scenario, speed, true)}
              disabled={busy}
              title="Scripted demo: 10 machines degrade dramatically over 90 seconds"
            >
              🎬 Demo Mode
            </button>
          </div>
        </div>
      )}

      {isRunning && (
        <div className="sim-running-actions">
          <button
            id="btn-stop-sim"
            className="btn-sim btn-stop"
            onClick={onStop}
            disabled={busy}
          >
            ⏹ Stop Simulation
          </button>
          <button
            id="btn-reset-sim"
            className="btn-sim btn-reset"
            onClick={onReset}
            disabled={busy}
            title="Stop simulation and restore DB to original seed data"
          >
            ↺ Reset Data
          </button>
        </div>
      )}

      {!isRunning && (
        <button
          id="btn-reset-only"
          className="btn-sim btn-reset"
          onClick={onReset}
          disabled={busy}
          style={{ marginTop: 8 }}
          title="Restore DB to original seed data"
        >
          ↺ Reset Data
        </button>
      )}
    </div>
  );
}

// ── Main Dashboard ─────────────────────────────────────────────────────────────

export default function FleetDashboard() {
  const navigate = useNavigate();

  const [overview, setOverview]     = useState(null);
  const [machines, setMachines]     = useState([]);
  const [filter, setFilter]         = useState('all');
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState(null);
  const [simStatus, setSimStatus]   = useState(null);
  const [busy, setBusy]             = useState(false);

  const pollRef = useRef(null);

  // Initial data load
  useEffect(() => {
    Promise.all([getFleetOverview(), getVehicles(), getSimulationStatus()])
      .then(([ov, ms, sim]) => {
        setOverview(ov);
        setMachines(ms);
        setSimStatus(sim);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // Live polling while simulation is running
  const refresh = useCallback(() => {
    Promise.all([getFleetOverview(), getVehicles(), getSimulationStatus()])
      .then(([ov, ms, sim]) => {
        setOverview(ov);
        setMachines(ms);
        setSimStatus(sim);
      })
      .catch(() => {});   // silently ignore poll errors
  }, []);

  useEffect(() => {
    if (simStatus?.is_running) {
      pollRef.current = setInterval(refresh, 3000);
    } else {
      clearInterval(pollRef.current);
    }
    return () => clearInterval(pollRef.current);
  }, [simStatus?.is_running, refresh]);

  // ── Handlers ────────────────────────────────────────────────────────────────

  const handleStart = async (scenario, speed, demo) => {
    setBusy(true);
    try {
      const status = await startSimulation(scenario, speed, demo);
      setSimStatus(status);
    } catch (e) {
      alert(`Could not start simulation: ${e?.response?.data?.detail ?? e.message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleStop = async () => {
    setBusy(true);
    try {
      const status = await stopSimulation();
      setSimStatus(status);
      refresh();
    } catch (e) {
      alert(`Could not stop simulation: ${e?.response?.data?.detail ?? e.message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async () => {
    if (!window.confirm('Reset all simulation data and restore original seed snapshot?')) return;
    setBusy(true);
    try {
      await resetSimulation();
      // Reload fresh data after reset
      const [ov, ms, sim] = await Promise.all([getFleetOverview(), getVehicles(), getSimulationStatus()]);
      setOverview(ov);
      setMachines(ms);
      setSimStatus(sim);
    } catch (e) {
      alert(`Reset failed: ${e?.response?.data?.detail ?? e.message}`);
    } finally {
      setBusy(false);
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────────

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
  const avgPct   = Math.round((overview?.avg_risk ?? 0) * 100);
  const isSimRunning = simStatus?.is_running;

  return (
    <main className="page-content">

      {/* ── Simulation panel ── */}
      <SimulationPanel
        simStatus={simStatus}
        onStart={handleStart}
        onStop={handleStop}
        onReset={handleReset}
        busy={busy}
      />

      {/* ── KPI Stats ── */}
      <div className="stats-grid" style={{ marginTop: 24 }}>
        <StatCard label="Total Machines" value={overview.total} />
        <StatCard label="Healthy"  value={overview.healthy_count}  color="var(--healthy)" />
        <StatCard label="At Risk"  value={overview.at_risk_count}  color="var(--at-risk)" />
        <StatCard label="Critical" value={overview.critical_count} color="var(--critical)" />
        <div className="card card-sm">
          <div className="card-title">Avg Failure Risk</div>
          <div className="stat-value">{avgPct}%</div>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{
                width: `${avgPct}%`,
                background: avgPct >= 70 ? 'var(--critical)'
                  : avgPct >= 40 ? 'var(--at-risk)'
                  : 'var(--healthy)',
              }}
            />
          </div>
        </div>
      </div>

      {/* ── Machine grid ── */}
      <div style={{ marginTop: 24 }}>
        <div className="section-header">
          <span className="section-title">
            Fleet Machines
            {isSimRunning && (
              <span className="live-badge" style={{ marginLeft: 10 }}>
                <span className="live-dot" /> LIVE
              </span>
            )}
          </span>
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
              isSimActive={isSimRunning && simStatus?.active_machines?.includes(m.machine_id)}
              onClick={() => navigate(`/machine/${m.machine_id}`)}
            />
          ))}
        </div>
      </div>

      {/* ── Alerts panel ── */}
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
