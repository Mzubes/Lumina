from fpdf import FPDF, XPos, YPos
from pathlib import Path

def generate_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(200, 10, text="Fund Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    for key, value in data.items():
        pdf.cell(200, 10, text=f"{key}: {value}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    reports_directory = Path(__file__).resolve().parent / 'static' / 'reports'
    reports_directory.mkdir(parents=True, exist_ok=True)
    filename = reports_directory / f"report_{data.get('fund_id', 'default')}.pdf"
    pdf.output(str(filename))
    return f"/static/reports/{filename.name}"
