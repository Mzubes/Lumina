import React from 'react';
import { HashRouter, NavLink, Navigate, Route, Routes } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import Distribution from './components/Distribution';
import Approvals from './components/approvals';
import DataHub from './components/datahub';
import Reports from './components/reports';
import Login from './pages/Login';
import ClientPortal from './pages/ClientPortal';

const navItems = [
  ['/', 'Dashboard'], ['/data-hub', 'Data Hub'], ['/reports', 'Reports'],
  ['/approvals', 'Approvals'], ['/distribution', 'Distribution'],
  ['/client-portal', 'Client Portal'],
];

function App() {
  return (
    <HashRouter>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="brand">Lumina</div>
          <div className="brand-subtitle">Institutional Reporting</div>
          <nav>{navItems.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/'}>{label}</NavLink>
          ))}</nav>
          <NavLink className="login-link" to="/login">Sign in</NavLink>
        </aside>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/data-hub" element={<DataHub />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/approvals" element={<Approvals />} />
            <Route path="/distribution" element={<Distribution />} />
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
