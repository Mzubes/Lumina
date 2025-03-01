import React from 'react';
import { BrowserRouter as Router, Route, Switch } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import Login from './pages/Login';
import ClientPortal from './pages/ClientPortal';

function App() {
  return (
    <Router>
      <Switch>
        <Route exact path="/" component={Dashboard} />
        <Route path="/login" component={Login} />
        <Route path="/client-portal" component={ClientPortal} />
        {/* Add other routes as needed */}
      </Switch>
    </Router>
  );
}

export default App;
