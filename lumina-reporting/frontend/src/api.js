export const apiBaseUrl = (process.env.REACT_APP_API_BASE_URL || '').replace(/\/$/, '');
export const isDemoMode = !apiBaseUrl;

export async function apiFetch(path, options = {}) {
  if (isDemoMode) throw new Error('API is not configured');
  const token = window.localStorage.getItem('lumina_token');
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${apiBaseUrl}${path}`, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || `Request failed (${response.status})`);
  return data;
}
