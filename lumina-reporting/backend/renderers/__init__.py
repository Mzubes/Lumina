from renderers.html_pdf_renderer import render_html_pdf
from renderers.pdf_renderer import render_pdf
from renderers.pptx_renderer import render_pptx
from renderers.raw_renderer import render_raw
from renderers.xlsx_renderer import render_xlsx

RENDERERS = {
    # HTML + CSS Paged Media (WeasyPrint). Running headers, page counters,
    # repeating table headers and full Unicode -- none of which the fpdf2
    # path could do. See renderers/html_pdf_renderer.py.
    'pdf': render_html_pdf,
    # The previous imperative renderer, kept one release for side-by-side
    # comparison. Remove once the new path is signed off.
    'pdf_legacy': render_pdf,
    'pptx': render_pptx,
    'xlsx': render_xlsx,
    'raw': render_raw,
}

CONTENT_TYPES = {
    'pdf': 'application/pdf',
    'pdf_legacy': 'application/pdf',
    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}
