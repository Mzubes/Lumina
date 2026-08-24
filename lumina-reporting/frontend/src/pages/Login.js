import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, isDemoMode } from '../api';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    if (isDemoMode) {
      setError('Authentication becomes available when the API URL is configured.');
      return;
    }
    try {
      const data = await apiFetch('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
      window.localStorage.setItem('lumina_token', data.token);
      navigate('/');
    } catch (requestError) { setError(requestError.message); }
  };

  return <div className="login">
    <span className="eyebrow">Secure access</span><h1>Sign in</h1>
    <form onSubmit={handleSubmit}>
      <input type="email" placeholder="Email" value={email} onChange={event => setEmail(event.target.value)} required />
      <input type="password" placeholder="Password" value={password} onChange={event => setPassword(event.target.value)} required />
      <button type="submit">Log In</button>
    </form>
    {error && <p className="form-message">{error}</p>}
  </div>;
};

export default Login;
