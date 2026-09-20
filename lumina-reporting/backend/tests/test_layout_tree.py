"""The layout tree, and the proof that introducing it changed nothing.

Phase D puts a section/element tree between the resolver and the renderer.
The whole point of doing that as a separate step is that it can be shown to
be a no-op for existing documents -- so the v2 model can be built on a
foundation known not to have moved anything.
"""

import hashlib
import io
import json
from pathlib import Path

import pytest
from pypdf import PdfReader

from renderers.html_pdf_renderer import render_html_pdf
from renderers.layout import (DEFAULT_CONTENT_WIDTH_MM, layout_from_components,
                              validate)

GOLDEN = Path(__file__).parent / 'golden'
# Captured by running the PRE-Phase-D renderer over the same fixtures. See
# the test below for why this is content streams and not whole-file bytes.
BASELINE = json.loads((GOLDEN / 'content_streams.json').read_text())


def _content_streams(pdf_bytes):
    return [hashlib.sha256(page.get_contents().get_data()).hexdigest()
            for page in PdfReader(io.BytesIO(pdf_bytes)).pages]


# ---------------------------------------------------------------------------
# The verification Phase D is actually for
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('name', sorted(BASELINE))
def test_the_tree_draws_exactly_what_the_flat_list_drew(name):
    """Every page's drawing instructions, unchanged.

    The plan asked for byte-comparable output. Whole-file PDF bytes are the
    wrong instrument: the file is Flate-compressed, so an insignificant
    whitespace difference in the generated HTML -- which reordering a Jinja
    block inevitably causes -- reshuffles most of the file while drawing
    the identical page. The content stream is the drawing itself,
    uncompressed: insensitive to how the file was packed, exactly sensitive
    to what landed where.

    Chasing whole-file equality would have meant contorting the template to
    reproduce the old one's blank lines, permanently, to satisfy a proxy.
    """
    content = json.loads((GOLDEN / f'{name}.json').read_text())
    assert _content_streams(render_html_pdf(content)) == BASELINE[name]


# ---------------------------------------------------------------------------
# What the adapter makes of today's flat list
# ---------------------------------------------------------------------------

def test_each_component_becomes_one_flow_band():
    """That is what the flat list always meant: each component owns a band,
    and the bands stack."""
    tree = layout_from_components([
        {'type': 'text_block', 'title': 'Approach', 'text': 'x'},
        {'type': 'data_table', 'title': 'Holdings', 'columns': ['A'], 'rows': [['1']]},
    ])
    assert [section['ordinal'] for section in tree] == [0, 1]
    assert all(section['layout_mode'] == 'flow' for section in tree)
    assert all(section['height_mm'] is None for section in tree)


def test_a_band_keeps_its_heading():
    """So a heading still belongs to its content rather than floating
    between two sections."""
    tree = layout_from_components([{'type': 'text_block', 'title': 'Approach'}])
    assert tree[0]['name'] == 'Approach'


def test_a_charted_table_is_two_elements_in_one_band():
    """One band, so a page break can never separate a table from the chart
    of its own rows. Two elements, because that is what the page has always
    shown and what the v2 model can finally say."""
    tree = layout_from_components([
        {'type': 'data_table', 'columns': ['A', 'B'], 'rows': [['1', '2']],
         'chart': {'kind': 'bar', 'rows': []}},
    ])
    assert [element['element_type'] for element in tree[0]['elements']] == ['table', 'chart']
    assert len(tree) == 1


def test_a_table_without_a_chart_is_one_element():
    tree = layout_from_components([{'type': 'data_table', 'columns': ['A'], 'rows': [['1']]}])
    assert [element['element_type'] for element in tree[0]['elements']] == ['table']


def test_an_unrecognised_component_yields_an_empty_band():
    """Not a guess. The renderer says "Nothing to display." on the page;
    guessing would put a blank box in a client document instead."""
    tree = layout_from_components([{'type': 'sunburst_widget', 'title': 'Mystery'}])
    assert tree[0]['elements'] == []
    assert tree[0]['name'] == 'Mystery'


def test_legacy_elements_are_full_width_and_anchored_at_the_origin():
    tree = layout_from_components([{'type': 'text_block', 'text': 'x'}])
    element = tree[0]['elements'][0]
    assert (element['x_mm'], element['y_mm']) == (0, 0)
    assert element['w_mm'] == DEFAULT_CONTENT_WIDTH_MM


def test_an_element_carries_its_resolved_content():
    """In v2 the values arrive through a binding; during cutover they
    arrive already resolved, and the renderer cannot tell the difference."""
    component = {'type': 'text_block', 'text': 'Investment approach'}
    element = layout_from_components([component])[0]['elements'][0]
    assert element['content'] is component
    assert element['binding_kind'] == 'none'


def test_no_components_is_no_sections():
    assert layout_from_components([]) == []
    assert layout_from_components(None) == []


# ---------------------------------------------------------------------------
# The structural guard
# ---------------------------------------------------------------------------

def test_a_legacy_tree_is_structurally_sound():
    content = json.loads((GOLDEN / 'factsheet.json').read_text())
    assert validate(layout_from_components(content['components'])) == []


def test_validate_catches_a_mode_and_height_mismatch():
    tree = layout_from_components([{'type': 'text_block'}])
    tree[0]['layout_mode'] = 'fixed'          # fixed, but no height
    assert any('height' in problem for problem in validate(tree))


def test_validate_catches_a_css_declaration_in_a_style_token():
    """The renderer-agnostic rule, checked for trees built in code as well
    as for rows the database already guards."""
    tree = layout_from_components([{'type': 'text_block'}])
    tree[0]['elements'][0]['style_token'] = 'font-size: 12pt'
    assert any('CSS declaration' in problem for problem in validate(tree))


def test_validate_catches_an_unknown_element_type():
    tree = layout_from_components([{'type': 'text_block'}])
    tree[0]['elements'][0]['element_type'] = 'iframe'
    assert any('unknown element type' in problem for problem in validate(tree))


# ---------------------------------------------------------------------------
# The regression guard
# ---------------------------------------------------------------------------

RESOLVER_TYPES = ('holdings_table', 'performance_summary', 'text_block',
                  'data_table', 'people_grid')


@pytest.mark.parametrize('component_type', RESOLVER_TYPES)
def test_every_type_the_resolver_emits_reaches_the_page(component_type):
    """The first cut keyed the mapping on the component type and covered
    three of the five. `holdings_table` and `performance_summary` quietly
    became empty bands -- real content missing from a client document, with
    nothing raising.

    The old template never had that bug: it dispatched on whether the
    component had columns, so a tabular type it had never heard of still
    rendered. Shape, not name.
    """
    component = {'type': component_type, 'title': 'Section',
                 'text': 'words', 'people': [{'name': 'A'}],
                 'columns': ['A', 'B'], 'rows': [['1', '2']]}
    tree = layout_from_components([component])
    assert tree[0]['elements'], f'{component_type} rendered nothing'


def test_a_tabular_type_nobody_has_invented_yet_still_renders():
    """The property that makes the guard above hold in future."""
    tree = layout_from_components([
        {'type': 'attribution_table', 'columns': ['Effect'], 'rows': [['x']]},
    ])
    assert [element['element_type'] for element in tree[0]['elements']] == ['table']


def test_the_resolver_type_list_is_still_accurate():
    """A new resolver type with no mapping is the failure this file exists
    to prevent, so the list it checks against cannot be allowed to rot."""
    import re

    source = (Path(__file__).parent.parent / 'report_content.py').read_text()
    emitted = set(re.findall(r"'type':\s*'(\w+)'", source))
    assert emitted <= set(RESOLVER_TYPES), (
        f'report_content.py emits {emitted - set(RESOLVER_TYPES)}, which this '
        f'file does not cover -- add it to RESOLVER_TYPES and check it maps.')
