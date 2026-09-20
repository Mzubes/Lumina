"""Tier 2: the charts that carry a computed axis.

A wrong axis is the most dangerous kind of chart bug, because the result
still looks like a chart. Both defects pinned below shipped a plausible
picture of the wrong thing.
"""

import pytest

from renderers.chart_palette import DEFAULT_SERIES, MAX_SERIES
from renderers.charts import build_chart
from renderers.html_pdf_renderer import _format_cell, to_number
from renderers.vega_charts import build_spec, render_svg

THEME = {'muted': '#6b6b6b', 'rule': '#dcdcdc'}
MONTHS = ['Jun 25', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan 26',
          'Feb', 'Mar', 'Apr', 'May', 'Jun']


def spec(kind='line', series=('Strategy',), rows=None, brand=None):
    rows = rows or [(month, [100.0 + index]) for index, month in enumerate(MONTHS)]
    return build_spec(kind, 'Month', list(series), rows, THEME, brand)


def chart(component_kind, columns, rows):
    return build_chart({'chart_type': component_kind, 'columns': columns, 'rows': rows},
                       to_number, _format_cell, None, THEME)


# ---------------------------------------------------------------------------
# The two that shipped a convincing picture of the wrong thing
# ---------------------------------------------------------------------------

def test_the_x_axis_keeps_the_order_the_data_arrived_in():
    """Vega sorts an ordinal domain by VALUE unless told otherwise, which
    for month labels is alphabetical: Apr, Aug, Dec, Feb, Jan, Jul, Jun...
    A growth chart with its months shuffled reads as a plausible chart of
    nonsense, and nothing but the axis gives it away."""
    assert spec()['encoding']['x']['sort'] is None

    svg = render_svg(spec())
    # The rendered labels, in the order they appear left to right.
    positions = [(svg.index(f'>{month}<'), month) for month in MONTHS]
    assert [month for _, month in sorted(positions)] == MONTHS


def test_an_indexed_series_asked_for_as_an_area_becomes_a_line():
    """An area fill encodes magnitude from the baseline, so its baseline
    must be zero. A series running 100 to 119 then renders as a flat line
    pinned to the top of an empty plot -- all the movement crushed out.
    The fill is not what that chart is about."""
    indexed = spec('area', rows=[('Jan', [100.0]), ('Feb', [110.0]), ('Mar', [119.0])])
    assert [layer['mark']['type'] for layer in indexed['layer']] == ['line']
    assert indexed['encoding']['y']['scale']['zero'] is False


def test_a_series_that_does_reach_zero_keeps_its_fill_and_its_baseline():
    grounded = spec('area', rows=[('Jan', [0.0]), ('Feb', [40.0]), ('Mar', [95.0])])
    assert [layer['mark']['type'] for layer in grounded['layer']] == ['area', 'line']
    assert grounded['encoding']['y']['scale']['zero'] is True


@pytest.mark.parametrize('rows', [
    [('a', [-5.0]), ('b', [10.0])],   # crosses zero
    [('a', [-9.0]), ('b', [-2.0])],   # entirely below it
])
def test_a_series_spanning_zero_keeps_its_fill(rows):
    """The baseline is meaningful when the data crosses it, so the fill is
    meaningful too."""
    assert [layer['mark']['type'] for layer in spec('area', rows=rows)['layer']] \
        == ['area', 'line']


# ---------------------------------------------------------------------------
# Safety: labels arrive from a warehouse, and the SVG is inlined unescaped
# ---------------------------------------------------------------------------

def test_a_label_cannot_break_out_of_the_svg():
    """The template marks this SVG `| safe`, so this is the assertion that
    makes that safe. Report labels come from a data warehouse, not from us."""
    hostile = '</text></svg><script>alert(1)</script>'
    svg = render_svg(spec(rows=[(hostile, [1.0]), ('ok', [2.0])]))
    assert svg.count('<svg') == 1 and svg.count('</svg>') == 1
    assert '<script>' not in svg
    assert '&lt;script&gt;' in svg


# ---------------------------------------------------------------------------
# Theming and palette
# ---------------------------------------------------------------------------

def test_the_chart_wears_the_document_font():
    """Otherwise Vega picks its own sans and the chart reads as something
    pasted in from another program."""
    assert 'DejaVu Sans' in render_svg(spec())


def test_axis_furniture_takes_the_theme_colours():
    config = spec()['config']
    assert config['axis']['labelColor'] == THEME['muted']
    assert config['axis']['gridColor'] == THEME['rule']


def test_series_take_palette_slots():
    two = spec(series=('Strategy', 'Index'),
               rows=[('Jan', [100.0, 100.0]), ('Feb', [104.0, 101.0])])
    assert two['encoding']['color']['scale']['range'] == list(DEFAULT_SERIES[:2])


def test_a_single_series_has_no_legend():
    """The section title names it; a one-entry legend is noise."""
    assert 'color' not in spec()['encoding']
    assert all(layer['mark']['color'] == DEFAULT_SERIES[0] for layer in spec()['layer'])


def test_a_brand_palette_reaches_a_trend_chart_too():
    brand = {'chart_series': ['#1d6fd0', '#d4562a']}
    two = spec(series=('A', 'B'), rows=[('Jan', [1.0, 2.0])], brand=brand)
    assert two['encoding']['color']['scale']['range'] == ['#1d6fd0', '#d4562a']


# ---------------------------------------------------------------------------
# Through the component pipeline
# ---------------------------------------------------------------------------

def test_a_line_component_produces_inline_svg():
    model = chart('line', ['Month', 'Strategy'], [['Jan', 100], ['Feb', 104]])
    assert model['kind'] == 'vega'
    assert model['svg'].lstrip().startswith('<svg')


def test_too_many_series_produces_no_chart_rather_than_a_folded_one():
    """A part-to-whole chart can sum its tail into "Other". A trend chart
    cannot -- adding two price series together means nothing -- so the
    honest outcome is no chart. The table above it still carries every
    number."""
    columns = ['Month'] + [f'Series {index}' for index in range(MAX_SERIES + 1)]
    rows = [['Jan'] + [float(index) for index in range(MAX_SERIES + 1)]]
    assert chart('line', columns, rows) is None


def test_an_unparseable_row_is_dropped_not_charted_as_zero():
    model = chart('line', ['Month', 'Strategy'],
                  [['Jan', 100], ['Feb', 'n/a'], ['Mar', 104]])
    svg = model['svg']
    assert '>Jan<' in svg and '>Mar<' in svg and '>Feb<' not in svg
