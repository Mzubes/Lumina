import React from 'react';
import { HashRouter, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import Approvals from './components/approvals';
import Compliance from './components/compliance';
import DataHub from './components/datahub';
import DataSources from './components/datasources';
import Marketing from './components/marketing';
import Pitchbooks from './components/pitchbooks';
import Reports from './components/reports';
import Templates from './components/templates';
import Login from './pages/Login';
import ClientPortal from './pages/ClientPortal';
import {
  IconBadge, IconCheckCircle, IconDashboard, IconDatabase, IconDocument,
  IconLayout, IconLogIn, IconLogOut, IconPlug, IconPresentation, IconShield, IconUsers,
} from './icons';

const navSections = [
  { label: 'Overview', items: [['/', 'Dashboard', IconDashboard]] },
  { label: 'Data', items: [
    ['/data-hub', 'Data Hub', IconDatabase],
    ['/data-sources', 'Data Sources', IconPlug],
  ] },
  { label: 'Production', items: [
    ['/templates', 'Templates', IconLayout],
    ['/reports', 'Reports', IconDocument],
    ['/approvals', 'Approvals', IconCheckCircle],
    ['/compliance', 'Compliance', IconShield],
  ] },
  { label: 'Marketing', items: [
    ['/marketing', 'Fact Sheets & Marketing', IconBadge],
    ['/pitch-books', 'Pitch Books & Meeting Packs', IconPresentation],
  ] },
  { label: 'Client', items: [['/client-portal', 'Client Portal', IconUsers]] },
];

const ROLE_LABEL = { admin: 'Admin', editor: 'Editor', viewer: 'Viewer', client: 'Client', compliance: 'Compliance' };

function Sidebar() {
  // useLocation forces a re-render on every navigation (including the
  // post-login/post-logout redirect), so reading localStorage inline here
  // always reflects the current session instead of going stale after login.
  useLocation();
  const navigate = useNavigate();
  const token = window.localStorage.getItem('lumina_token');
  const role = window.localStorage.getItem('lumina_role');

  const handleLogout = () => {
    window.localStorage.removeItem('lumina_token');
    window.localStorage.removeItem('lumina_role');
    window.localStorage.removeItem('lumina_client_id');
    navigate('/login');
  };

  return (
    <aside className="sidebar">
      <div className="brand-row">
        <div className="brand-mark">L</div>
        <div>
          <div className="brand">Lumina</div>
          <div className="brand-subtitle">Institutional Reporting</div>
        </div>
      </div>
      <nav>
        {navSections.map(section => (
          <React.Fragment key={section.label}>
            <div className="nav-section-label">{section.label}</div>
            {section.items.map(([to, label, Icon]) => (
              <NavLink key={to} to={to} end={to === '/'}>
                <Icon /><span>{label}</span>
              </NavLink>
            ))}
          </React.Fragment>
        ))}
      </nav>
      {token ? (
        <button type="button" className="login-link session-link" onClick={handleLogout}>
          <IconLogOut />
          <span>Sign out{role && ROLE_LABEL[role] ? ` — ${ROLE_LABEL[role]}` : ''}</span>
        </button>
      ) : (
        <NavLink className="login-link" to="/login">
          <IconLogIn /><span>Sign in</span>
        </NavLink>
      )}
    </aside>
  );
}

function App() {
  return (
    <HashRouter>
      <div className="app-shell">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/data-hub" element={<DataHub />} />
            <Route path="/data-sources" element={<DataSources />} />
            <Route path="/templates" element={<Templates />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/approvals" element={<Approvals />} />
            <Route path="/compliance" element={<Compliance />} />
            <Route path="/marketing" element={<Marketing />} />
            <Route path="/pitch-books" element={<Pitchbooks />} />
            <Route path="/distribution" element={<Navigate to="/reports" replace />} />
            <Route path="/client-portal" element={<ClientPortal />} />
            <Route path="/login" element={<Login />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </HashRouter>
  );
}

export default App;
