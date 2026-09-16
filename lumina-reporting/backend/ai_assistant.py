"""Lumina AI -- the persistent assistant embedded in the app shell.

Deliberately thin and read-only: it answers questions grounded in a JSON
snapshot of real Lumina data (assembled below, same underlying queries the
REST API itself uses), and it never takes an action -- no tool-calling loop,
no write access. A human always drives approvals, edits, and distribution;
the assistant's job is to save that human time finding and summarizing
things, not to act on their behalf. See mcp_server.py for the same
read-only philosophy applied to external MCP clients instead of this
in-app chat surface.

Talks to the Claude API directly over HTTPS (no SDK dependency, matching
this repo's existing connectors/api_connector.py pattern) so it's easy to
mock in tests without an extra library.
"""

import json
import os

import requests

from database import db_session
from models import Client, Report
from routes.book import _client_aum
import workflow_engine

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
ANTHROPIC_MODEL = os.environ.get('ANTHROPIC_MODEL', 'claude-sonnet-5')
ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages'

SYSTEM_PROMPT = """You are Lumina AI, an assistant embedded throughout Lumina, an institutional \
financial reporting platform used by client reporting, client services, and compliance staff.

Ground every answer in the JSON data provided below. Never invent figures, client names, \
report statuses, or holdings that aren't in it -- if the data doesn't cover the question, say \
so plainly rather than guessing. You cannot take actions in the system yourself (you cannot \
approve, distribute, edit, or send anything) -- when a request implies an action, describe \
what the user should do and, per Lumina's configured workflow, who needs to sign off. You can \
draft starting points (for example, a report template outline or a summary paragraph) but \
always say plainly that a human needs to review and run it through the normal process before \
it's used for real.

Current user role: {role}
Current page: {page}

Data available to you right now:
{context_json}
"""


class AssistantError(Exception):
    """Raised when a configured Claude API call itself fails (network, 4xx/5xx, bad body)."""


def _firm_snapshot():
    clients = db_session.query(Client).all()
    total_aum = 0.0
    for institution in clients:
        aum, _ = _client_aum(institution.id)
        if aum:
            total_aum += aum

    status_counts = {}
    for (status,) in db_session.query(Report.status).all():
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        'clientCount': len(clients),
        'totalAum': total_aum,
        'reportsByStatus': status_counts,
    }


def _report_snapshot(report_id):
    report = db_session.query(Report).filter_by(id=report_id).first()
    if not report:
        return None
    return {
        'id': report.id,
        'title': report.title,
        'status': report.status,
        'reportType': report.report_type,
        'team': report.team,
        'isDistributed': workflow_engine.report_is_distributed(report),
        'updatedAt': report.updated_at.isoformat() if report.updated_at else None,
    }


def _client_snapshot(client_id):
    institution = db_session.query(Client).filter_by(id=client_id).first()
    if not institution:
        return None
    aum, as_of = _client_aum(client_id)
    return {
        'id': institution.id,
        'name': institution.name,
        'aum': aum,
        'asOfDate': as_of.isoformat() if as_of else None,
    }


def build_context(report_id=None, client_id=None):
    context = {'firm': _firm_snapshot()}
    if report_id:
        report_snapshot = _report_snapshot(report_id)
        if report_snapshot:
            context['currentReport'] = report_snapshot
    if client_id:
        client_snapshot = _client_snapshot(client_id)
        if client_snapshot:
            context['currentClient'] = client_snapshot
    return context


def ask(message, user, page=None, report_id=None, client_id=None):
    """Returns {'reply': str, 'configured': bool}. Raises AssistantError only
    for a configured-but-failed call -- an unconfigured key is a normal,
    non-error response so the UI can render it inline instead of an error state."""
    if not ANTHROPIC_API_KEY:
        return {
            'reply': (
                "Lumina AI isn't connected yet in this environment -- ask an admin to set "
                "the ANTHROPIC_API_KEY environment variable to turn on the assistant."
            ),
            'configured': False,
        }

    context = build_context(report_id=report_id, client_id=client_id)
    system_prompt = SYSTEM_PROMPT.format(
        role=user.get('role', 'staff'),
        page=page or 'unknown',
        context_json=json.dumps(context, indent=2),
    )

    try:
        response = requests.post(
            ANTHROPIC_API_URL,
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': ANTHROPIC_MODEL,
                'max_tokens': 1024,
                'system': system_prompt,
                'messages': [{'role': 'user', 'content': message}],
            },
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise AssistantError(f"Lumina AI request failed: {error}") from error

    try:
        body = response.json()
    except ValueError as error:
        raise AssistantError(f"Lumina AI returned an unreadable response: {error}") from error

    reply_text = ''.join(
        block.get('text', '') for block in body.get('content', []) if block.get('type') == 'text'
    )
    return {'reply': reply_text or "Lumina AI didn't return a response -- try rephrasing.", 'configured': True}
