from fpdf import FPDF, XPos, YPos

# fpdf2's core "Helvetica" font only supports latin-1 -- real document text
# (an em-dash in a series label, curly quotes in a disclosure) routinely
# isn't latin-1 and would otherwise crash the export outright. Normalize the
# common cases to their ASCII equivalents, then fall back to dropping
# anything still outside latin-1 so no input text can ever crash a render.
_UNICODE_SUBSTITUTIONS = {
    '—': '-', '–': '-', '‘': "'", '’': "'",
    '“': '"', '”': '"', '…': '...', ' ': ' ', '•': '-',
}

def _pdf_safe(value):
    text = str(value)
    for source, replacement in _UNICODE_SUBSTITUTIONS.items():
        text = text.replace(source, replacement)
    return text.encode('latin-1', errors='replace').decode('latin-1')

class _ReportPDF(FPDF):
    """FPDF calls header()/footer() automatically on every add_page(), which
    is what makes the banner and footer repeat on every page -- the plain
    FPDF class used before this only ever drew a one-time title block on
    page 1. header_config/footer_config are template-level and optional;
    with neither set this renders identically to the pre-engine behavior."""

    def __init__(self, header_config, footer_config):
        super().__init__()
        self._header_config = header_config or {}
        self._footer_config = footer_config or {}

    def header(self):
        title = self._header_config.get('title')
        subtitle = self._header_config.get('subtitle')
        if not title and not subtitle:
            return
        if title:
            self.set_font("Helvetica", size=12, style="B")
            self.cell(0, 8, _pdf_safe(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if subtitle:
            self.set_font("Helvetica", size=9)
            self.set_text_color(100, 100, 100)
            self.cell(0, 6, _pdf_safe(subtitle), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_text_color(0, 0, 0)
        self.set_draw_color(200, 200, 200)
        self.line(self.l_margin, self.get_y() + 2, self.w - self.r_margin, self.get_y() + 2)
        self.ln(8)

    def footer(self):
        text = self._footer_config.get('text')
        if not text:
            return
        self.set_y(-18)
        self.set_draw_color(200, 200, 200)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.set_font("Helvetica", size=7)
        self.set_text_color(120, 120, 120)
        self.set_y(-15)
        self.cell(0, 5, _pdf_safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Helvetica", size=7)
        self.cell(0, 5, f"Page {self.page_no()}", align="R")
        self.set_text_color(0, 0, 0)

def render_pdf(content):
    header_config = content.get('header_config') or {}
    footer_config = content.get('footer_config') or {}
    pdf = _ReportPDF(header_config, footer_config)
    pdf.set_auto_page_break(auto=True, margin=22 if footer_config.get('text') else 15)
    pdf.add_page()

    if not header_config.get('title') and not header_config.get('subtitle'):
        # No template-level header configured -- keep the original one-time
        # title/client/generated-at block so existing templates render
        # exactly as they did before this engine existed.
        pdf.set_font("Helvetica", size=16, style="B")
        pdf.cell(0, 12, _pdf_safe(content['report_title']), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        pdf.set_font("Helvetica", size=10)
        pdf.cell(0, 8, _pdf_safe(f"Client: {content.get('client_name') or ''}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.cell(0, 8, _pdf_safe(f"Generated: {content.get('generated_at') or ''}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)

    for component in content['components']:
        pdf.set_font("Helvetica", size=13, style="B")
        pdf.cell(0, 10, _pdf_safe(component['title']), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", size=10)

        if component['type'] == 'text_block':
            pdf.multi_cell(0, 6, _pdf_safe(component.get('text', '')))
        elif component['type'] == 'people_grid':
            for person in component.get('people', []):
                pdf.set_font("Helvetica", size=10, style="B")
                pdf.cell(0, 6, _pdf_safe(person.get('name', '')), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_font("Helvetica", size=9)
                subtitle = ' - '.join(part for part in [person.get('title'), person.get('detail')] if part)
                if subtitle:
                    pdf.cell(0, 6, _pdf_safe(subtitle), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(1)
        else:
            columns = component.get('columns', [])
            rows = component.get('rows', [])
            if columns:
                table_data = [columns] + [[str(cell) for cell in row] for row in rows]
                with pdf.table() as table:
                    for data_row in table_data:
                        row = table.row()
                        for cell in data_row:
                            row.cell(_pdf_safe(cell))
        pdf.ln(4)

    return bytes(pdf.output())
