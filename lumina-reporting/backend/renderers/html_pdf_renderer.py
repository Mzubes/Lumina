"""HTML + CSS Paged Media renderer (Phase A of the document engine plan).

Replaces the fpdf2 path. fpdf2 is an imperative cursor writer whose core
fonts are latin-1 only -- which is why the old renderer carries a
substitution table that silently turns em-dashes into hyphens and drops
anything else. It also has no concept of a running header, a page counter,
or a table header that repeats across a break, so all three were being
hand-simulated.

This renderer consumes exactly the same payload `resolve_report_content()`
already produces, so nothing upstream changes. The old renderer stays
registered as 'pdf_legacy' for one release so the two can be compared
side by side.

Two rules hold everywhere below:

1. **No `color-mix()`.** It renders NOTHING in WeasyPrint, silently --
   verified: plain hex renders, linear-gradient renders, color-mix does not.
   The app's screen stylesheet uses it 48 times. Every derived colour here
   is precomputed in Python instead. `tests/test_html_pdf_renderer.py`
   asserts the generated CSS is free of it.

2. **No JavaScript.** WeasyPrint does not run any, and nothing here needs
   it: charts are CSS bars or inline SVG, both of which it renders natively.
"""

import html
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from renderers.charts import build_chart
from renderers.layout import layout_from_components, pin_repeating_bands, validate
from schema_v2.styling import element_classes
from weasyprint import HTML

TEMPLATE_DIR = Path(__file__).parent / 'templates'

# Fallbacks when a template carries no theme_config.
DEFAULT_PRIMARY = '#10265c'
DEFAULT_ACCENT = '#1447E6'
DEFAULT_INK = '#141821'
DEFAULT_MUTED = '#667085'
DEFAULT_RULE = '#dfe4ee'


def _clamp(value):
    return max(0, min(255, int(round(value))))


def _hex_to_rgb(value, fallback=None):
    if not isinstance(value, str):
        return fallback
    cleaned = value.strip().lstrip('#')
    if len(cleaned) != 6:
        return fallback
    try:
        return tuple(int(cleaned[index:index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return fallback


def _rgb_to_hex(rgb):
    return '#%02x%02x%02x' % tuple(_clamp(channel) for channel in rgb)


def mix(color, other, weight):
    """Precomputed color-mix. `weight` is how much of `color` survives.

    This exists because WeasyPrint silently drops `color-mix()`. Doing the
    arithmetic here means the stylesheet only ever contains literal hex,
    which is the one form every engine agrees on.
    """
    first = _hex_to_rgb(color) or (0, 0, 0)
    second = _hex_to_rgb(other) or (255, 255, 255)
    return _rgb_to_hex(
        first[index] * weight + second[index] * (1 - weight) for index in range(3)
    )


def _theme(theme_config):
    """Resolve a template's theme into a flat set of literal colours.

    Every tint and shade a component might want is computed once here, so no
    stylesheet rule ever has to derive a colour at render time.
    """
    primary = theme_config.get('primary_color') or DEFAULT_PRIMARY
    accent = theme_config.get('accent_color') or DEFAULT_ACCENT
    if not _hex_to_rgb(primary):
        primary = DEFAULT_PRIMARY
    if not _hex_to_rgb(accent):
        accent = DEFAULT_ACCENT

    return {
        'primary': primary,
        'accent': accent,
        'ink': DEFAULT_INK,
        'muted': DEFAULT_MUTED,
        'rule': DEFAULT_RULE,
        # Precomputed tints -- the header band, the zebra stripe, the chart
        # track. Each would have been a color-mix() in the screen stylesheet.
        'primary_tint': mix(primary, '#ffffff', 0.10),
        'primary_tint_strong': mix(primary, '#ffffff', 0.18),
        'accent_tint': mix(accent, '#ffffff', 0.12),
        'accent_bar_light': mix(accent, '#ffffff', 0.55),
        'zebra': mix(primary, '#ffffff', 0.04),
        'logo_url': theme_config.get('logo_url') or '',
    }


def to_number(value):
    """A cell's numeric value, or None when it has none.

    Warehouse-delivered cells arrive already formatted as often as not --
    "22%", "$1,234", "(0.4)". Charting and alignment both need the number
    behind the presentation, and parsing it in one place means the chart and
    the column alignment can never disagree about whether a column is
    numeric.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    probe = value.strip().replace(',', '').replace('%', '').replace('$', '')
    # Accounting negatives: (0.4) means -0.4.
    negative = probe.startswith('(') and probe.endswith(')')
    if negative:
        probe = probe[1:-1]
    if not probe:
        return None
    try:
        number = float(probe)
    except ValueError:
        return None
    return -number if negative else number


def _numeric(value):
    """True when a cell should right-align and use tabular figures.

    Column alignment is decided from the data, not configured per template:
    a numeric column that left-aligns is the single most common way a
    generated table looks amateur.
    """
    return to_number(value) is not None


def _format_cell(value):
    if value is None or value == '':
        return '—'
    if isinstance(value, float):
        # Thousands separators and two decimals -- the house default for a
        # figure with no explicit format. Whole numbers keep no decimals so
        # a quantity column doesn't read as money.
        return f'{value:,.2f}' if value % 1 else f'{value:,.0f}'
    if isinstance(value, int):
        return f'{value:,}'
    return str(value)


# A4 less the page margins leaves ~245mm of content. These are the rendered
# heights of the pieces a section is made of, measured from the stylesheet
# above rather than guessed.
CONTENT_HEIGHT_MM = 245
SECTION_HEADING_MM = 12
TABLE_HEADER_MM = 9
TABLE_ROW_MM = 5.6
CHART_ROW_MM = 7.0
CHART_CHROME_MM = 12
DONUT_MM = 38
# vega_charts.CHART_HEIGHT is 190 CSS px, which is 190/96 inches.
VEGA_MM = 51


def _estimated_height_mm(component, chart):
    """Roughly how tall a section will render.

    Rough is enough: it only decides whether a section is short enough to
    ask the engine to keep together, and the threshold below leaves a wide
    margin for being wrong.
    """
    height = SECTION_HEADING_MM if component.get('title') else 0
    rows = component.get('rows') or []
    if component.get('columns') and rows:
        height += TABLE_HEADER_MM + TABLE_ROW_MM * len(rows)
    if chart:
        # Branching on the kind explicitly rather than falling through to a
        # row count: a tier-2 chart is one fixed-height SVG and has no rows
        # at all, which used to raise here.
        if chart['kind'] == 'donut':
            height += DONUT_MM
        elif chart['kind'] == 'composition':
            height += CHART_CHROME_MM + CHART_ROW_MM
        elif chart['kind'] == 'vega':
            height += CHART_CHROME_MM + VEGA_MM
        else:
            height += CHART_CHROME_MM + CHART_ROW_MM * len(chart['rows'])
    return height


def _is_compact(component, chart):
    """Whether to ask the engine to keep this section on one page.

    Half a page, not a whole one: a section that only just fits would be
    pushed to a fresh page whenever it lands mid-page, which trades an ugly
    break for a half-empty page. Below half, the move is nearly always the
    right one.
    """
    return _estimated_height_mm(component, chart) <= CONTENT_HEIGHT_MM / 2


def _prepare(content):
    theme = _theme(content.get('theme_config') or {})
    components = []
    for component in content.get('components') or []:
        prepared = dict(component)
        columns = component.get('columns') or []
        rows = component.get('rows') or []
        if columns:
            prepared['numeric_columns'] = [
                # A column is numeric when its data is, judged on the first
                # row that actually has a value there.
                any(_numeric(row[index]) for row in rows if index < len(row))
                for index in range(len(columns))
            ]
            prepared['formatted_rows'] = [
                [_format_cell(cell) for cell in row] for row in rows
            ]
        # Chart colours come from the brand kit's validated categorical
        # palette, never from the template's theme: a theme colour is one
        # hue, and a chart needs a set that separates under colour-vision
        # deficiency. See renderers/chart_palette.py.
        prepared['chart'] = build_chart(component, to_number, _format_cell,
                                        content.get('brand_colors'), theme)
        prepared['compact'] = _is_compact(component, prepared['chart'])
        components.append(prepared)

    # Everything below the renderer reads the layout tree, never the flat
    # list -- see renderers/layout.py. The legacy path produces a tree that
    # renders byte-identically to what the flat list produced, which is what
    # makes the v2 cutover checkable on real documents.
    sections = layout_from_components(components)
    for section, component in zip(sections, components):
        section['compact'] = component['compact']
    return theme, sections


def _environment():
    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(['html']),
    )
    environment.filters['cell'] = _format_cell
    # The one place a style_token or an option becomes a class. Kept in
    # schema_v2.styling rather than in the template so the API's validation
    # and the renderer's output cannot drift apart.
    environment.filters['style_classes'] = lambda element: ' '.join(element_classes(element))
    return environment


def render_document_html(content):
    """The HTML a PDF is made from. Exposed separately so the canvas's live
    preview and the golden-render tests can read exactly what the PDF sees,
    rather than a lookalike."""
    theme, sections = _prepare(content)
    template = _environment().get_template('report.html')
    return template.render(
        content=content,
        sections=sections,
        margin_boxes={},
        reserved={'top': 0, 'bottom': 0},
        document_header=True,
        theme=theme,
        header=content.get('header_config') or {},
        footer=content.get('footer_config') or {},
    )


class TemplateLayoutError(ValueError):
    """A layout tree that cannot be rendered.

    Raised before a single byte is drawn. A structurally wrong template
    that renders anyway produces a document someone has to notice is
    wrong, which is worse than one that refuses to build.
    """


def render_template_html(tree, content=None, theme_config=None):
    """A v2 DocumentTemplate's resolved tree, as HTML.

    `tree` has already been through `layout_from_template()` and
    `bindings.resolve_tree()` -- structure, then data. This adds the page
    furniture and draws it.
    """
    problems = validate(tree)
    if problems:
        raise TemplateLayoutError('; '.join(problems))

    theme = _theme(theme_config or {})
    sections, margin_boxes, reserved = pin_repeating_bands(tree)
    for section in sections:
        section.setdefault('compact', False)
    return _environment().get_template('report.html').render(
        content=content or {},
        sections=sections,
        margin_boxes=margin_boxes,
        reserved=reserved,
        # A designed template draws its own masthead.
        document_header=False,
        theme=theme,
        header=(content or {}).get('header_config') or {},
        footer=(content or {}).get('footer_config') or {},
    )


def render_template_pdf(tree, content=None, theme_config=None):
    document = HTML(string=render_template_html(tree, content, theme_config),
                    base_url=str(TEMPLATE_DIR))
    return document.write_pdf()


def render_html_pdf(content):
    """Entry point matching the renderer registry's contract: payload in,
    PDF bytes out."""
    document = HTML(string=render_document_html(content), base_url=str(TEMPLATE_DIR))
    return document.write_pdf()
