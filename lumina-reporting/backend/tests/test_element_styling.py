"""The style vocabulary, from the model to the ink.

`style_token` was stored, validated, carried through the layout tree --
and then silently ignored by the renderer, so a template could say
`heading-1` and the PDF would draw body text. These tests exist because
that failure was invisible: nothing raised, nothing looked wrong in the
markup, and only a rendered page showed it.

So the assertions here are about what the ENGINE drew, not about what the
template emitted. A class name in the HTML proves the Jinja ran; a taller
glyph in the raster proves the stylesheet did.
"""

import shutil

import pytest

from renderers.html_pdf_renderer import (TemplateLayoutError, render_template_html,
                                         render_template_pdf)
from schema_v2.styling import (CHART_KINDS, STYLE_TOKEN_NAMES, element_classes,
                               option_problems, style_problems)
from tests.print_testing import ink_ratio, pdf_to_images
from tests.test_template_render import band, el, rendered_body

THEME = {'primary_color': '#0d6b5f', 'accent_color': '#c9bd9a'}


# These two compare ink between two renders on the SAME machine, so
# unlike the golden tests they need no environment canary -- only a
# rasteriser.
NO_RASTERISER = shutil.which('pdftoppm') is None


def _document(token=None, options=None):
    return [band(0, 'fixed', height=40, elements=[
        el('text', static_text='Total net assets', x_mm=0, y_mm=0, w_mm=80, h_mm=14,
           style_token=token, options=options),
    ])]


# --- the vocabulary itself --------------------------------------------

def test_a_token_resolves_to_a_class():
    assert element_classes({'style_token': 'heading-1'}) == ['st-heading-1']


def test_an_unknown_name_resolves_to_nothing():
    """Not to `st-heading-9`. A class the stylesheet has never heard of is
    an unstyled element that looks styled in the markup."""
    assert element_classes({'style_token': 'heading-9'}) == []
    assert element_classes({'options': {'align': 'sideways'}}) == []


def test_options_are_names_never_literals():
    assert option_problems({'color': 'accent'}) == []
    # The whole reason the vocabulary is closed: an element carrying a hex
    # keeps drawing the old brand after a rebrand, and hands the PPTX
    # renderer CSS to interpret.
    assert option_problems({'color': '#eb6834'})


def test_an_unknown_option_key_is_reported():
    problems = option_problems({'alignment': 'center'}, 'section 0')
    assert problems == ["section 0: unknown option 'alignment'"]


def test_options_must_be_an_object():
    assert option_problems(['align']) == ['options must be an object']


def test_a_null_option_is_not_a_problem():
    """The canvas clears an option by removing it, but an older payload may
    carry an explicit null; that means "unset", not "invalid"."""
    assert option_problems({'align': None, 'color': None}) == []


def test_style_problems_names_the_alternatives():
    message = style_problems('heading-9', 'section 0')[0]
    assert 'heading-9' in message and 'heading-1' in message


def test_chart_kinds_are_exactly_what_the_renderer_can_draw():
    from renderers.charts import KINDS
    # Equality, not a subset. A kind the inspector offers and the chart
    # builder cannot draw is a dropdown entry that produces a blank box;
    # one the builder has and the inspector hides is a capability nobody
    # can reach. The first version of this list had both faults.
    assert sorted(CHART_KINDS) == sorted(KINDS)


# --- the renderer honouring it ----------------------------------------

def test_every_token_has_a_rule_in_the_stylesheet():
    """The check that would have caught the original bug: a token in the
    vocabulary with no rule draws as body text while the canvas shows a
    heading."""
    css = render_template_html(_document(), theme_config=THEME)
    for token in STYLE_TOKEN_NAMES:
        assert f'.st-{token} {{' in css, f'{token} has no rule'


def test_the_token_reaches_the_element_not_just_the_stylesheet():
    body = rendered_body(render_template_html(_document('heading-1'), theme_config=THEME))
    assert 'st-heading-1' in body


def test_options_reach_the_element():
    body = rendered_body(render_template_html(
        _document(options={'align': 'right', 'color': 'accent', 'border': 'bottom'}),
        theme_config=THEME))
    assert 'align-right' in body and 'color-accent' in body and 'border-bottom' in body


def test_an_unknown_token_is_refused_before_anything_is_drawn():
    """Stronger than emitting no class: the renderer shares the API's
    vocabulary check, so a tree that would draw the wrong thing never gets
    as far as drawing."""
    with pytest.raises(TemplateLayoutError, match='unknown style token'):
        render_template_html(_document('font-size: 40px'), theme_config=THEME)

    with pytest.raises(TemplateLayoutError, match='unknown option'):
        render_template_html(_document(options={'alignment': 'left'}), theme_config=THEME)


def test_a_colour_role_resolves_to_the_theme_not_a_literal():
    css = render_template_html(_document(), theme_config=THEME)
    # accent comes from theme_config, so a rebrand moves it.
    assert '.color-accent { color: #c9bd9a; }' in css


@pytest.mark.skipif(NO_RASTERISER, reason='pdftoppm (poppler-utils) is not installed')
def test_a_heading_token_puts_more_ink_on_the_page_than_body():
    """The one that proves the stylesheet ran. Same words, same box, same
    engine -- only the token differs, so more ink means larger type was
    actually set.

    Measured over the WHOLE page rather than a crop: PIL pads a crop that
    runs past the image edge with black, and the padding counts as ink --
    which drowned the real signal when this test was first written.
    """
    plain = ink_ratio(pdf_to_images(
        render_template_pdf(_document('body'), theme_config=THEME))[0])
    heading = ink_ratio(pdf_to_images(
        render_template_pdf(_document('figure-large'), theme_config=THEME))[0])
    assert heading > plain * 1.5, f'figure-large {heading:.5f} vs body {plain:.5f}'


@pytest.mark.skipif(NO_RASTERISER, reason='pdftoppm (poppler-utils) is not installed')
def test_a_fill_puts_ink_where_there_was_none():
    bare = ink_ratio(pdf_to_images(
        render_template_pdf(_document('body'), theme_config=THEME))[0])
    filled = ink_ratio(pdf_to_images(render_template_pdf(
        _document('body', {'fill': 'tint'}), theme_config=THEME))[0])
    # An 80x14mm tint is ~4% of an A4 page, so this is not a near thing.
    assert filled > bare * 10, f'fill drew nothing: {filled:.5f} vs {bare:.5f}'
