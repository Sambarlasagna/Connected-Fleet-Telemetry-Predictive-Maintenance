import { useState, useEffect } from 'react';
import { getMLflowModel, getMLflowRuns } from '../services/api';

/* ── tiny sparkbar component ─────────────────────────────── */
function MetricBar({ value, max = 1.0, color = '#6366f1' }) {
  return (
    <div style={{ background: 'rgba(255,255,255,0.05)', borderRadius: 4, height: 6, width: '100%', marginTop: 4 }}>
      <div style={{ width: `${Math.min((value / max) * 100, 100)}%`, height: '100%', borderRadius: 4, background: color, transition: 'width 0.6s ease' }} />
    </div>
  );
}

/* ── single run row ─────────────────────────────────────── */
function RunRow({ run, isFirst }) {
  const auc       = run.metrics?.auc_roc   ?? 0;
  const f1        = run.metrics?.f1        ?? 0;
  const precision = run.metrics?.precision ?? 0;
  const recall    = run.metrics?.recall    ?? 0;

  const ts = run.start_time
    ? new Date(run.start_time).toLocaleString()
    : '—';

  const badge = isFirst
    ? <span style={{ background:'rgba(99,102,241,0.2)', color:'#818cf8', border:'1px solid rgba(99,102,241,0.4)', borderRadius:4, padding:'1px 7px', fontSize:'0.65rem', fontWeight:700, marginLeft:8 }}>BEST</span>
    : null;

  return (
    <tr style={{ borderBottom: '1px solid var(--border)' }}>
      <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
        {run.run_id}{badge}
      </td>
      <td style={{ padding: '10px 12px', fontSize: '0.8rem' }}>
        n={run.params?.n_estimators} d={run.params?.max_depth} leaf={run.params?.min_samples_leaf}
      </td>
      <td style={{ padding: '10px 12px', textAlign:'right' }}>
        <span style={{ color: auc > 0.95 ? '#34d399' : auc > 0.85 ? '#fbbf24' : '#f87171', fontWeight: 700 }}>
          {auc.toFixed(4)}
        </span>
      </td>
      <td style={{ padding: '10px 12px', textAlign:'right' }}>{f1.toFixed(4)}</td>
      <td style={{ padding: '10px 12px', textAlign:'right' }}>{precision.toFixed(4)}</td>
      <td style={{ padding: '10px 12px', textAlign:'right' }}>{recall.toFixed(4)}</td>
      <td style={{ padding: '10px 12px', fontSize:'0.75rem', color:'var(--text-muted)' }}>{ts}</td>
    </tr>
  );
}

export default function AnalyticsPage() {
  const [modelInfo, setModelInfo] = useState(null);
  const [runs,      setRuns]      = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState(null);

  useEffect(() => {
    Promise.all([getMLflowModel(), getMLflowRuns(20)])
      .then(([model, runsData]) => {
        setModelInfo(model);
        setRuns(runsData.runs || []);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const meta = modelInfo?.meta;
  const prod = modelInfo?.production_version;

  const sortedRuns = [...runs].sort((a, b) => (b.metrics?.auc_roc ?? 0) - (a.metrics?.auc_roc ?? 0));

  return (
    <div className="page-container" style={{ paddingTop: 24 }}>

      {/* ── Header ── */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: '1.6rem', fontWeight: 700, margin: 0 }}>
          ML Ops — Model Registry
        </h1>
        <p style={{ color: 'var(--text-muted)', marginTop: 6, fontSize: '0.9rem' }}>
          MLflow experiment tracking · RandomForest predictive maintenance model
        </p>
      </div>

      {loading && (
        <div style={{ color: 'var(--text-muted)', padding: 40, textAlign: 'center' }}>
          Loading MLflow data...
        </div>
      )}

      {error && (
        <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: 16, color: '#f87171', marginBottom: 20 }}>
          {error}
        </div>
      )}

      {!loading && (
        <>
          {/* ── Production Model Card ── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 28 }}>

            <div className="card" style={{ padding: 20 }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>AUC-ROC</div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: '#34d399' }}>
                {meta?.auc_roc ?? '—'}
              </div>
              <MetricBar value={meta?.auc_roc ?? 0} color="#34d399" />
            </div>

            <div className="card" style={{ padding: 20 }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>F1 Score</div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: '#6366f1' }}>
                {meta?.f1_score ?? '—'}
              </div>
              <MetricBar value={meta?.f1_score ?? 0} color="#6366f1" />
            </div>

            <div className="card" style={{ padding: 20 }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Precision</div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: '#818cf8' }}>
                {meta?.precision ?? '—'}
              </div>
              <MetricBar value={meta?.precision ?? 0} color="#818cf8" />
            </div>

            <div className="card" style={{ padding: 20 }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Recall</div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: '#a78bfa' }}>
                {meta?.recall ?? '—'}
              </div>
              <MetricBar value={meta?.recall ?? 0} color="#a78bfa" />
            </div>

            <div className="card" style={{ padding: 20 }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Registry</div>
              <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text)' }}>
                {modelInfo?.registry_name ?? '—'}
              </div>
              <div style={{ marginTop: 6 }}>
                {prod ? (
                  <span style={{ background: 'rgba(52,211,153,0.15)', color: '#34d399', border: '1px solid rgba(52,211,153,0.3)', borderRadius: 4, padding: '2px 8px', fontSize: '0.72rem', fontWeight: 700 }}>
                    v{prod.version} · Production
                  </span>
                ) : (
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>No production model</span>
                )}
              </div>
            </div>

            <div className="card" style={{ padding: 20 }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Hyperparams</div>
              <div style={{ fontSize: '0.85rem', lineHeight: 1.7, color: 'var(--text)' }}>
                <div>n_estimators: <strong>{meta?.n_estimators ?? '—'}</strong></div>
                <div>max_depth: <strong>{meta?.max_depth ?? '—'}</strong></div>
              </div>
            </div>

          </div>

          {/* ── Experiment Runs Table ── */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '18px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ fontWeight: 700 }}>Experiment Runs</div>
              <a
                href="http://127.0.0.1:5000"
                target="_blank"
                rel="noreferrer"
                style={{ fontSize: '0.78rem', color: '#818cf8', textDecoration: 'none', border: '1px solid rgba(99,102,241,0.3)', borderRadius: 6, padding: '4px 12px' }}
              >
                Open MLflow UI →
              </a>
            </div>

            {sortedRuns.length === 0 ? (
              <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>
                No runs found. Run <code>python ml/training/train_with_mlflow.py</code> to create your first run.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                  <thead>
                    <tr style={{ background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid var(--border)' }}>
                      {['Run ID', 'Hyperparams', 'AUC-ROC ↓', 'F1', 'Precision', 'Recall', 'Timestamp'].map(h => (
                        <th key={h} style={{ padding: '10px 12px', textAlign: h === 'Run ID' || h === 'Hyperparams' || h === 'Timestamp' ? 'left' : 'right', fontWeight: 600, color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sortedRuns.map((run, i) => (
                      <RunRow key={run.run_id} run={run} isFirst={i === 0} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* ── MLflow UI link ── */}
          <div style={{ marginTop: 20, padding: '14px 20px', background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 10, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            <strong style={{ color: 'var(--text)' }}>MLflow Tracking Server</strong> running at{' '}
            <a href="http://127.0.0.1:5000" target="_blank" rel="noreferrer" style={{ color: '#818cf8' }}>http://127.0.0.1:5000</a>
            {' '}· Database: <code style={{ fontSize: '0.78rem' }}>mlruns/mlflow.db</code>
            {' '}· Experiment: <code style={{ fontSize: '0.78rem' }}>fleetguard-predictive-maintenance</code>
          </div>
        </>
      )}
    </div>
  );
}
