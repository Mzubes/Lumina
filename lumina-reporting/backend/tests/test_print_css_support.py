"""What the print engine actually supports — probed, not assumed.

Every assertion here renders a box that is teal ONLY if the feature works,
then looks at the pixels. That matters because WeasyPrint's failure mode for
an unsupported property is to draw NOTHING — no error, no fallback, no
warning. A template author reaching for the wrong property gets an invisible
element and no clue why.

This file is the boundary, in code. It documents what may be used in a print
template, and it fails if a WeasyPrint upgrade moves that boundary in either
direction — including the pleasant direction, so the unsupported list can be
shortened deliberately rather than by accident.
"""

import pytest

from tests.print_testing import close_to, dominant_colour, hex_to_rgb, html_to_image, ink_ratio

TEAL = '#0d6b5f'
PAGE = '<style>@page{size:60mm 40mm;margin:0}body{margin:0}</style>'

# Each probe paints the whole page teal if, and only if, the feature works.
SUPPORTED = {
    'linear-gradient': f'<div style="width:60mm;height:40mm;background:linear-gradient({TEAL},{TEAL})"></div>',
    'var() custom property': f'<div style="--c:{TEAL};width:60mm;height:40mm;background:var(--c)"></div>',
    'calc()': f'<div style="width:calc(30mm * 2);height:40mm;background:{TEAL}"></div>',
    'currentColor': f'<div style="color:{TEAL};width:60mm;height:40mm;background:currentColor"></div>',
    'rgba()': '<div style="width:60mm;height:40mm;background:rgba(13,107,95,1)"></div>',
    'flexbox': f'<div style="display:flex;height:40mm"><div style="flex:1;background:{TEAL}"></div></div>',
    'css grid': f'<div style="display:grid;grid-template-columns:1fr;height:40mm"><div style="background:{TEAL}"></div></div>',
    'position:absolute': f'<div style="position:absolute;inset:0;background:{TEAL}"></div>',
    'border-radius': f'<div style="width:60mm;height:40mm;background:{TEAL};border-radius:4mm"></div>',
    'transform': f'<div style="width:60mm;height:40mm;background:{TEAL};transform:rotate(0deg)"></div>',
    'opacity': f'<div style="width:60mm;height:40mm;background:{TEAL};opacity:1"></div>',
    'clip-path': f'<div style="width:60mm;height:40mm;background:{TEAL};clip-path:inset(0)"></div>',
    'inline svg': f'<svg width="60mm" height="40mm"><rect width="100%" height="100%" fill="{TEAL}"/></svg>',
}

# The silent-failure list. Anything here draws nothing at all.
UNSUPPORTED = {
    # The one that motivated this whole phase. styles.css uses it 48 times.
    'color-mix()': f'<div style="width:60mm;height:40mm;background:color-mix(in srgb,{TEAL} 100%,white)"></div>',
    # Found while building this matrix -- and a natural reach for a chart
    # container, which makes it the next color-mix waiting to happen.
    'aspect-ratio': f'<div style="width:60mm;aspect-ratio:3/2;background:{TEAL}"></div>',
}


@pytest.mark.parametrize('feature', sorted(SUPPORTED))
def test_supported_css_feature_renders(feature):
    image = html_to_image(PAGE + SUPPORTED[feature])
    assert ink_ratio(image) > 0.9, f'{feature} drew nothing'
    assert close_to(dominant_colour(image), hex_to_rgb(TEAL)), f'{feature} drew the wrong colour'


@pytest.mark.parametrize('feature', sorted(UNSUPPORTED))
def test_unsupported_css_feature_draws_nothing(feature):
    """Pinned deliberately. If one of these starts working after an engine
    upgrade, this test fails and the allow-list gets widened on purpose --
    rather than a template quietly depending on it."""
    image = html_to_image(PAGE + UNSUPPORTED[feature])
    assert ink_ratio(image) < 0.05, (
        f'{feature} now renders — WeasyPrint support changed. '
        f'Move it to SUPPORTED and relax the print-CSS lint if that is intended.'
    )


def test_box_shadow_paints_but_only_outside_the_box():
    """Supported, with a caveat worth pinning: the shadow paints, so a
    'spread' shadow is a usable border substitute."""
    markup = f'<div style="width:40mm;height:20mm;margin:10mm;background:#fff;box-shadow:0 0 0 8mm {TEAL}"></div>'
    image = html_to_image(PAGE + markup)
    assert 0.3 < ink_ratio(image) < 0.8
    assert close_to(dominant_colour(image), hex_to_rgb(TEAL))


# ---------------------------------------------------------------------------
# Pagination
#
# Colour failures are silent; pagination failures are worse -- a rule the
# engine ignores leaves a chart stranded on the wrong page under the wrong
# heading, and the document still looks plausible. Both facts below are
# relied on by report.html, so both are probed rather than assumed.
# ---------------------------------------------------------------------------

PAGE_BREAK_CASE = (
    '<style>@page{size:60mm 40mm;margin:2mm}body{margin:0}'
    '.a{{height:20mm;background:#0d6b5f}}.b{{height:10mm;background:#c9bd9a}}'
    '.c{{height:10mm;background:#0d6b5f;{rule}}}</style>'
    '<div class="a"></div><div class="b"></div><div class="c"></div>'
)


def _page_inks(rule):
    from tests.print_testing import pdf_to_images
    from weasyprint import HTML
    document = PAGE_BREAK_CASE.replace('{rule}', rule)
    return [round(ink_ratio(page), 2) for page in pdf_to_images(HTML(string=document).write_pdf())]


def test_break_before_avoid_is_honoured():
    """report.html uses it to keep a chart with the table it belongs to.

    The content box holds 36mm; the blocks are 20 + 10 + 10. Left alone the
    engine fills page one with the first two. Honouring the rule, the middle
    block has to travel with the third.
    """
    assert _page_inks('') == [0.69, 0.23]
    assert _page_inks('break-before:avoid') == [0.46, 0.46]


def test_break_inside_avoid_degrades_instead_of_clipping():
    """report.html puts it on every section so a short one stays whole. A
    section taller than a page must still break normally -- if the engine
    clipped instead, rows would vanish from a client's statement with no
    error anywhere."""
    import io

    from pypdf import PdfReader
    from weasyprint import HTML

    rows = ''.join(f'<tr><td>Row {index}</td></tr>' for index in range(1, 61))
    document = ('<style>@page{size:60mm 40mm;margin:2mm}section{break-inside:avoid}'
                'table{width:100%;font-size:5pt}</style>'
                f'<section><table>{rows}</table></section>')
    pdf = HTML(string=document).write_pdf()
    text = ''.join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
    assert len(PdfReader(io.BytesIO(pdf)).pages) > 1
    assert [index for index in range(1, 61) if f'Row {index}' not in text] == []
