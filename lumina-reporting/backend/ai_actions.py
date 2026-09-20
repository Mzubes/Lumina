"""Validation for the navigation links Lumina AI may put in front of a user.

The assistant is read-only (see ai_assistant.py), and an "action" here is
strictly a deep link to a page the user could have reached from the nav
anyway -- never a form submission, never an endpoint call. That keeps the
V1 spec's D8 ("no LLM writes to the book") true by construction rather than
by convention.

Even so, the link text comes out of a model that is summarising firm data
which people other than the caller wrote. A report title or a client name is
untrusted input, so a prompt-injected or simply hallucinated link must not be
able to put an arbitrary URL in the UI. Everything below is therefore an
allow-list: a path is rendered only if it matches a route this app actually
has. Anything else is dropped silently -- a missing button is a small loss,
a link to somewhere else entirely is not.
"""

import re

# Exactly the routes in frontend/src/App.js that a staff user can open.
# Adding a screen means adding it here; until then the assistant simply
# won't link to it, which is the safe direction to fail in.
_STATIC_PATHS = {
    '/', '/start', '/reports', '/queue', '/templates', '/data-hub', '/data-sources',
    '/marketing', '/pitch-books', '/clients', '/disclosures', '/audit-trail',
    '/users', '/workflow-groups', '/internal-portal', '/client-portal',
}

_ID_PATTERNS = (
    re.compile(r'^/reports/\d+$'),
    re.compile(r'^/internal-portal/clients/\d+$'),
)

# Query params the app itself understands. A link may carry these and nothing
# else, so a crafted path can't smuggle a redirect target or a token through
# the query string.
_ALLOWED_QUERY_KEYS = {
    '/reports': {'stuck', 'overdue', 'status', 'client_id', 'team', 'report_type', 'asset_class', 'q'},
    '/audit-trail': {'report_id', 'actor', 'action_type', 'since', 'until'},
}

MAX_ACTIONS = 3
MAX_FOLLOW_UPS = 2
MAX_LABEL_LENGTH = 60


def is_allowed_path(to):
    """True only for an in-app path this application actually routes.

    Rejects anything with a scheme or authority (so `https://evil.example`,
    `//evil.example` and `javascript:` all fail), anything with a fragment
    (the app is hash-routed; a second `#` would rewrite the whole route),
    and any query key the target page doesn't use.
    """
    if not isinstance(to, str) or not to.startswith('/') or to.startswith('//'):
        return False
    if '#' in to or '\\' in to or ':' in to:
        return False

    path, _, query = to.partition('?')
    if path not in _STATIC_PATHS and not any(pattern.match(path) for pattern in _ID_PATTERNS):
        return False
    if not query:
        return True

    allowed_keys = _ALLOWED_QUERY_KEYS.get(path)
    if not allowed_keys:
        return False
    for pair in query.split('&'):
        key = pair.partition('=')[0]
        if key not in allowed_keys:
            return False
    return True


def sanitize_actions(candidates):
    """Keep the allow-listed links, drop everything else, cap the count."""
    kept = []
    for candidate in candidates or []:
        label = (candidate.get('label') or '').strip()
        to = (candidate.get('to') or '').strip()
        if not label or not is_allowed_path(to):
            continue
        kept.append({'label': label[:MAX_LABEL_LENGTH], 'to': to})
        if len(kept) == MAX_ACTIONS:
            break
    return kept


def sanitize_follow_ups(candidates):
    return [
        question.strip()[:120]
        for question in (candidates or [])
        if isinstance(question, str) and question.strip()
    ][:MAX_FOLLOW_UPS]
