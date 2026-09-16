"""Lumina's MCP (Model Context Protocol) server.

Exposes a small, curated, READ-ONLY set of tools over the existing Lumina
REST API so Claude (or any other MCP client) can answer questions about
reports, workflow, and client books without a human copy-pasting exports
into a chat window.

The one hard requirement, and the reason this file exists as a thin proxy
rather than a second copy of the query logic: every tool call must run
with the *calling user's own* Lumina role and permissions, never a shared
service account. There is no separate MCP credential -- a client
authenticates with the exact same JWT `/api/auth/login` already issues,
`LuminaTokenVerifier` verifies it the same way `routes/auth.require_auth`
does, and every tool forwards that same token to the real API as a normal
`Authorization: Bearer ...` header. The REST layer's own scoping
(`_scoped_query`, role checks, `report_is_distributed`, etc.) is what
actually enforces who can see what -- this file adds no authorization
logic of its own, so it can't drift from it.

Run standalone (separate process from the Flask app -- FastMCP's
streamable-http transport is ASGI, the Flask app is WSGI):

    JWT_SECRET_KEY=... LUMINA_API_BASE_URL=http://localhost:5000 \\
        python mcp_server.py

Deliberately NOT included yet: any tool that takes an action (approving,
distributing, editing a report). Read-only lookups are a much smaller
trust decision than letting an agent fire a workflow transition -- see
the roadmap's Open Questions before adding write tools.
"""

import os

import httpx
import jwt
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP

LUMINA_API_BASE_URL = os.environ.get('LUMINA_API_BASE_URL', 'http://localhost:5000')
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'development-only-jwt-secret')
MCP_ISSUER_URL = os.environ.get('MCP_ISSUER_URL', LUMINA_API_BASE_URL)
MCP_RESOURCE_URL = os.environ.get('MCP_RESOURCE_URL', 'http://localhost:8000')


class LuminaTokenVerifier(TokenVerifier):
    """Verifies the caller's actual Lumina session JWT -- the same secret
    and algorithm as routes/auth.py's require_auth, so a token is valid
    here if and only if it's valid against the real API."""

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        except jwt.PyJWTError:
            return None
        return AccessToken(
            token=token,
            client_id=str(payload.get('user_id', '')),
            scopes=[payload.get('role', '')],
            subject=str(payload.get('user_id', '')),
            claims=payload,
        )


mcp = FastMCP(
    name='lumina',
    instructions=(
        "Read-only tools over the Lumina institutional reporting platform. "
        "Every call runs with the calling user's own Lumina role and "
        "permissions -- results are scoped exactly as they would be inside "
        "the Lumina app itself, nothing more."
    ),
    token_verifier=LuminaTokenVerifier(),
    auth=AuthSettings(
        issuer_url=MCP_ISSUER_URL,
        resource_server_url=MCP_RESOURCE_URL,
        # Lumina JWTs carry no 'aud'/resource claim to check against --
        # LuminaTokenVerifier's own signature check against JWT_SECRET_KEY
        # is what proves a token is a real Lumina session, not an audience
        # match. Leave the SDK's separate resource-indicator check off.
        validate_token_resource=False,
    ),
)


class LuminaAuthError(RuntimeError):
    """No verified Lumina session on this request -- surfaced to the
    calling model as a tool error rather than an empty/misleading result."""


class LuminaAPIError(RuntimeError):
    """The real API rejected or failed the forwarded request. Message is
    the API's own response body where available, so a 403 reads as
    'Insufficient permissions' rather than a raw HTTP status."""


def _bearer_headers() -> dict:
    access_token = get_access_token()
    if access_token is None:
        raise LuminaAuthError('No authenticated Lumina session for this request.')
    return {'Authorization': f'Bearer {access_token.token}'}


async def _get(path: str, params: dict | None = None) -> dict | list:
    params = {k: v for k, v in (params or {}).items() if v is not None}
    async with httpx.AsyncClient(base_url=LUMINA_API_BASE_URL, timeout=15.0) as client:
        response = await client.get(path, params=params, headers=_bearer_headers())
    if response.is_error:
        try:
            detail = response.json().get('message', response.text)
        except ValueError:
            detail = response.text
        raise LuminaAPIError(f'{response.status_code}: {detail}')
    return response.json()


@mcp.tool()
async def get_report(report_id: int) -> dict:
    """Look up a single report: its status, team, report type, template,
    active workflow step(s), and which actions the calling user is
    currently eligible to take on it."""
    return await _get(f'/api/reports/{report_id}')


@mcp.tool()
async def list_reports(
    status: str | None = None,
    team: str | None = None,
    report_type: str | None = None,
    client_id: int | None = None,
    q: str | None = None,
) -> list:
    """List reports visible to the calling user. All filters are optional
    and combine with AND: status (e.g. 'review', 'approved'), team,
    report_type (factsheet/marketing/performance/holdings/pitchbook/
    meeting_pack/custom), client_id, or q (a free-text title search)."""
    return await _get('/api/reports', {
        'status': status, 'team': team, 'report_type': report_type,
        'client_id': client_id, 'q': q,
    })


@mcp.tool()
async def my_queue() -> list:
    """Everything currently actionable by the calling user in one place --
    the same list shown on their My Queue page -- each entry annotated
    with why it's there (a workflow action they can take, a component
    review pending their sign-off, or both)."""
    return await _get('/api/reports/my-queue')


@mcp.tool()
async def get_report_history(report_id: int) -> list:
    """Full status-transition audit trail for one report: every step it
    moved through, who moved it, and when."""
    return await _get(f'/api/reports/{report_id}/history')


@mcp.tool()
async def get_eligible_actions(report_id: int) -> list:
    """Which workflow actions (edges on this report's diagram) the calling
    user is currently allowed to fire -- e.g. approve, request changes,
    distribute -- and nothing they aren't permitted to do."""
    return await _get(f'/api/reports/{report_id}/eligible-actions')


@mcp.tool()
async def get_activity_log(limit: int = 50) -> list:
    """Firm-wide activity/audit log across every report: transitions,
    component-review sign-offs, and distribution-link creation, merged and
    sorted most-recent-first. Restricted to admin/editor/viewer roles by
    the underlying API -- a client-role token will get a permission error
    here, same as it would calling the API directly."""
    return await _get('/api/activity', {'limit': limit})


@mcp.tool()
async def get_portfolio(client_id: int | None = None) -> dict:
    """Holdings and performance snapshots for a client's book -- the same
    data shown on the Client Portal or Internal Portal. A client-role
    caller always gets their own book and client_id is ignored; a staff
    caller must pass client_id."""
    return await _get('/api/portfolio', {'client_id': client_id})


@mcp.tool()
async def get_dashboard_summary() -> dict:
    """Firm-level production aggregates: report counts by status, reports
    generated by week, and pending component reviews."""
    return await _get('/api/dashboard')


if __name__ == '__main__':
    mcp.run(transport='streamable-http')
