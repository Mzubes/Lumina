import contextlib
import threading

import pytest
from werkzeug.serving import make_server

import mcp_server
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken

# mcp_server.py talks to the real API over HTTP (it has to forward the
# caller's own bearer token the same way a browser would), so these tests
# spin up the actual Flask app on a real socket rather than using the
# Flask test client.

class _ServerThread(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.server = make_server('127.0.0.1', 0, app)
        self.port = self.server.server_port

    def run(self):
        self.server.serve_forever()

    def stop(self):
        self.server.shutdown()

@pytest.fixture()
def live_server(app, monkeypatch):
    thread = _ServerThread(app)
    thread.start()
    base_url = f'http://127.0.0.1:{thread.port}'
    monkeypatch.setattr(mcp_server, 'LUMINA_API_BASE_URL', base_url)
    monkeypatch.setattr(mcp_server, 'JWT_SECRET_KEY', 'test-jwt-secret')
    yield base_url
    thread.stop()
    thread.join(timeout=2)

def _token(headers):
    return headers['Authorization'].removeprefix('Bearer ').strip()

@contextlib.contextmanager
def _as_token(token):
    access_token = AccessToken(token=token, client_id='test-client', scopes=[''])
    reset = auth_context_var.set(AuthenticatedUser(access_token))
    try:
        yield
    finally:
        auth_context_var.reset(reset)

# --- token verification -----------------------------------------------

async def test_verifier_accepts_a_real_lumina_token(live_server, auth_headers, monkeypatch):
    verifier = mcp_server.LuminaTokenVerifier()
    result = await verifier.verify_token(_token(auth_headers))
    assert result is not None
    assert result.claims['role'] == 'admin'

async def test_verifier_rejects_garbage(live_server):
    verifier = mcp_server.LuminaTokenVerifier()
    assert await verifier.verify_token('not-a-real-token') is None

# --- tools require an authenticated context -----------------------------

async def test_tool_without_a_session_raises_auth_error(live_server):
    with pytest.raises(mcp_server.LuminaAuthError):
        await mcp_server.get_dashboard_summary()

# --- tools forward the caller's own token, and inherit its scoping -----

async def test_my_queue_runs_as_the_calling_user(live_server, editor_headers):
    with _as_token(_token(editor_headers)):
        result = await mcp_server.my_queue()
    assert isinstance(result, list)

async def test_my_queue_rejects_a_client_role_token(live_server, client_portal_headers):
    # /api/reports/my-queue is admin/editor/viewer only -- a client-role
    # caller should see the same 403 an MCP tool user would get calling
    # the REST API directly, not a silently empty result.
    with _as_token(_token(client_portal_headers)):
        with pytest.raises(mcp_server.LuminaAPIError) as excinfo:
            await mcp_server.my_queue()
    assert '403' in str(excinfo.value)

async def test_get_portfolio_scopes_a_client_caller_to_their_own_book(
    live_server, client_portal_headers, sample_client, sample_holding,
):
    with _as_token(_token(client_portal_headers)):
        result = await mcp_server.get_portfolio()
    assert len(result['holdings']) == 1
    assert result['holdings'][0]['security_name'] == 'Apple Inc.'

async def test_get_portfolio_requires_client_id_for_a_staff_caller(live_server, auth_headers):
    with _as_token(_token(auth_headers)):
        with pytest.raises(mcp_server.LuminaAPIError) as excinfo:
            await mcp_server.get_portfolio()
    assert '400' in str(excinfo.value)

async def test_get_portfolio_with_explicit_client_id_as_staff(
    live_server, auth_headers, sample_client, sample_holding,
):
    with _as_token(_token(auth_headers)):
        result = await mcp_server.get_portfolio(client_id=sample_client)
    assert len(result['holdings']) == 1

async def test_list_reports_filters_forward_correctly(live_server, auth_headers, sample_template):
    with _as_token(_token(auth_headers)):
        reports = await mcp_server.list_reports(status='draft')
    assert reports == []

async def test_get_dashboard_summary_as_admin(live_server, auth_headers):
    with _as_token(_token(auth_headers)):
        result = await mcp_server.get_dashboard_summary()
    assert 'reportsByStatus' in result or isinstance(result, dict)

async def test_get_activity_log_rejects_client_role(live_server, client_portal_headers):
    with _as_token(_token(client_portal_headers)):
        with pytest.raises(mcp_server.LuminaAPIError) as excinfo:
            await mcp_server.get_activity_log()
    assert '403' in str(excinfo.value)
