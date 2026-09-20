"""Golden renders: the only test that would catch a CSS regression before a
client opens the PDF.

Every other print test asserts something specific -- a colour, a counter, a
class. This one asserts that the whole page still *looks* the way it did,
which is the only assertion that covers the failure nobody thought to write
a test for.

Comparison happens on a downsampled fingerprint rather than raw pixels. A
full-resolution diff of the same document rendered on two machines is
dominated by glyph-edge antialiasing, so an exact-match test would either be
permanently red or carry a tolerance so wide it caught nothing. The
fingerprint throws that noise away and keeps the structure: block positions,
heights, fills, page count.

Regenerating, after a deliberate design change:

    REGENERATE_GOLDEN=1 pytest tests/test_golden_documents.py

then look at the resulting PNGs in the diff before committing them. A
regenerated reference that nobody looked at is worse than no reference.
"""

import json
import os
import shutil
from pathlib import Path

import pytest
from PIL import Image

from tests.print_testing import (ENVIRONMENT_REFERENCE, GOLDEN_DIR, content_to_images,
                                 environment_fingerprint, environment_matches_references,
                                 fingerprint, fingerprint_difference)

FIXTURES = sorted(GOLDEN_DIR.glob('*.json'))
REGENERATE = os.environ.get('REGENERATE_GOLDEN') == '1'

# A page is 120x170 fingerprint cells. 1% is ~200 cells -- far more than
# rasteriser rounding moves, far less than any visible change. Measured
# against real perturbations in test_the_tolerance_is_tight_enough below.
TOLERANCE = 0.01


def _reference_path(name, page):
    return GOLDEN_DIR / f'{name}.page-{page}.png'


def _load(path):
    return json.loads(path.read_text())


def _document_difference(name, content):
    """The worst per-page difference between a render and its references.

    A changed page count scores 1.0 -- pages that no longer exist cannot be
    compared, and the count changing is itself the regression.
    """
    pages = [fingerprint(image) for image in content_to_images(content)]
    references = sorted(GOLDEN_DIR.glob(f'{name}.page-*.png'))
    if len(pages) != len(references):
        return 1.0
    return max(
        fingerprint_difference(page, Image.open(reference).convert('RGB'))
        for page, reference in zip(pages, references)
    )


if REGENERATE:
    # Written at import, before any test runs, so the canary is on disk by
    # the time the checks below look for it.
    environment_fingerprint().save(ENVIRONMENT_REFERENCE)


def _why_skip():
    if shutil.which('pdftoppm') is None:
        return 'pdftoppm (poppler-utils) is required to rasterise golden renders'
    if not REGENERATE and not environment_matches_references():
        # Deliberately a skip, not a failure. A machine with a different
        # Pango or font set lays out text differently, so every reference
        # would mismatch for a reason that has nothing to do with the
        # change under test -- a red build nobody can act on. The skip
        # reason says so out loud rather than leaving a silent gap.
        return ('this machine does not render text the way the golden '
                'references were made (different WeasyPrint, Pango or fonts)')
    return None


pytestmark = pytest.mark.skipif(_why_skip() is not None, reason=_why_skip() or '')


def test_the_environment_canary_is_committed():
    """The canary is what lets the tests above skip honestly instead of
    failing for the wrong reason. Without it committed, they skip
    everywhere and the whole suite is decoration."""
    assert ENVIRONMENT_REFERENCE.exists(), (
        'missing golden/_environment.png -- regenerate with REGENERATE_GOLDEN=1')


def test_fixtures_exist():
    """Guards against the glob quietly matching nothing, which would make
    the parametrised test below collect zero cases and pass."""
    assert [path.stem for path in FIXTURES] == ['edge_cases', 'factsheet', 'long_table']


@pytest.mark.parametrize('path', FIXTURES, ids=lambda path: path.stem)
def test_document_matches_its_golden_render(path):
    pages = [fingerprint(image) for image in content_to_images(_load(path))]
    assert pages, f'{path.stem} rendered no pages at all'

    if REGENERATE:
        for stale in GOLDEN_DIR.glob(f'{path.stem}.page-*.png'):
            stale.unlink()
        for number, page in enumerate(pages, start=1):
            page.save(_reference_path(path.stem, number))
        pytest.skip(f'regenerated {len(pages)} reference page(s) for {path.stem}')

    references = sorted(GOLDEN_DIR.glob(f'{path.stem}.page-*.png'))
    assert references, (
        f'no reference images for {path.stem}. Run with REGENERATE_GOLDEN=1 '
        'and review the generated PNGs before committing them.'
    )
    assert len(pages) == len(references), (
        f'{path.stem} now renders {len(pages)} page(s), was {len(references)}. '
        'A changed page count is a layout regression unless it was intended.'
    )

    for number, page in enumerate(pages, start=1):
        expected = Image.open(_reference_path(path.stem, number)).convert('RGB')
        difference = fingerprint_difference(page, expected)
        assert difference <= TOLERANCE, (
            f'{path.stem} page {number} differs from its golden render by '
            f'{difference:.1%} of the page (tolerance {TOLERANCE:.0%}).'
        )


def test_the_long_table_still_spans_pages():
    """The multi-page fixture only earns its place while it is multi-page --
    if a spacing change shrank it to one page, the repeating-header and
    page-counter guarantees would stop being exercised and nothing else
    would notice."""
    assert len(sorted(GOLDEN_DIR.glob('long_table.page-*.png'))) >= 2


@pytest.mark.skipif(REGENERATE, reason='no references to compare against mid-regeneration')
def test_the_tolerance_is_tight_enough_to_catch_a_real_change():
    """Without this, TOLERANCE is a guess. A single dropped table row is
    about the smallest change worth failing on; it must land well clear of
    the threshold, and an unchanged render well under it.

    Measured across the whole document rather than one page: the holdings
    table sits on page 2, so a page-1-only comparison would score a dropped
    row at exactly zero and prove nothing.
    """
    content = _load(GOLDEN_DIR / 'factsheet.json')
    unchanged = _document_difference('factsheet', content)

    perturbed = json.loads(json.dumps(content))
    holdings = next(component for component in perturbed['components']
                    if component.get('title') == 'Top Ten Holdings')
    holdings['rows'] = holdings['rows'][:-1]
    changed = _document_difference('factsheet', perturbed)

    assert unchanged < TOLERANCE / 2, f'an unchanged render already differs by {unchanged:.1%}'
    assert changed > TOLERANCE * 2, f'dropping a table row moved only {changed:.1%}'
