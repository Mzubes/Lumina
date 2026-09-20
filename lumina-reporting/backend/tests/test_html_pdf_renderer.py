"""Phase A: the WeasyPrint renderer, and the guards that keep it honest.

The two failure modes this renderer has are both silent, which is why they
get tests rather than trust:

  * `color-mix()` renders NOTHING in WeasyPrint -- no error, no fallback,
    just an invisible box. The app's screen stylesheet uses it 48 times, so
    a copy-paste into a print template is a live risk.
  * A CSS regression in a PDF is invisible until a client opens it. The
    structural assertions below stand in for a full golden-image suite.
"""

import re

import pytest
from pypdf import PdfReader

from renderers import CONTENT_TYPES, RENDERERS
from renderers.html_pdf_renderer import mix, render_document_html, render_html_pdf, to_number


def _content(**overrides):
    payload = {
        'report_title': 'Pzena Global Small Cap — Monthly Factsheet',
        'client_name': 'Meridian Pension Partners',
        'generated_at': '2026-06-30T09:00:00',
        'components': [],
        'header_config': {'title': 'Pzena Global Small Cap — Monthly Factsheet',
                          'subtitle': 'FACTSHEET · as at 30 June 2026'},
        'footer_config': {'text': 'Confidential — for institutional use only'},
        'theme_config': {'primary_color': '#0d6b5f', 'accent_color': '#c9bd9a'},
    }
    payload.update(overrides)
    return payload


def _table(rows, columns=None, **extra):
    component = {'type': 'data_table', 'title': 'Sector Weights',
                 'columns': columns or ['Sector', 'Strategy', 'Index'], 'rows': rows}
    component.update(extra)
    return component


def _text(pdf_bytes, page=0):
    """Text extracted from a rendered page.

    Used ONLY for things that exist after layout -- page counters, running
    headers, page counts, embedded-font coverage. Not for asserting content
    is present: PDF extraction splits kerned pairs, so "Tate" comes back as
    "T ate". Content assertions go against the HTML, which is deterministic.
    """
    return PdfReader(__import__('io').BytesIO(pdf_bytes)).pages[page].extract_text()


def _body(document):
    """The document HTML with the stylesheet stripped, so an assertion about
    rendered markup can't be satisfied by a class name in a CSS rule."""
    return document[document.index('</style>'):]


# ---------------------------------------------------------------------------
# The guard that matters most
# ---------------------------------------------------------------------------

def test_generated_css_never_contains_color_mix():
    """WeasyPrint drops color-mix() silently -- an element styled with it
    renders as nothing at all. Every derived colour must be precomputed."""
    document = render_document_html(_content(components=[_table([['Financials', '12%', '15%']])]))
    assert 'color-mix' not in document


def test_mix_precomputes_a_literal_hex():
    # The replacement for color-mix(). Pure arithmetic, no CSS function.
    assert mix('#000000', '#ffffff', 0.5) == '#808080'
    assert mix('#0d6b5f', '#ffffff', 1.0) == '#0d6b5f'
    assert mix('#0d6b5f', '#ffffff', 0.0) == '#ffffff'


def test_mix_survives_a_malformed_colour():
    # A template with a junk theme colour must still render, not crash.
    assert mix('not-a-colour', '#ffffff', 0.5).startswith('#')


# ---------------------------------------------------------------------------
# What fpdf2 could not do at all
# ---------------------------------------------------------------------------

def test_unicode_survives_instead_of_being_substituted():
    """The old renderer carries a substitution table turning em-dashes into
    hyphens and dropping anything outside latin-1. Real document text --
    a Danish holding, a curly quote -- must arrive intact."""
    component = _table([['Ørsted A/S', '3.1%', '2.8%'], ['Zürich Insurance', '2.4%', '2.0%']])
    text = _text(render_html_pdf(_content(components=[component])))
    assert 'Ørsted' in text
    assert 'Zürich' in text
    assert '—' in text          # the em-dash in the title


def test_every_page_carries_a_page_counter():
    """counter(pages) cannot be produced by an imperative writer: the total
    is unknown until layout finishes."""
    rows = [[f'Holding {index:02d}', f'{index}%', f'{index}%'] for index in range(1, 120)]
    pdf = render_html_pdf(_content(components=[_table(rows)]))
    reader = PdfReader(__import__('io').BytesIO(pdf))
    assert len(reader.pages) > 1
    for index, page in enumerate(reader.pages, start=1):
        assert f'Page {index} of {len(reader.pages)}' in page.extract_text()


def test_a_long_table_repeats_its_header_on_every_page():
    rows = [[f'Holding {index:02d}', f'{index}%', f'{index}%'] for index in range(1, 120)]
    pdf = render_html_pdf(_content(components=[_table(rows)]))
    reader = PdfReader(__import__('io').BytesIO(pdf))
    for page in reader.pages:
        text = page.extract_text()
        if 'Holding' in text:
            assert 'SECTOR' in text.upper()


def test_the_running_header_and_footer_appear_on_every_page():
    rows = [[f'Holding {index:02d}', f'{index}%', f'{index}%'] for index in range(1, 120)]
    pdf = render_html_pdf(_content(components=[_table(rows)]))
    reader = PdfReader(__import__('io').BytesIO(pdf))
    assert len(reader.pages) > 1
    for page in reader.pages:
        assert 'Confidential' in page.extract_text()


# ---------------------------------------------------------------------------
# Number handling -- shared by alignment and charting
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('value,expected', [
    ('22%', 22.0), ('$1,234.50', 1234.5), ('(0.4)', -0.4), ('-3.2', -3.2),
    (7, 7.0), (7.5, 7.5), ('', None), ('n/a', None), (None, None), (True, None),
])
def test_to_number_reads_warehouse_formatted_cells(value, expected):
    """Cells arrive pre-formatted as often as not. Alignment and charting
    both need the number behind the presentation, from one parser."""
    assert to_number(value) == expected


def test_a_percent_column_charts_rather_than_being_silently_skipped():
    """Found in the first real render: '22%' failed float() and the chart
    vanished with no error."""
    component = _table([['Financials', '12%', '15%'], ['Industrials', '29%', '20%']],
                       chart_type='bar_comparison')
    body = _body(render_document_html(_content(components=[component])))
    # Both series drawn, each at a width derived from the parsed number --
    # 29% is the peak, so it is the full-width bar.
    assert body.count('class="chart-bar"') == 4
    assert 'width: 100.0%' in body
    assert 'width: 41.4%' in body  # 12 of 29


def test_a_non_numeric_column_produces_no_chart():
    component = _table([['Financials', 'n/a', 'n/a']], chart_type='bar_comparison')
    assert 'class="chart-bar"' not in _body(render_document_html(_content(components=[component])))


def test_numeric_columns_right_align_and_text_columns_do_not():
    document = render_document_html(_content(components=[
        _table([['Financials', '12%', '15%']])]))
    header_row = re.search(r'<thead>.*?</thead>', document, re.S).group(0)
    cells = re.findall(r'<th class="([^"]*)"', header_row)
    assert cells == ['', 'num', 'num']


# ---------------------------------------------------------------------------
# Component coverage and resilience
# ---------------------------------------------------------------------------

def test_every_resolver_output_type_renders():
    """The renderer must cover everything report_content.py can emit --
    a type it silently drops is a missing section nobody notices."""
    components = [
        {'type': 'text_block', 'title': 'About Us', 'text': 'A deep value manager.'},
        {'type': 'people_grid', 'title': 'Portfolio Managers',
         'people': [{'name': 'Evan Fox, CFA', 'title': 'Portfolio Manager', 'detail': 'Since 2007'}]},
        {'type': 'holdings_table', 'title': 'Top 10 Holdings',
         'columns': ['Security', 'Weight %'], 'rows': [['Tate & Lyle PLC', 2.5]]},
        {'type': 'performance_summary', 'title': 'Performance',
         'columns': ['Period', 'Return'], 'rows': [['YTD', 6.9]]},
        _table([['Financials', '12%', '15%']]),
    ]
    body = _body(render_document_html(_content(components=components)))
    for expected in ('About Us', 'Portfolio Managers', 'Evan Fox', 'Top 10 Holdings',
                     'Tate &amp; Lyle', 'Performance', 'Sector Weights'):
        assert expected in body, expected
    # And the whole thing still produces a valid PDF.
    assert render_html_pdf(_content(components=components)).startswith(b'%PDF')


def test_an_empty_table_says_so_rather_than_rendering_a_bare_heading():
    assert 'No data on file' in _body(render_document_html(_content(components=[_table([])])))


def test_a_report_with_no_components_still_renders_a_valid_pdf():
    pdf = render_html_pdf(_content(components=[]))
    assert pdf.startswith(b'%PDF')
    assert 'Pzena' in _text(pdf)


def test_a_template_with_no_theme_falls_back_to_defaults():
    document = render_document_html(_content(theme_config={}))
    assert 'color-mix' not in document
    assert '#10265c' in document      # the default primary


# ---------------------------------------------------------------------------
# Registry wiring
# ---------------------------------------------------------------------------

def test_pdf_is_the_new_renderer_and_the_old_one_is_still_reachable():
    """The old path stays available for one release so the two can be
    compared side by side before it is removed."""
    assert RENDERERS['pdf'] is render_html_pdf
    assert 'pdf_legacy' in RENDERERS
    assert CONTENT_TYPES['pdf_legacy'] == 'application/pdf'


def test_both_renderers_still_accept_the_same_payload():
    content = _content(components=[_table([['Financials', '12%', '15%']])])
    assert RENDERERS['pdf'](content).startswith(b'%PDF')
    assert RENDERERS['pdf_legacy'](content).startswith(b'%PDF')


# ---------------------------------------------------------------------------
# Keep-together, and what it costs
# ---------------------------------------------------------------------------

def test_a_short_section_asks_to_be_kept_on_one_page():
    """Without it, a four-row table's chart strands itself at the top of the
    next page, arriving under the PREVIOUS section's heading -- which is how
    a reader attributes it."""
    component = _table([['Equity', 62], ['Cash', 38]], columns=['Asset', 'Weight'],
                       chart_type='donut', title='Asset Allocation')
    assert 'component-compact' in _body(render_document_html(_content(components=[component])))


def test_a_long_section_does_not():
    """Caught by looking at a render, not by a test: asking the engine to
    keep an over-tall section together costs a whole page. It first tries to
    honour the rule by pushing the section to a fresh page, then gives up
    and breaks it anyway -- leaving the page before it blank.
    """
    component = _table([[f'Holding {index}', index] for index in range(1, 61)],
                       columns=['Security', 'Units'], title='Positions')
    assert 'component-compact' not in _body(render_document_html(_content(components=[component])))


def test_a_long_document_does_not_open_with_a_blank_page():
    """The regression test for that bug, measured where it showed up: the
    first page of the 60-row fixture came back at 1% ink."""
    from tests.print_testing import content_to_images, ink_ratio

    component = _table([[f'Holding {index}', f'{index * 1375:,}'] for index in range(1, 61)],
                       columns=['Security', 'Units'], title='Positions')
    first = content_to_images(_content(components=[component]))[0]
    assert ink_ratio(first) > 0.10, 'the document opens on a near-blank page'


# ---------------------------------------------------------------------------
# Which faces a document may embed
# ---------------------------------------------------------------------------

# Every face here is a real file in fonts-dejavu-core, the package CI and
# the deployment install. Anything else means the engine substituted or
# SYNTHESIZED a face, which makes the document depend on the render host's
# font set -- two machines, two different PDFs from one payload.
ALLOWED_FACES = {'DejaVu-Sans', 'DejaVu-Sans-Bold'}


def _embedded_faces(pdf_bytes):
    import io

    from pypdf import PdfReader
    return {str(font.get_object().get('/BaseFont')).split('+')[-1]
            for page in PdfReader(io.BytesIO(pdf_bytes)).pages
            for font in (page.get('/Resources', {}).get('/Font') or {}).values()}


def test_a_document_embeds_only_faces_that_really_exist():
    """CI found this the expensive way: `.empty` asked for italic, DejaVu
    Sans ships no oblique face, and the engine synthesized one. The single
    fixture using italic then rendered differently on two machines while
    the other three matched -- a red build whose cause was invisible in the
    diff.

    Counting the embedded faces turns that whole class of bug into a
    named failure.
    """
    component = _table([['Financials', '12%', '15%']], chart_type='bar_comparison')
    faces = _embedded_faces(render_html_pdf(_content(components=[component])))
    assert faces <= ALLOWED_FACES, f'unexpected face(s): {sorted(faces - ALLOWED_FACES)}'


def test_an_empty_section_note_is_not_italic():
    """The specific rule behind the allow-list, pinned so it cannot drift
    back: no italic anywhere in the print stylesheet, because the family
    has no italic to give."""
    document = render_document_html(_content(components=[_table([])]))
    assert 'No data on file' in _body(document)
    assert 'font-style: italic' not in document


def test_the_running_header_is_set_in_the_document_face():
    """@page margin boxes do NOT inherit from body -- they take the page
    context's initial family, which is serif. The running header and
    footer were set in DejaVu Serif on every page of every document until
    the face count showed a third font nobody had asked for."""
    document = render_document_html(_content(components=[_table([['A', '1', '2']])]))
    page_block = document[document.index('@page'):document.index('html {')]
    assert 'font-family: "DejaVu Sans"' in page_block
    assert 'DejaVu-Serif' not in _embedded_faces(
        render_html_pdf(_content(components=[_table([['A', '1', '2']])])))
