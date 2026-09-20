"""Chart geometry for print.

Tier 1 of the pipeline: the forms that need no computed axis -- bars,
part-to-whole, ring -- built as plain geometry and rendered as HTML/CSS or
static SVG. They are ports of the app's own `BarChart`, `CompositionBar` and
`DonutChart`, which are already print-safe markup (the first is pure
HTML/CSS with zero SVG; the other two are static SVG). Anything needing a
scale, ticks or a computed axis goes to tier 2 instead.

Two things change in the port, both because **paper has no pointer**:

  * every tooltip becomes a direct label or a legend row. The screen
    components put the value in a hover tip; here it has to be on the page,
    which is also what discharges the palette's sub-3:1 contrast warning.
  * `color-mix()` and gradients resolved through it become literal hex.
    WeasyPrint drops `color-mix()` silently, so the screen components'
    track tint and bar gradient are precomputed here.

Everything this module returns is plain data. The Jinja template draws it;
no HTML is built in Python.
"""

import math

from renderers.chart_palette import fold_to_other, series_colors

# Mark specs, in print units. The screen components are specified in px; a
# 2px surface gap at 96dpi is ~0.5mm, and a 4px rounded data-end ~1mm.
SEGMENT_GAP_MM = 0.5
BAR_RADIUS_MM = 1.0
BAR_HEIGHT_MM = 2.4
# A bar shorter than this is invisible; the screen component uses the same
# floor so a near-zero value still reads as "present but small".
MIN_VISIBLE_PCT = 1.5

DONUT_RADIUS = 60
DONUT_STROKE = 22
DONUT_BOX = 160
DONUT_CIRCUMFERENCE = 2 * math.pi * DONUT_RADIUS

# The forms this tier draws. `bar_comparison` is the vocabulary the existing
# templates already use, kept so Phase A's documents keep rendering.
KINDS = ('bar', 'bar_comparison', 'composition', 'donut')


def _series_rows(columns, rows, to_number, format_cell):
    """(label, [values], [display strings]) per row, dropping rows whose
    values are unreadable.

    The display strings are carried alongside the numbers rather than
    recomputed later, so a dropped or duplicated row cannot slide the labels
    out of step with the bars they annotate.

    `to_number` is injected rather than imported to keep this module free of
    the renderer -- the same parsing has to serve both, and a chart that
    silently vanished because '22%' would not parse is exactly the bug Phase
    A shipped once already.
    """
    parsed = []
    for row in rows:
        if not row:
            continue
        cells = list(row[1:len(columns)])
        values = [to_number(cell) for cell in cells]
        if not values or any(value is None for value in values):
            continue
        parsed.append((str(row[0]), values, [format_cell(cell) for cell in cells]))
    return parsed


def _legend(labels, colors):
    return [{'label': label, 'color': color} for label, color in zip(labels, colors)]


def _bars(parsed, colors):
    """Grouped horizontal bars, scaled to the largest magnitude present.

    One shared scale across every series -- a second scale is the single
    worst thing a chart can do, and grouped bars are where the temptation
    shows up.

    When any value is negative the chart becomes **diverging**: a zero line
    down the middle, bars growing left or right from it. Drawing a negative
    as a positive-length bar is not a cosmetic shortcut, it is a false
    chart -- an attribution of -40bps would otherwise be indistinguishable
    from +40bps, and longer than a real +15.
    """
    signed = any(value < 0 for _, values, _ in parsed for value in values)
    peak = max((max(abs(value) for value in values) for _, values, _ in parsed), default=0) or 1
    rows = []
    for label, values, labels in parsed:
        rows.append({
            'label': label,
            'bars': [
                {
                    # Against a full track, or against one half of it when
                    # the zero line is in the middle.
                    'pct': max(min(abs(value) / peak * 100, 100),
                               MIN_VISIBLE_PCT if value else 0),
                    'color': color,
                    'value_label': text,
                    'negative': value < 0,
                }
                for value, color, text in zip(values, colors, labels)
            ],
        })
    return rows, signed


def _shares(pairs, colors):
    """Part-to-whole segments from (label, value) pairs.

    Negative and zero values are dropped: a share of a whole cannot be
    negative, and a zero-width segment with a gap either side draws as a
    stray line rather than nothing.
    """
    positive = [(label, value) for label, value in pairs if value > 0]
    total = sum(value for _, value in positive)
    if not total:
        return [], 0
    return [
        {'label': label, 'value': value, 'pct': value / total * 100, 'color': color}
        for (label, value), color in zip(positive, colors)
    ], total


def _donut_segments(shares):
    """Ring geometry as stroke-dasharray offsets.

    Drawn with one circle per segment rather than arc paths, the same
    technique the screen component uses -- fewer places to get a sweep flag
    wrong, and WeasyPrint renders it as vector.
    """
    gap = DONUT_CIRCUMFERENCE * (SEGMENT_GAP_MM / 40)
    consumed = 0.0
    segments = []
    for share in shares:
        length = share['pct'] / 100 * DONUT_CIRCUMFERENCE
        segments.append({
            **share,
            'dash': max(length - gap, 0.1),
            'rest': DONUT_CIRCUMFERENCE,
            'offset': -consumed,
        })
        consumed += length
    return segments


def build_chart(component, to_number, format_cell, brand_colors=None):
    """A drawable model, or None when there is nothing to draw.

    Returning None rather than an empty chart matters: a titled section with
    an empty chart in it looks like a rendering failure, which is how a
    client reads it too.
    """
    kind = component.get('chart_type')
    if kind not in KINDS:
        return None

    columns = component.get('columns') or []
    rows = component.get('rows') or []
    if len(columns) < 2 or not rows:
        return None

    parsed = _series_rows(columns, rows, to_number, format_cell)
    if not parsed:
        return None

    if kind in ('composition', 'donut'):
        # One series only: a part-to-whole form has one whole.
        pairs, folded = fold_to_other([(label, values[0]) for label, values, _ in parsed])
        shares, total = _shares(pairs, series_colors(len(pairs), brand_colors))
        if not shares:
            return None
        model = {
            'kind': kind,
            'segments': _donut_segments(shares) if kind == 'donut' else shares,
            'legend': [{'label': share['label'], 'color': share['color'],
                        'value_label': f"{share['pct']:.0f}%"} for share in shares],
            'total': total,
            'total_label': columns[1],
            'folded': folded,
            'box': DONUT_BOX,
            'radius': DONUT_RADIUS,
            'stroke': DONUT_STROKE,
        }
        return model

    series_labels = list(columns[1:])
    colors = series_colors(len(series_labels), brand_colors)
    rows_model, signed = _bars(parsed, colors)
    return {
        'kind': 'bar',
        'rows': rows_model,
        # A diverging chart needs its zero line drawn and labelled; a
        # one-sided one must not pretend to have one.
        'signed': signed,
        # A single series needs no legend -- the section title names it.
        'legend': _legend(series_labels, colors) if len(series_labels) > 1 else [],
        'bar_height_mm': BAR_HEIGHT_MM,
        'bar_radius_mm': BAR_RADIUS_MM,
        'gap_mm': SEGMENT_GAP_MM,
    }
