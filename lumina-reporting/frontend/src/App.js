import React from 'react';
import { HashRouter, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import Approvals from './components/approvals';
import DataHub from './components/datahub';
import DataSources from './components/datasources';
import Reports from './components/reports';
import Templates from './components/templates';
import Login from './pages/Login';
import ClientPortal from './pages/ClientPortal';
import {
  IconCheckCircle, IconDashboard, IconDatabase, IconDocument,
  IconLayout, IconLogIn, IconLogOut, IconPlug, IconUsers,
} from './icons';

const navItems = [
  ['/', 'Dashboard', IconDashboard],
  ['/data-hub', 'Data Hub', IconDatabase],
  ['/data-sources', 'Data Sources', IconPlug],
  ['/templates', 'Templates', IconLayout],
  ['/reports', 'Reports', IconDocument],
  ['/approvals', 'Approvals', IconCheckCircle],
  ['/client-portal', 'Client Portal', IconUsers],
];

const ROLE_LABEL = { admin: 'Admin', editor: 'Editor', viewer: 'Viewer', client: 'Client' };

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
      <nav>{navItems.map(([to, label, Icon]) => (
        <NavLink key={to} to={to} end={to === '/'}>
          <Icon /><span>{label}</span>
        </NavLink>
      ))}</nav>
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
