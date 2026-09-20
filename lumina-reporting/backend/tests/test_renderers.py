import csv
import io
import json
import zipfile

import pytest

from renderers import RENDERERS

SAMPLE_CONTENT = {
    'report_title': 'Q2 Report',
    'client_name': 'Acme Institutional',
    'generated_at': '2026-06-30T00:00:00',
    'components': [
        {'type': 'holdings_table', 'title': 'Portfolio Holdings',
         'columns': ['Security', 'Asset Class', 'Quantity', 'Market Value', 'Weight %'],
         'rows': [['Apple Inc.', 'Equity', 100.0, 17500.0, 12.5]]},
        {'type': 'performance_summary', 'title': 'Performance',
         'columns': ['Period', 'Return %', 'Benchmark %'],
         'rows': [['QTD', 3.25, 2.9]]},
        {'type': 'text_block', 'title': 'Commentary', 'text': 'Markets were steady this quarter.'},
    ],
}

def test_render_pdf_produces_valid_pdf_bytes():
    pdf_bytes = RENDERERS['pdf'](SAMPLE_CONTENT)
    assert pdf_bytes[:4] == b'%PDF'
    assert len(pdf_bytes) > 100

def test_render_pptx_produces_valid_zip():
    pptx_bytes = RENDERERS['pptx'](SAMPLE_CONTENT)
    assert pptx_bytes[:2] == b'PK'
    with zipfile.ZipFile(io.BytesIO(pptx_bytes)) as archive:
        names = archive.namelist()
        assert any(name.startswith('ppt/slides/slide') for name in names)
        # title slide + one slide per component
        slide_count = len([n for n in names if n.startswith('ppt/slides/slide') and n.endswith('.xml')])
        assert slide_count == 1 + len(SAMPLE_CONTENT['components'])

def test_render_xlsx_produces_valid_zip_with_sheets():
    xlsx_bytes = RENDERERS['xlsx'](SAMPLE_CONTENT)
    assert xlsx_bytes[:2] == b'PK'
    with zipfile.ZipFile(io.BytesIO(xlsx_bytes)) as archive:
        assert 'xl/workbook.xml' in archive.namelist()

def test_render_raw_json_round_trips():
    raw_bytes = RENDERERS['raw'](SAMPLE_CONTENT, raw_format='json')
    parsed = json.loads(raw_bytes)
    assert parsed['report_title'] == 'Q2 Report'
    assert len(parsed['components']) == 3

def test_render_raw_csv_has_sections_per_component():
    raw_bytes = RENDERERS['raw'](SAMPLE_CONTENT, raw_format='csv')
    text = raw_bytes.decode('utf-8')
    rows = list(csv.reader(io.StringIO(text)))
    section_headers = [row[0] for row in rows if row and row[0].startswith('# ')]
    assert section_headers == ['# Portfolio Holdings', '# Performance', '# Commentary']
    assert ['Apple Inc.', 'Equity', '100.0', '17500.0', '12.5'] in rows
