"""Tier 2 of the chart pipeline: the forms that need a computed axis.

A trend over time needs ticks, a scale and a baseline that mean something
numerically. Tier 1 draws bars whose lengths are ratios, which needs no
axis; a line chart without one is decoration. Rather than write a scale and
tick generator by hand, this hands the job to Vega-Lite.

`vl-convert` is a pure-Rust binding: no Node, no browser, no network. It
takes a JSON spec and returns SVG, which WeasyPrint renders as vector.
Steady-state conversion is ~25ms, so this stays on the synchronous render
path.

The spec is themed to the document rather than left at Vega's defaults --
the document's own font, the muted ink from the theme, hairline rules --
so a chart does not read as something pasted in from another program.
"""

import json

import vl_convert

from renderers.chart_palette import series_colors

# The content box of an A4 page at this document's margins, in CSS px at
# 96dpi: 210mm - 32mm of margins. The SVG scales to its container, but
# authoring at the real width keeps label density honest.
CHART_WIDTH = 660
CHART_HEIGHT = 190

# Matches the document stylesheet, so chart type and body type are the same
# type. Without this, Vega picks its own sans and the chart looks imported.
FONT = 'DejaVu Sans'
LABEL_SIZE = 9
LINE_WIDTH = 2
# Vega sizes points by AREA in square px. 64 gives an 8px-diameter mark,
# the floor the mark spec sets.
POINT_SIZE = 64


class ChartTooComplex(ValueError):
    """More series than the palette validates for."""


def _config(theme):
    """Vega config that makes the chart part of the document."""
    return {
        'font': FONT,
        'background': None,
        'axis': {
            'labelFont': FONT, 'titleFont': FONT,
            'labelFontSize': LABEL_SIZE - 1, 'titleFontSize': LABEL_SIZE,
            'labelColor': theme['muted'], 'titleColor': theme['muted'],
            # Recessive: the data is the subject, the frame is not.
            'domainColor': theme['rule'], 'tickColor': theme['rule'],
            'gridColor': theme['rule'], 'gridOpacity': 0.6, 'gridWidth': 0.5,
            'labelPadding': 4, 'titlePadding': 8,
        },
        'legend': {
            'labelFont': FONT, 'titleFont': FONT,
            'labelFontSize': LABEL_SIZE - 1, 'labelColor': theme['muted'],
            'orient': 'bottom', 'direction': 'horizontal',
            'title': None, 'symbolType': 'square', 'symbolSize': 60,
        },
        'view': {'stroke': None},
    }


# An area fill encodes magnitude measured from the baseline, so its
# baseline has to be zero -- Vega enforces that, correctly. A series that
# never approaches zero (an indexed "growth of $100" running 100 to 119)
# therefore renders as a flat line pinned to the top of an empty plot. The
# fill is not what that chart is about, so it becomes a line with a
# truncated axis instead. This is the ratio at which the fill stops being
# worth its baseline.
AREA_NEEDS_ZERO_RATIO = 0.5


def _wants_area(kind, values):
    if kind != 'area':
        return False
    numbers = [row['y'] for row in values]
    low, high = min(numbers), max(numbers)
    if low < 0 or high <= 0:
        # Crosses or sits below zero: the baseline is meaningful, so the
        # fill is too.
        return True
    return low / high <= AREA_NEEDS_ZERO_RATIO


def _layers(kind):
    """Line, or line plus a soft wash beneath it.

    The area fill is deliberately faint. A saturated fill under a line reads
    as a magnitude in its own right, which it is not -- the line is the
    value and the fill is only there to give it a direction.
    """
    base = {
        'mark': {'type': 'line', 'strokeWidth': LINE_WIDTH,
                 'point': {'size': POINT_SIZE, 'filled': True}},
    }
    if kind == 'area':
        return [
            {'mark': {'type': 'area', 'opacity': 0.14, 'line': False}},
            base,
        ]
    return [base]


def build_spec(kind, x_label, series_names, rows, theme, brand_colors=None):
    """A Vega-Lite spec from the same (label, [values]) rows tier 1 uses.

    `rows` are (label, [values]) -- one value per series, in series_names
    order.
    """
    colors = series_colors(len(series_names), brand_colors)

    values = [
        {'x': label, 'series': name, 'y': value}
        for label, series_values in rows
        for name, value in zip(series_names, series_values)
    ]
    draw_area = _wants_area(kind, values)

    encoding = {
        # sort=None means "keep the order the rows arrived in". Without it
        # Vega sorts an ordinal domain by value, which for month labels is
        # ALPHABETICAL -- Apr, Aug, Dec, Feb, Jan, Jul, Jun... A growth
        # chart with its months shuffled is worse than no chart, and it
        # looks entirely plausible until you read the axis.
        'x': {'field': 'x', 'type': 'ordinal', 'title': x_label, 'sort': None,
              'axis': {'labelAngle': 0, 'grid': False}},
        # A line's value is its height, so a truncated axis is legitimate
        # and often necessary -- a series moving between 98 and 104 against
        # a zero baseline is a flat line. It is NOT legitimate for an area
        # (see _wants_area) or for bars, which is why tier 1 keeps its own
        # baseline.
        'y': {'field': 'y', 'type': 'quantitative', 'title': None,
              'scale': {'zero': draw_area, 'nice': True}},
    }
    if len(series_names) > 1:
        encoding['color'] = {
            'field': 'series', 'type': 'nominal',
            'scale': {'domain': list(series_names), 'range': colors},
        }

    spec = {
        '$schema': 'https://vega.github.io/schema/vega-lite/v5.json',
        'width': CHART_WIDTH, 'height': CHART_HEIGHT,
        'data': {'values': values},
        'encoding': encoding,
        'layer': _layers('area' if draw_area else 'line'),
        'config': _config(theme),
    }
    if len(series_names) == 1:
        # No colour encoding, so no legend: one series is named by the
        # section title. The hue is set on the mark instead.
        for layer in spec['layer']:
            layer['mark']['color'] = colors[0]
    return spec


def render_svg(spec):
    """SVG for a spec.

    Returned as a string and inlined into the document. That is safe
    because vl_convert escapes every data-derived string into SVG text --
    a label of '</text></svg><script>' comes back escaped, not as markup.
    `test_vega_charts.py` pins that, since report labels arrive from a
    warehouse rather than from us.
    """
    return vl_convert.vegalite_to_svg(json.dumps(spec))
