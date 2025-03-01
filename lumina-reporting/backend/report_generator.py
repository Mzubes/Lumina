from fpdf import FPDF

def generate_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Fund Report", ln=True, align="C")
    for key, value in data.items():
        pdf.cell(200, 10, txt=f"{key}: {value}", ln=True)
    filename = f"static/reports/report_{data.get('fund_id', 'default')}.pdf"
    pdf.output(filename)
    return filename
