from renderers.pdf_renderer import render_pdf
from renderers.pptx_renderer import render_pptx
from renderers.raw_renderer import render_raw
from renderers.xlsx_renderer import render_xlsx

RENDERERS = {
    'pdf': render_pdf,
    'pptx': render_pptx,
    'xlsx': render_xlsx,
    'raw': render_raw,
}

CONTENT_TYPES = {
    'pdf': 'application/pdf',
    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}
