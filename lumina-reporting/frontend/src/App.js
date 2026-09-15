import React, { useEffect, useState } from 'react';
import { HashRouter, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import ActivityLog from './components/ActivityLog';
import Dashboard from './components/Dashboard';
import Clients from './components/clients';
import DataHub from './components/datahub';
import DataSources from './components/datasources';
import Disclosures from './components/disclosures';
import GlobalSearch from './components/GlobalSearch';
import Marketing from './components/marketing';
import MyQueue from './components/MyQueue';
import Pitchbooks from './components/pitchbooks';
import Reports from './components/reports';
import ReportDetail from './components/ReportDetail';
import Templates from './components/templates';
import Users from './components/users';
import WorkflowGroups from './components/workflowGroups';
import Login from './pages/Login';
import ClientPortal from './pages/ClientPortal';
import PublicReport from './pages/PublicReport';
import {
  IconBadge, IconBriefcase, IconCheckCircle, IconClipboard, IconDashboard, IconDatabase, IconDocument,
  IconLayout, IconLogIn, IconLogOut, IconPlug, IconPresentation, IconSearch, IconShield, IconUserGear, IconUsers,
  IconWorkflow,
} from './icons';

// Staff roles -- every non-client role. `client` gets its own separate,
// much shorter nav below rather than a filtered-down version of this one.
const STAFF_ROLES = ['admin', 'editor', 'viewer', 'compliance'];
// Only roles that can actually act on at least one queue item (approve,
// certify, or a component review assigned to them) -- a viewer's queue
// would always be empty, so it isn't offered to them at all.
const QUEUE_ROLES = ['admin', 'editor', 'compliance'];

// Each item's 4th element is the roles that see it; omitted = every staff role.
const navSections = [
  { label: 'Overview', items: [['/', 'Dashboard', IconDashboard, STAFF_ROLES]] },
  { label: 'Data', items: [
    ['/data-hub', 'Data Hub', IconDatabase, STAFF_ROLES],
    ['/data-sources', 'Data Sources', IconPlug, STAFF_ROLES],
  ] },
  { label: 'Production', items: [
    ['/templates', 'Templates', IconLayout, STAFF_ROLES],
    ['/reports', 'Reports', IconDocument, STAFF_ROLES],
    ['/queue', 'My Queue', IconCheckCircle, QUEUE_ROLES],
  ] },
  { label: 'Marketing', items: [
    ['/marketing', 'Fact Sheets & Marketing', IconBadge, STAFF_ROLES],
    ['/pitch-books', 'Pitch Books & Meeting Packs', IconPresentation, STAFF_ROLES],
  ] },
  { label: 'Admin', items: [
    ['/clients', 'Clients & Contacts', IconBriefcase, STAFF_ROLES],
    ['/disclosures', 'Disclosures', IconClipboard, STAFF_ROLES],
    ['/activity', 'Activity Log', IconShield, STAFF_ROLES],
    ['/users', 'Users & Roles', IconUserGear, ['admin']],
    ['/workflow-groups', 'Workflow Groups', IconWorkflow, ['admin']],
  ] },
  // Staff preview of the client-facing portal -- admin only, not a working
  // task for editor/viewer/compliance.
  { label: 'Client', items: [['/client-portal', 'Client Portal (preview)', IconUsers, ['admin']]] },
];

// A client's entire nav -- not a filtered-down staff nav, a separate one.
// Nothing above is relevant to them, so nothing above is offered.
const clientNavSections = [
  { label: 'Client', items: [['/client-portal', 'Client Portal', IconUsers]] },
];

const ROLE_LABEL = { admin: 'Admin', editor: 'Editor', viewer: 'Viewer', client: 'Client', compliance: 'Compliance' };

function Sidebar({ onSearchOpen }) {
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

  const sections = (role === 'client' ? clientNavSections : navSections)
    .map(section => ({
      ...section,
      items: section.items.filter(([, , , roles]) => !roles || roles.includes(role)),
    }))
    .filter(section => section.items.length > 0);

  return (
    <aside className="sidebar">
      <div className="brand-row">
        <div className="brand-mark">L</div>
        <div>
          <div className="brand">Lumina</div>
          <div className="brand-subtitle">Institutional Reporting</div>
        </div>
      </div>
      {role !== 'client' && (
        <button type="button" className="sidebar-search-trigger" onClick={onSearchOpen}>
          <IconSearch /><span>Search</span><span className="sidebar-search-kbd">⌘K</span>
        </button>
      )}
      <nav>
        {sections.map(section => (
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

// Every route below requires a login -- without this, an unauthenticated
// visitor lands directly on a page that quietly renders empty (each
// component's own apiFetch calls fail and get caught into an empty
// fallback state) instead of ever being asked to sign in.
function RequireAuth({ children }) {
  const token = window.localStorage.getItem('lumina_token');
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

function AuthenticatedShell() {
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className="app-shell">
      <Sidebar onSearchOpen={() => setSearchOpen(true)} />
      <GlobalSearch open={searchOpen} onClose={() => setSearchOpen(false)} />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<RequireAuth><Dashboard /></RequireAuth>} />
          <Route path="/data-hub" element={<RequireAuth><DataHub /></RequireAuth>} />
          <Route path="/data-sources" element={<RequireAuth><DataSources /></RequireAuth>} />
          <Route path="/templates" element={<RequireAuth><Templates /></RequireAuth>} />
          <Route path="/reports" element={<RequireAuth><Reports /></RequireAuth>} />
          <Route path="/reports/:id" element={<RequireAuth><ReportDetail /></RequireAuth>} />
          <Route path="/queue" element={<RequireAuth><MyQueue /></RequireAuth>} />
          {/* Retired paths -- keep old links/bookmarks working instead of a silent Dashboard redirect. */}
          <Route path="/approvals" element={<Navigate to="/queue" replace />} />
          <Route path="/compliance" element={<Navigate to="/queue" replace />} />
          <Route path="/marketing" element={<RequireAuth><Marketing /></RequireAuth>} />
          <Route path="/pitch-books" element={<RequireAuth><Pitchbooks /></RequireAuth>} />
          <Route path="/clients" element={<RequireAuth><Clients /></RequireAuth>} />
          <Route path="/disclosures" element={<RequireAuth><Disclosures /></RequireAuth>} />
          <Route path="/activity" element={<RequireAuth><ActivityLog /></RequireAuth>} />
          <Route path="/users" element={<RequireAuth><Users /></RequireAuth>} />
          <Route path="/workflow-groups" element={<RequireAuth><WorkflowGroups /></RequireAuth>} />
          <Route path="/client-portal" element={<RequireAuth><ClientPortal /></RequireAuth>} />
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <HashRouter>
      <Routes>
        {/* Unauthenticated: a distributed report's share link. No sidebar, no
            login, standalone -- everything else lives behind AuthenticatedShell. */}
        <Route path="/public/:token" element={<PublicReport />} />
        <Route path="/*" element={<AuthenticatedShell />} />
      </Routes>
    </HashRouter>
  );
}

export default App;
