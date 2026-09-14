import React from 'react';
import { HashRouter, NavLink, Navigate, Route, Routes } from 'react-router-dom';
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
  IconLayout, IconLogIn, IconPlug, IconUsers,
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

function App() {
  return (
    <HashRouter>
      <div className="app-shell">
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
          <NavLink className="login-link" to="/login">
            <IconLogIn /><span>Sign in</span>
          </NavLink>
        </aside>
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
