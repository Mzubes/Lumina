"""The print chart palette, and the maths behind it.

The colour checks are computable, so they are computed rather than argued
about. These tests do two jobs: pin the Python port to the reference
implementation it was ported from, and pin the product decisions that fell
out of running it.
"""

import pytest

from renderers import chart_palette
from renderers.chart_palette import (ALL_PAIRS_MAX_SERIES, DEFAULT_SERIES, MAX_SERIES,
                                     OTHER_LABEL, PRINT_SURFACE, failures, fold_to_other,
                                     series_colors, validate)
from renderers.color_science import InvalidColor, contrast, delta_e, normalise, oklch

# The app's on-screen categorical order (styles.css --cat-1..6). Here only as
# the thing print deliberately does NOT inherit.
SCREEN_SERIES = ('#2a78d6', '#eb6834', '#1baf7a', '#4a3aa7', '#e87ba4', '#e34948')

# Numbers printed by the dataviz skill's validate_palette.js, the reference
# implementation color_science.py was ported from. Re-derive with:
#   node scripts/validate_palette.js "<palette>" --mode light --surface "#ffffff"
REFERENCE_NUMBERS = [
    # (first, second, cvd kind or None, expected delta-E)
    ('#1baf7a', '#eb6834', 'deutan', 9.2),
    ('#eda100', '#1baf7a', 'protan', 9.1),
    ('#eda100', '#e87ba4', None, 19.6),
    ('#e34948', '#e87ba4', None, 13.2),
    ('#1baf7a', '#2a78d6', None, 24.0),
    ('#eda100', '#eb6834', None, 13.7),
]
REFERENCE_CONTRAST = [('#1baf7a', 2.82), ('#eda100', 2.17), ('#e87ba4', 2.69)]


# ---------------------------------------------------------------------------
# The port agrees with the implementation it was ported from
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('first,second,kind,expected', REFERENCE_NUMBERS)
def test_delta_e_matches_the_reference_validator(first, second, kind, expected):
    """A drifting port would silently change what counts as accessible."""
    assert delta_e(first, second, kind) == pytest.approx(expected, abs=0.05)


@pytest.mark.parametrize('color,expected', REFERENCE_CONTRAST)
def test_contrast_matches_the_reference_validator(color, expected):
    assert contrast(color, PRINT_SURFACE) == pytest.approx(expected, abs=0.005)


def test_an_invalid_colour_is_refused_not_coerced():
    """The reference implementation is explicit that an unguarded parse lets
    NaN through every check, so the run fails OPEN -- an unreadable palette
    scoring as accessible. Refusing at the boundary is the point."""
    for junk in ('', 'teal', '#12345', '#gggggg', None, 0x2a78d6):
        with pytest.raises(InvalidColor):
            normalise(junk)


def test_whitespace_padded_hex_survives():
    # Hex lists get pasted out of rendered pages and arrive with NBSPs in.
    assert normalise(' #2A78D6 ') == '#2a78d6'


# ---------------------------------------------------------------------------
# What the numbers decided
# ---------------------------------------------------------------------------

def test_the_print_palette_passes_every_hard_check_on_paper():
    assert failures(DEFAULT_SERIES) == []


def test_the_print_palette_is_short_on_contrast_and_that_is_known():
    """Three hues sit below 3:1 against paper. That is a warn, not a fail --
    but only because printed charts carry visible labels and a legend, having
    no hover layer to fall back on. If the renderer ever drops those, this
    warn becomes a real accessibility hole."""
    report = dict((name, state) for name, state, _ in validate(DEFAULT_SERIES))
    assert report['Contrast vs surface'] == 'warn'
    faint = [color for color in DEFAULT_SERIES
             if contrast(color, PRINT_SURFACE) < chart_palette.CONTRAST_MIN]
    assert faint == ['#1baf7a', '#eda100', '#e87ba4']


def test_print_does_not_inherit_the_screen_palette():
    """Pinned so nobody 'simplifies' print by reusing --cat-1..6.

    The screen order fails the normal-vision floor on paper: magenta and red
    are adjacent at delta-E 13.2, under the floor of 15. All 120 re-orderings
    of those six hues were enumerated against the reference validator and
    none clears every gate -- the subset is short the two hues (yellow,
    green) that make the full reference set work, so this is not fixable by
    re-ordering.
    """
    broken = failures(SCREEN_SERIES)
    assert [name for name, _ in broken] == ['Normal-vision floor']
    assert set(SCREEN_SERIES) < set(DEFAULT_SERIES)


def test_every_slot_is_inside_the_lightness_band():
    low, high = chart_palette.LIGHTNESS_BAND
    assert all(low <= oklch(color)[0] <= high for color in DEFAULT_SERIES)


def test_the_first_three_slots_survive_all_pairs():
    """Scatter and bubble charts have no 'adjacent' -- every mark neighbours
    every other. Only the opening three clear that, which is why
    ALL_PAIRS_MAX_SERIES exists."""
    assert failures(DEFAULT_SERIES[:ALL_PAIRS_MAX_SERIES], pairs='all') == []
    assert failures(DEFAULT_SERIES[:ALL_PAIRS_MAX_SERIES + 1], pairs='all')


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------

def test_colours_come_back_in_fixed_slot_order():
    assert series_colors(3) == list(DEFAULT_SERIES[:3])
    # Slot 1 is slot 1 whether there are two series or eight. A filter that
    # drops a series must not repaint the survivors.
    assert series_colors(8)[0] == series_colors(2)[0]


def test_asking_for_a_ninth_series_raises_rather_than_cycling():
    """A cycled hue makes two different entities the same colour, which is a
    wrong chart, not a degraded one."""
    with pytest.raises(ValueError, match='Other'):
        series_colors(MAX_SERIES + 1)


def test_all_pairs_charts_are_capped_lower():
    assert series_colors(ALL_PAIRS_MAX_SERIES, pairs='all')
    with pytest.raises(ValueError):
        series_colors(ALL_PAIRS_MAX_SERIES + 1, pairs='all')


def test_folding_keeps_the_total_and_marks_the_remainder():
    rows = [(f'Sector {index}', index) for index in range(1, 12)]
    folded, did_fold = fold_to_other(rows)
    assert did_fold
    assert len(folded) == MAX_SERIES
    assert folded[-1][0] == OTHER_LABEL
    # The point of folding rather than truncating: the whole is still whole.
    assert sum(value for _, value in folded) == sum(value for _, value in rows)


def test_a_short_series_list_is_left_alone():
    rows = [('A', 1), ('B', 2)]
    assert fold_to_other(rows) == (rows, False)


# ---------------------------------------------------------------------------
# Brand kits
# ---------------------------------------------------------------------------

def test_a_valid_brand_palette_wins():
    brand = {'chart_series': ['#1d6fd0', '#d4562a', '#0f9e6e']}
    assert failures(brand['chart_series']) == []
    assert series_colors(3, brand) == brand['chart_series']


def test_a_house_style_brand_palette_can_still_be_rejected():
    """The Office-default blues and reds a firm is most likely to hand over
    do NOT pass: #1f4e79 is both outside the lightness band (L 0.414) and
    below the chroma floor (0.088), so it reads as near-grey on paper. Worth
    pinning, because it is the realistic case -- not a synthetic one."""
    office = ['#1f4e79', '#c0504d', '#4f81bd']
    assert [name for name, _ in failures(office)] == ['Lightness band', 'Chroma floor']
    assert series_colors(3, {'chart_series': office}) == list(DEFAULT_SERIES[:3])


def test_a_brand_palette_that_fails_the_checks_falls_back():
    """A brand kit is data a person typed. Rendering a client document whose
    series are indistinguishable is worse than rendering it off-brand."""
    indistinguishable = {'chart_series': ['#2a78d6', '#2b79d7', '#2c7ad8']}
    assert series_colors(3, indistinguishable) == list(DEFAULT_SERIES[:3])


@pytest.mark.parametrize('junk', [
    None, {}, {'chart_series': []}, {'chart_series': 'blue'},
    {'chart_series': ['#2a78d6', 'not-a-colour']}, 'not a dict',
])
def test_a_malformed_brand_palette_falls_back_without_raising(junk):
    # Never raise into the middle of a render.
    assert series_colors(2, junk) == list(DEFAULT_SERIES[:2])
