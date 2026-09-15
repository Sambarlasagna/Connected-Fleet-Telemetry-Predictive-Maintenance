import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import FleetDashboard from './pages/FleetDashboard';
import MachineDetail from './pages/MachineDetail';
import './index.css';

function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const isLanding = location.pathname === '/';

  if (isLanding) return null;

  return (
    <nav className="navbar">
      <div className="navbar-brand" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
        <div className="brand-dot" />
        FleetGuard
      </div>
      <div className="navbar-links">
        <span
          className={`nav-link ${location.pathname === '/fleet' ? 'active' : ''}`}
          onClick={() => navigate('/fleet')}
        >
          Fleet Dashboard
        </span>
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <Navbar />
        <Routes>
          <Route path="/"                      element={<LandingPage />} />
          <Route path="/fleet"                 element={<FleetDashboard />} />
          <Route path="/machine/:id"            element={<MachineDetail />} />
          <Route path="/machine/:id/prediction"  element={<MachineDetail />} />
          <Route path="/machine/:id/predictions" element={<MachineDetail />} />
          <Route path="*"                       element={<Navigate to="/fleet" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
