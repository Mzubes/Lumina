"""The lint rule: nothing on the print path may use a CSS feature the
engine silently drops.

`test_print_css_support` proves *which* features those are by rendering
them. This file enforces the finding at the source level, so an author who
reaches for `color-mix()` in a print template gets a named failure with a
file and a line, rather than an invisible element in a client's PDF.

The banned list is derived from the support matrix rather than restated, so
a WeasyPrint upgrade that starts supporting a feature relaxes the lint in
the same commit that widens the matrix -- there is no second list to forget.
"""

import re
from pathlib import Path

import pytest

from tests.test_print_css_support import UNSUPPORTED

RENDERERS_DIR = Path(__file__).resolve().parent.parent / 'renderers'

# Everything whose text can end up inside the <style> block of a PDF.
PRINT_SOURCES = sorted(RENDERERS_DIR.glob('templates/*.html')) + [
    RENDERERS_DIR / 'html_pdf_renderer.py',
]

# 'color-mix()' -> 'color-mix'. The matrix names features the way CSS specs
# do; the lint needs the bare token that appears in source.
BANNED = sorted(feature.replace('()', '') for feature in UNSUPPORTED)

_JINJA_COMMENT = re.compile(r'\{#.*?#\}', re.DOTALL)
_BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)
_DOCSTRING = re.compile(r'("""|\'\'\').*?\1', re.DOTALL)
_LINE_COMMENT = re.compile(r'(?m)^\s*#.*$')


def _strip_commentary(text, suffix):
    """Comments may name a banned feature -- the print template's own header
    warns about `color-mix()`. Linting the commentary would make the warning
    unwritable, so it is removed before the scan.

    Blanked spans keep their newlines so reported line numbers stay true.
    """
    def blank(match):
        return re.sub(r'[^\n]', ' ', match.group(0))

    if suffix == '.html':
        text = _JINJA_COMMENT.sub(blank, text)
        return _BLOCK_COMMENT.sub(blank, text)
    text = _DOCSTRING.sub(blank, text)
    return _LINE_COMMENT.sub(blank, text)


def _offences(path):
    stripped = _strip_commentary(path.read_text(), path.suffix)
    found = []
    for number, line in enumerate(stripped.splitlines(), start=1):
        for feature in BANNED:
            if feature in line:
                found.append(f'{path.name}:{number}: {feature}')
    return found


def test_the_lint_covers_the_real_print_path():
    """A glob that silently matches nothing would make every assertion below
    vacuously true."""
    assert PRINT_SOURCES, 'no print sources found to lint'
    assert all(path.exists() for path in PRINT_SOURCES)
    assert BANNED == ['aspect-ratio', 'color-mix']


@pytest.mark.parametrize('path', PRINT_SOURCES, ids=lambda path: path.name)
def test_print_source_avoids_silently_dropped_css(path):
    offences = _offences(path)
    assert not offences, (
        'These render as nothing at all in WeasyPrint -- no error, no '
        'fallback. Precompute the value in Python instead:\n  '
        + '\n  '.join(offences)
    )


def test_the_lint_would_actually_catch_an_offence(tmp_path):
    """Without this, a bug in the comment-stripping that blanked whole files
    would leave every test above passing on empty input."""
    offender = tmp_path / 'bad.html'
    offender.write_text('<style>.x { background: color-mix(in srgb, red, white); }</style>')
    assert _offences(offender) == ['bad.html:1: color-mix']


def test_the_lint_does_not_fire_on_commentary(tmp_path):
    for name, body in (
        ('note.html', '{# never use color-mix() here #}\n<style>.x{color:red}</style>'),
        ('note.py', '"""Avoid aspect-ratio."""\n# and color-mix too\nX = 1\n'),
    ):
        path = tmp_path / name
        path.write_text(body)
        assert _offences(path) == []
