import { useNavigate } from 'react-router-dom';

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="landing">
      <div className="landing-inner">
        <div className="landing-badge">
          <div className="brand-dot" />
          AI-Powered Predictive Maintenance
        </div>

        <h1 className="landing-title">
          Monitor your fleet.<br />
          Predict failures.<br />
          Prevent downtime.
        </h1>

        <p className="landing-sub">
          FleetGuard uses machine learning to analyze real-time telemetry from
          connected vehicles and predict mechanical failures before they happen.
        </p>

        <button className="landing-cta" onClick={() => navigate('/fleet')}>
          <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
          Explore Demo Fleet
        </button>

        <div className="landing-stats">
          <div>
            <div className="landing-stat-value">100</div>
            <div className="landing-stat-label">Machines Monitored</div>
          </div>
          <div>
            <div className="landing-stat-value">97.6%</div>
            <div className="landing-stat-label">Model AUC-ROC</div>
          </div>
          <div>
            <div className="landing-stat-value">876K</div>
            <div className="landing-stat-label">Telemetry Rows</div>
          </div>
          <div>
            <div className="landing-stat-value">27</div>
            <div className="landing-stat-label">Engineered Features</div>
          </div>
        </div>
      </div>
    </div>
  );
}
