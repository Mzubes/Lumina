"""Chart geometry -- the arithmetic behind every printed mark.

These assert the model, not the markup: a wrong number here draws a
convincing chart that says the wrong thing, which is the worst failure mode
this pipeline has.
"""

import pytest

from renderers.chart_palette import DEFAULT_SERIES, MAX_SERIES, OTHER_LABEL
from renderers.charts import build_chart
from renderers.html_pdf_renderer import _format_cell, to_number


def chart(rows, columns=('Sector', 'Strategy', 'Index'), chart_type='bar_comparison', brand=None):
    return build_chart(
        {'chart_type': chart_type, 'columns': list(columns), 'rows': rows},
        to_number, _format_cell, brand,
    )


# ---------------------------------------------------------------------------
# The one that matters most
# ---------------------------------------------------------------------------

def test_a_negative_value_is_drawn_on_the_other_side_of_zero():
    """An attribution of -40bps drawn as a positive-length bar is not a
    rough chart, it is a false one: it would be indistinguishable from
    +40bps and longer than a real +15."""
    model = chart([['Allocation', '(40)', '20'], ['Selection', '180', '(60)']],
                  columns=('Effect', 'Portfolio', 'Benchmark'))
    assert model['signed'] is True
    allocation, selection = model['rows']
    assert allocation['bars'][0]['negative'] is True
    assert allocation['bars'][1]['negative'] is False
    assert selection['bars'][1]['negative'] is True
    # Magnitudes still scale against the same peak, 180.
    assert allocation['bars'][0]['pct'] == pytest.approx(40 / 180 * 100, abs=0.1)


def test_an_all_positive_chart_does_not_pretend_to_have_a_zero_line():
    assert chart([['Financials', '22%', '18%']])['signed'] is False


def test_every_series_shares_one_scale():
    """Two y-scales in one chart is the single worst thing a chart can do,
    and grouped bars are where the temptation shows up."""
    model = chart([['A', 10, 1000], ['B', 5, 500]])
    widths = [bar['pct'] for row in model['rows'] for bar in row['bars']]
    # 1000 is the peak; 10 is 1% of it, not 100% of its own series.
    assert max(widths) == 100
    assert min(widths) == pytest.approx(0.5, abs=0.01) or min(widths) < 2


# ---------------------------------------------------------------------------
# Labels stay attached to the values they annotate
# ---------------------------------------------------------------------------

def test_labels_survive_a_dropped_row():
    """The first cut paired labels to bars by matching on the row label,
    which silently mis-annotated every bar after an unparseable row."""
    model = chart([['Financials', '22%', '18%'],
                   ['Unavailable', 'n/a', 'n/a'],
                   ['Energy', '7%', '5%']])
    assert [row['label'] for row in model['rows']] == ['Financials', 'Energy']
    assert [bar['value_label'] for bar in model['rows'][1]['bars']] == ['7%', '5%']


def test_duplicate_row_labels_keep_their_own_values():
    model = chart([['Financials', '22%', '18%'], ['Financials', '7%', '5%']])
    assert [bar['value_label'] for bar in model['rows'][0]['bars']] == ['22%', '18%']
    assert [bar['value_label'] for bar in model['rows'][1]['bars']] == ['7%', '5%']


# ---------------------------------------------------------------------------
# Colour
# ---------------------------------------------------------------------------

def test_series_take_palette_slots_in_order():
    model = chart([['A', 1, 2]])
    assert [entry['color'] for entry in model['legend']] == list(DEFAULT_SERIES[:2])


def test_a_single_series_gets_no_legend_box():
    """The section title already names it; a one-row legend is noise."""
    assert chart([['A', 1]], columns=('Sector', 'Weight'))['legend'] == []


def test_two_series_always_get_a_legend():
    """Identity is never colour alone -- and on paper there is no hover to
    fall back on."""
    assert len(chart([['A', 1, 2]])['legend']) == 2


def test_a_brand_palette_reaches_the_marks():
    brand = {'chart_series': ['#1d6fd0', '#d4562a', '#0f9e6e']}
    model = chart([['A', 1, 2]], brand=brand)
    assert [entry['color'] for entry in model['legend']] == ['#1d6fd0', '#d4562a']


# ---------------------------------------------------------------------------
# Part-to-whole
# ---------------------------------------------------------------------------

def test_shares_are_percentages_of_the_total_present():
    model = chart([['Equity', 60], ['Bonds', 30], ['Cash', 10]],
                  columns=('Asset', 'Weight'), chart_type='composition')
    assert [round(segment['pct']) for segment in model['segments']] == [60, 30, 10]
    assert model['total'] == 100


def test_a_negative_share_is_dropped_rather_than_drawn():
    """A share of a whole cannot be negative. Drawing one would make the
    segments stop summing to the total."""
    model = chart([['Equity', 60], ['Overdraft', -10], ['Cash', 40]],
                  columns=('Asset', 'Weight'), chart_type='composition')
    assert [segment['label'] for segment in model['segments']] == ['Equity', 'Cash']
    assert sum(segment['pct'] for segment in model['segments']) == pytest.approx(100)


def test_a_long_tail_folds_into_other_rather_than_cycling_hues():
    rows = [[f'Sector {index}', index] for index in range(1, 15)]
    model = chart(rows, columns=('Sector', 'Weight'), chart_type='donut')
    assert model['folded'] is True
    assert len(model['segments']) == MAX_SERIES
    assert model['segments'][-1]['label'] == OTHER_LABEL
    # Folding, not truncating: the ring is still a whole.
    assert sum(segment['pct'] for segment in model['segments']) == pytest.approx(100)


def test_donut_segments_leave_a_gap_and_run_in_order():
    model = chart([['Equity', 50], ['Bonds', 50]],
                  columns=('Asset', 'Weight'), chart_type='donut')
    first, second = model['segments']
    # Each dash is its share of the circumference, less the surface gap.
    assert first['dash'] < model['segments'][0]['rest'] / 2
    # The second starts where the first ended, not at zero.
    assert second['offset'] < first['offset']


# ---------------------------------------------------------------------------
# Nothing to draw
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('rows,columns', [
    ([], ('Sector', 'Weight')),
    ([['Financials', 'n/a']], ('Sector', 'Weight')),
    ([['Financials']], ('Sector',)),
    ([['Equity', 0], ['Cash', 0]], ('Asset', 'Weight')),
])
def test_nothing_drawable_returns_no_chart(rows, columns):
    """None rather than an empty chart: a titled section with a blank chart
    in it reads as a rendering failure, which is how a client reads it too."""
    kind = 'composition' if len(columns) == 2 else 'bar_comparison'
    assert chart(rows, columns=columns, chart_type=kind) is None


def test_an_unknown_chart_type_is_ignored():
    assert chart([['A', 1, 2]], chart_type='sunburst') is None
    assert chart([['A', 1, 2]], chart_type=None) is None
