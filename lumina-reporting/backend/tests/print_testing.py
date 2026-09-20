"""Rasterisation helpers shared by the print-CSS tests.

A print regression is invisible until a client opens the PDF, so both the
CSS support matrix and the golden-document tests work the same way: render
to PDF, rasterise, and look at pixels. Asserting on the HTML would prove
only that a rule was written, not that the engine honoured it.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops

from renderers.html_pdf_renderer import render_html_pdf
from weasyprint import HTML

GOLDEN_DIR = Path(__file__).parent / 'golden'
# 96 DPI keeps reference images small enough to commit while still catching
# a shifted rule or a dropped fill. Fine typographic differences are not
# what these tests are for.
RASTER_DPI = 96


def _require_pdftoppm():
    if shutil.which('pdftoppm') is None:  # pragma: no cover - environment guard
        raise RuntimeError('pdftoppm (poppler-utils) is required for print tests')


def pdf_to_images(pdf_bytes, dpi=RASTER_DPI):
    """Every page of a PDF, as PIL images."""
    _require_pdftoppm()
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / 'doc.pdf'
        source.write_bytes(pdf_bytes)
        subprocess.run(
            ['pdftoppm', '-png', '-r', str(dpi), str(source), str(Path(directory) / 'page')],
            check=True, capture_output=True,
        )
        return [Image.open(path).convert('RGB').copy()
                for path in sorted(Path(directory).glob('page-*.png'))]


def html_to_image(document_html, dpi=RASTER_DPI):
    """One standalone HTML fragment, rendered and rasterised. Used by the
    support-matrix probes, which are not full reports."""
    pdf = HTML(string=document_html).write_pdf()
    return pdf_to_images(pdf, dpi=dpi)[0]


def content_to_images(content, dpi=RASTER_DPI):
    return pdf_to_images(render_html_pdf(content), dpi=dpi)


def ink_ratio(image, box=None):
    """Fraction of pixels in `box` that are not white.

    The probe behind every support assertion: if a CSS feature is
    unsupported, WeasyPrint draws nothing and the region stays blank. A
    ratio near zero means "the engine ignored this rule".
    """
    region = image.crop(box) if box else image
    pixels = list(region.getdata())
    if not pixels:
        return 0.0
    inked = sum(1 for pixel in pixels if pixel != (255, 255, 255))
    return inked / len(pixels)


def dominant_colour(image, box=None):
    """The most common non-white colour in a region, as an (r, g, b) tuple.

    Lets a test assert that a fill is *the right colour*, not merely that
    something was drawn -- the difference between catching a dropped rule
    and catching a wrong one.
    """
    region = image.crop(box) if box else image
    counts = {}
    for pixel in region.getdata():
        if pixel == (255, 255, 255):
            continue
        counts[pixel] = counts.get(pixel, 0) + 1
    return max(counts, key=counts.get) if counts else None


def close_to(actual, expected, tolerance=12):
    """Channel-wise colour comparison with room for anti-aliasing and the
    rasteriser's own rounding."""
    if actual is None:
        return False
    return all(abs(a - b) <= tolerance for a, b in zip(actual, expected))


def hex_to_rgb(value):
    cleaned = value.lstrip('#')
    return tuple(int(cleaned[index:index + 2], 16) for index in (0, 2, 4))


def difference_ratio(first, second):
    """Fraction of pixels that differ between two renders.

    Deliberately a *count* of differing pixels rather than a mean intensity
    delta: a mean hides a small region of catastrophic change behind a large
    area of agreement, which is exactly the regression worth catching.
    """
    if first.size != second.size:
        return 1.0
    difference = ImageChops.difference(first, second)
    changed = sum(1 for pixel in difference.getdata() if any(channel > 8 for channel in pixel))
    return changed / (first.size[0] * first.size[1])


# A full-resolution A4 page is ~794x1123 px at 96 DPI. Comparing at that
# scale makes the test a hinting detector: the same document rasterised on
# two machines differs in thousands of edge pixels without a single visible
# change. Downsampling to this width averages that noise away while keeping
# every structural fact -- where blocks sit, how tall they are, what colour
# they are, how many pages there are.
FINGERPRINT_WIDTH = 120


def fingerprint(image, width=FINGERPRINT_WIDTH):
    """A page reduced to a small box-filtered image, for golden comparison."""
    height = max(1, round(image.size[1] * width / image.size[0]))
    return image.resize((width, height), Image.BOX)


def fingerprint_difference(first, second, tolerance=24):
    """Fraction of fingerprint cells whose colour moved by more than
    `tolerance` on any channel.

    A cell covers roughly 7x7 source pixels, so a changed cell means a real
    block of the page changed -- not an antialiased glyph edge.
    """
    if first.size != second.size:
        return 1.0
    return sum(
        1 for a, b in zip(first.getdata(), second.getdata())
        if any(abs(x - y) > tolerance for x, y in zip(a, b))
    ) / (first.size[0] * first.size[1])


# Rendered by the same engine and fonts as a real report, but independent of
# the report template -- so a CSS change in the template cannot move it, and
# only a different WeasyPrint, Pango or font set can. That is exactly the
# distinction the golden tests need: "the document changed" must not be
# confused with "this machine lays out text differently".
#
# It exercises every face a document may use (regular and bold), because an
# earlier version used only the regular one and therefore did NOT notice
# that a second machine resolved a different face for the one style the
# canary omitted.
ENVIRONMENT_CANARY = '''
<style>
  @page { size: 80mm 40mm; margin: 4mm }
  body { margin: 0; font-family: "DejaVu Sans", Helvetica, Arial, sans-serif;
         font-size: 9pt; line-height: 1.42 }
  .rule { height: 2pt; background: #0d6b5f; margin: 2mm 0 }
  table { width: 100%; border-collapse: collapse; font-size: 8.5pt }
  td { padding: 1.9mm 2mm; border-bottom: .4pt solid #dcdcdc }
</style>
<div>Hamburgefonstiv &mdash; 1,234.50 (0.4%)</div>
<div style="font-weight:700">Hamburgefonstiv Bold 1,234.50</div>
<div class="rule"></div>
<table><tr><td>Tate &amp; Lyle</td><td>3.4%</td></tr></table>
'''

ENVIRONMENT_REFERENCE = GOLDEN_DIR / '_environment.png'


def environment_fingerprint():
    return fingerprint(html_to_image(ENVIRONMENT_CANARY))


def environment_matches_references(tolerance=0.005):
    """Whether this machine renders text the way the golden references were
    made. False means the golden comparison would measure the environment
    rather than the code, so it should be skipped, not failed."""
    if not ENVIRONMENT_REFERENCE.exists():
        return False
    recorded = Image.open(ENVIRONMENT_REFERENCE).convert('RGB')
    return fingerprint_difference(environment_fingerprint(), recorded) <= tolerance
