from fpdf import FPDF, XPos, YPos

def render_pdf(content):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", size=16, style="B")
    pdf.cell(0, 12, content['report_title'], new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 8, f"Client: {content.get('client_name') or ''}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 8, f"Generated: {content.get('generated_at') or ''}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    for component in content['components']:
        pdf.set_font("Helvetica", size=13, style="B")
        pdf.cell(0, 10, component['title'], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", size=10)

        if component['type'] == 'text_block':
            pdf.multi_cell(0, 6, component.get('text', ''))
        else:
            columns = component.get('columns', [])
            rows = component.get('rows', [])
            if columns:
                table_data = [columns] + [[str(cell) for cell in row] for row in rows]
                with pdf.table() as table:
                    for data_row in table_data:
                        row = table.row()
                        for cell in data_row:
                            row.cell(str(cell))
        pdf.ln(4)

    return bytes(pdf.output())
