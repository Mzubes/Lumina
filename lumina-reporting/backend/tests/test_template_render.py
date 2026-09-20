"""Rendering a v2 DocumentTemplate: bindings, fixed bands, repeats.

The legacy path is proven unchanged in test_layout_tree.py. This is the
other model actually drawing a document.
"""

import io

import pytest
from pypdf import PdfReader

from renderers.bindings import MissingBinding, resolve_tree
from renderers.html_pdf_renderer import (TemplateLayoutError, render_template_html,
                                         render_template_pdf)
from renderers.layout import pin_repeating_bands
from tests.print_testing import content_to_images, ink_ratio, pdf_to_images

THEME = {'primary_color': '#0d6b5f', 'accent_color': '#c9bd9a'}


def rendered_body(document_html):
    """The markup with the stylesheet stripped, so an assertion about what
    was drawn cannot be satisfied by a class name in a CSS rule."""
    return document_html[document_html.index('</style>'):]


def el(element_type, **overrides):
    element = {'element_type': element_type, 'binding_kind': 'none',
               'x_mm': 0, 'y_mm': 0, 'w_mm': 60, 'h_mm': 8, 'z_index': 0,
               'style_token': None, 'static_text': None, 'content': None,
               'options': None, 'dataset_field_id': None,
               'display_spec_id': None, 'binding_key': None}
    element.update(overrides)
    return element


def band(ordinal, mode='flow', height=None, repeat='none', elements=()):
    return {'ordinal': ordinal, 'name': None, 'layout_mode': mode,
            'height_mm': height, 'repeat_mode': repeat, 'break_before': 'auto',
            'break_after': 'auto', 'elements': list(elements)}


def holdings(count=40):
    return {
        'rows': [{'name': f'Holding {index:02d}',
                  'sector': ['Financials', 'Energy', 'Industrials'][index % 3],
                  'weight': round(6 - index * 0.12, 2)} for index in range(1, count + 1)],
        'columns': ['name', 'sector', 'weight'],
        'fields': [{'field': 'weight', 'default_aggregation': 'sum'}],
        # Grouped and subtotalled, so the document genuinely spans pages --
        # the repeat tests below need more than one page to mean anything.
        'spec': {'sort_by': [{'field': 'weight', 'direction': 'desc'}],
                 'group_by': [{'field': 'sector', 'sort': 'size', 'show_subtotal': True}],
                 'row_limit': 26, 'remainder_label': 'Other ({count} holdings)',
                 'totals': {'grand_total': True, 'label': 'Total'}},
    }


def masthead():
    return band(0, 'fixed', 24, 'every_page', [
        el('field', binding_kind='system', binding_key='client_name',
           x_mm=0, y_mm=2, w_mm=100, h_mm=7, z_index=1),
        el('page_number', binding_kind='system', binding_key='page_number',
           x_mm=150, y_mm=2, w_mm=28, h_mm=6, z_index=1),
        el('box', x_mm=0, y_mm=20, w_mm=178, h_mm=1.2, z_index=0),
    ])


def document():
    tree = [masthead(),
            band(1, elements=[el('table', binding_kind='display_spec',
                                 display_spec_id=7, w_mm=178, h_mm=200)])]
    return resolve_tree(tree, {'system': {'client_name': 'Meridian Pension Partners'},
                               'datasets': {7: holdings()}})


# ---------------------------------------------------------------------------
# It draws
# ---------------------------------------------------------------------------

def test_a_designed_template_renders_a_pdf():
    assert render_template_pdf(document(), theme_config=THEME).startswith(b'%PDF')


def test_a_fixed_band_anchors_its_elements():
    body = rendered_body(render_template_html(document(), theme_config=THEME))
    assert 'band-fixed' in body
    # The brand rule sits 20mm down and spans the content width.
    assert 'top: 20mm' in body and 'width: 178mm' in body


def test_a_designed_template_does_not_get_the_legacy_masthead():
    """It draws its own. Forcing the legacy title block on top would give
    the document two titles."""
    html = render_template_html(document(), theme_config=THEME)
    assert 'doc-title' not in rendered_body(html)
    # ...and no legacy running footer either.
    assert 'content: "Page " counter(page)' not in html


def test_the_legacy_furniture_survives_for_the_legacy_path():
    import json
    from pathlib import Path

    from renderers.html_pdf_renderer import render_document_html
    content = json.loads((Path(__file__).parent / 'golden' / 'factsheet.json').read_text())
    html = render_document_html(content)
    assert 'doc-title' in rendered_body(html)
    assert 'content: "Page " counter(page)' in html


# ---------------------------------------------------------------------------
# Repeating bands, and the two things that go wrong with them
# ---------------------------------------------------------------------------

def test_a_repeating_band_appears_on_every_page():
    images = pdf_to_images(render_template_pdf(document(), theme_config=THEME))
    assert len(images) > 1
    for index, image in enumerate(images, start=1):
        strip = image.crop((0, 0, image.size[0], int(image.size[1] * 0.16)))
        assert ink_ratio(strip) > 0.005, f'masthead missing from page {index}'


def test_the_page_counter_is_lifted_out_of_a_repeating_band():
    """A repeating band is drawn once and replicated, so a counter inside
    one FREEZES -- measured: every page of a seven-page document read
    "p 1 of 7". The element is moved to the @page margin box nearest where
    it was authored, which is the only place the counter resolves."""
    tree, boxes, _ = pin_repeating_bands(document())
    assert boxes == {'@top-right': {'style_token': None}}
    assert all(element['element_type'] != 'page_number'
               for element in tree[0]['elements'])


def test_the_lifted_counter_actually_counts():
    pdf = render_template_pdf(document(), theme_config=THEME)
    pages = PdfReader(io.BytesIO(pdf)).pages
    seen = [page.extract_text() for page in pages]
    assert f'1 of {len(pages)}' in seen[0].replace('\n', ' ')
    assert f'2 of {len(pages)}' in seen[1].replace('\n', ' ')


def test_a_pinned_band_reserves_its_space_on_every_page():
    """Body padding reserved it on page one only, so from page two the
    masthead landed on top of the table. The reservation belongs in the
    page margin."""
    _, _, reserved = pin_repeating_bands(document())
    assert reserved == {'top': 24.0, 'bottom': 0.0}
    html = render_template_html(document(), theme_config=THEME)
    assert 'margin: 50.0mm 16mm' in html      # 26 base + 24 reserved


# ---------------------------------------------------------------------------
# Refusing to draw the wrong thing
# ---------------------------------------------------------------------------

def test_a_structurally_wrong_tree_is_refused_before_anything_is_drawn():
    """A wrong template that renders anyway produces a document someone has
    to notice is wrong."""
    tree = [band(0, 'fixed', None)]       # fixed, but no height
    with pytest.raises(TemplateLayoutError):
        render_template_html(tree, theme_config=THEME)


def test_a_repeating_band_in_the_middle_is_refused():
    tree = [band(0, 'fixed', 10), band(1, 'fixed', 10, 'every_page'), band(2, 'fixed', 10)]
    with pytest.raises(TemplateLayoutError, match='page header'):
        render_template_html(tree, theme_config=THEME)


def test_a_binding_the_context_cannot_satisfy_raises():
    """A factsheet with a silently empty "as at" date is worse than one
    that fails to build."""
    tree = [band(0, elements=[el('field', binding_kind='system',
                                 binding_key='as_of_date')])]
    with pytest.raises(MissingBinding):
        resolve_tree(tree, {'system': {}})


# ---------------------------------------------------------------------------
# Iteration
# ---------------------------------------------------------------------------

def test_a_band_bound_to_a_spec_is_drawn_once_per_row():
    """What makes "one card per holding" expressible without the template
    needing a loop construct."""
    source = holdings(5)
    source['spec'] = {}
    tree = [{**band(0, elements=[el('field', binding_kind='dataset_field',
                                    dataset_field_id='name')]),
             'iterate_display_spec_id': 9}]
    resolved = resolve_tree(tree, {'datasets': {9: source}})
    assert len(resolved) == 5
    assert [section['elements'][0]['content']['value'] for section in resolved] == \
        [row['name'] for row in source['rows']]
