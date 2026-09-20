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
import re

import requests

import ai_actions
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

Format your answer as short, scannable Markdown: **bold** for figures and names, "- " bullets for lists, and short paragraphs. Do not use headings, tables, code blocks, or links in the prose.

After your answer, you may add directives on their own lines, each on one line:

[[action: Short button label | /an/in-app/path]]
[[followup: A short question the user might ask next]]

Use at most 3 actions and 2 followups, and only when they genuinely help. An action is navigation only -- it opens a page the user could reach from the menu anyway, and it can never approve, send, edit, or change anything. Only these paths exist: / (Production Hub), /start, /reports, /reports/{{id}}, /queue, /templates, /data-hub, /data-sources, /marketing, /pitch-books, /clients, /disclosures, /audit-trail, /users, /workflow-groups, /internal-portal, /internal-portal/clients/{{id}}, /client-portal. /reports also accepts ?stuck=1 and ?overdue=1. Never invent a path outside this list, and never link outside the application.

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


# One directive per line, e.g. "[[action: Open the report | /reports/12]]".
# A line-oriented marker rather than a JSON block: the model only has to get
# one line right at a time, and a malformed line is dropped on its own
# instead of costing the whole structured payload.
_DIRECTIVE_RE = re.compile(r'^\s*\[\[(action|followup)\s*:\s*(.+?)\]\]\s*$', re.IGNORECASE | re.MULTILINE)


def parse_directives(reply_text):
    """Split a raw reply into (prose, actions, follow_ups).

    Every proposed link goes through ai_actions.sanitize_actions before it
    leaves this function, so a hallucinated or injected path never reaches
    the UI -- see that module for why that matters.
    """
    raw_actions = []
    follow_ups = []

    for kind, payload in _DIRECTIVE_RE.findall(reply_text or ''):
        if kind.lower() == 'action':
            label, separator, to = payload.partition('|')
            if separator:
                raw_actions.append({'label': label.strip(), 'to': to.strip()})
        else:
            follow_ups.append(payload.strip())

    prose = _DIRECTIVE_RE.sub('', reply_text or '').strip()
    return prose, ai_actions.sanitize_actions(raw_actions), ai_actions.sanitize_follow_ups(follow_ups)


def _money(value):
    if not value:
        return '$0'
    if value >= 1e9:
        return f'${value / 1e9:.2f}B'
    if value >= 1e6:
        return f'${value / 1e6:.1f}M'
    return f'${value:,.0f}'


def context_summary(context, page=None):
    """A short line naming what the assistant can actually see right now.

    Computed here rather than in the browser so the chips and the answer are
    describing the same snapshot -- a count assembled separately in the
    frontend could disagree with the data the model was given.
    """
    parts = [page] if page else []
    firm = context.get('firm') or {}
    if firm.get('clientCount') is not None:
        count = firm['clientCount']
        parts.append(f"{count} client{'' if count == 1 else 's'}")
    if firm.get('totalAum'):
        parts.append(f"{_money(firm['totalAum'])} AUM")
    if context.get('currentClient'):
        parts.append(context['currentClient']['name'])
    if context.get('currentReport'):
        parts.append(context['currentReport']['title'])
    return ' · '.join(part for part in parts if part)


def ask(message, user, page=None, report_id=None, client_id=None):
    """Returns {'reply', 'configured', 'actions', 'followUps', 'contextSummary'}.

    The first two keys are the original contract and are unchanged; the rest
    are additive and always present (empty when there's nothing to say), so a
    caller never has to branch on their existence.

    Raises AssistantError only for a configured-but-failed call -- an
    unconfigured key is a normal, non-error response so the UI can render it
    inline instead of an error state."""
    if not ANTHROPIC_API_KEY:
        return {
            'reply': (
                "Lumina AI isn't connected yet in this environment -- ask an admin to set "
                "the ANTHROPIC_API_KEY environment variable to turn on the assistant."
            ),
            'configured': False,
            'actions': [],
            'followUps': [],
            'contextSummary': None,
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
    prose, actions, follow_ups = parse_directives(reply_text)
    return {
        'reply': prose or "Lumina AI didn't return a response -- try rephrasing.",
        'configured': True,
        'actions': actions,
        'followUps': follow_ups,
        'contextSummary': context_summary(context, page=page),
    }
