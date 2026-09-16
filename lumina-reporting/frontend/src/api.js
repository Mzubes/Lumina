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

// Public report links carry no login -- these hit the same API but never
// attach an Authorization header, since the token in the URL path is itself
// the credential.
export async function publicFetch(path) {
  if (isDemoMode) throw new Error('API is not configured');
  const response = await fetch(`${apiBaseUrl}${path}`);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || `Request failed (${response.status})`);
  return data;
}

// Fetches a binary response (a PDF, typically) and hands back a blob: URL an
// <iframe> can point at directly -- browsers render a PDF blob with their
// own native viewer, so this needs no PDF-viewer library. Caller owns the
// URL and must revoke it once done (e.g. on unmount or before fetching a
// fresh one) to avoid leaking memory.
// Fires a report workflow action -- either a diagram edge (generic
// /transition endpoint, action.edgeId) or a legacy fixed verb (one of the
// six original per-status routes, action.verb as its URL segment, e.g.
// 'request-changes'). ReportsTable.js's getReportActions decides which
// shape a given report/action needs; callers (reports.js, MyQueue.js,
// ReportDetail.js) just pass along whatever it returned so the edge-vs-verb
// branching lives in exactly one place.
export async function fireReportAction(reportId, action, note) {
  if (action.kind === 'edge') {
    return apiFetch(`/api/reports/${reportId}/transition`, {
      method: 'POST',
      body: JSON.stringify(note ? { edge_id: action.edgeId, note } : { edge_id: action.edgeId }),
    });
  }
  return apiFetch(`/api/reports/${reportId}/${action.verb}`, {
    method: 'POST',
    body: JSON.stringify(note ? { note } : {}),
  });
}

export async function apiFetchBlobUrl(path) {
  if (isDemoMode) throw new Error('API is not configured');
  const token = window.localStorage.getItem('lumina_token');
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${apiBaseUrl}${path}`, { headers });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  const blob = await response.blob();
  return window.URL.createObjectURL(blob);
}

// POST body -> blob: URL. Used by the template editor's live preview, which
// has to send the in-progress (unsaved) template state as the request body
// rather than fetch by id, unlike apiFetchBlobUrl above.
export async function apiPostBlobUrl(path, body) {
  if (isDemoMode) throw new Error('API is not configured');
  const token = window.localStorage.getItem('lumina_token');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${apiBaseUrl}${path}`, { method: 'POST', headers, body: JSON.stringify(body) });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.message || `Request failed (${response.status})`);
  }
  const blob = await response.blob();
  return window.URL.createObjectURL(blob);
}

// Same as apiFetchBlobUrl but for a public, no-auth export route.
export async function publicFetchBlobUrl(path) {
  if (isDemoMode) throw new Error('API is not configured');
  const response = await fetch(`${apiBaseUrl}${path}`);
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  const blob = await response.blob();
  return window.URL.createObjectURL(blob);
}

export async function apiDownload(path) {
  if (isDemoMode) throw new Error('Exporting becomes available when the API URL is configured.');
  const token = window.localStorage.getItem('lumina_token');
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${apiBaseUrl}${path}`, { headers });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.message || `Request failed (${response.status})`);
  }
  const blob = await response.blob();
  const disposition = response.headers.get('Content-Disposition') || '';
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : 'download';

  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
