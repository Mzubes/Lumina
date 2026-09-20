import base64
from io import BytesIO

import requests
from fpdf import FPDF, XPos, YPos

# fpdf2's core "Helvetica" font only supports latin-1 -- real document text
# (an em-dash in a series label, curly quotes in a disclosure) routinely
# isn't latin-1 and would otherwise crash the export outright. Normalize the
# common cases to their ASCII equivalents, then fall back to dropping
# anything still outside latin-1 so no input text can ever crash a render.
_UNICODE_SUBSTITUTIONS = {
    '—': '-', '–': '-', '‘': "'", '’': "'",
    '“': '"', '”': '"', '…': '...', ' ': ' ', '•': '-',
}

def _pdf_safe(value):
    text = str(value)
    for source, replacement in _UNICODE_SUBSTITUTIONS.items():
        text = text.replace(source, replacement)
    return text.encode('latin-1', errors='replace').decode('latin-1')

def _hex_to_rgb(hex_color, fallback=None):
    if not hex_color or not isinstance(hex_color, str):
        return fallback
    hex_color = hex_color.strip().lstrip('#')
    if len(hex_color) != 6:
        return fallback
    try:
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return fallback

def _tint(rgb, amount=0.85):
    """Lighten an RGB tuple toward white -- used for a table header row's
    fill so it reads as a tinted band rather than the full saturated color."""
    return tuple(round(channel + (255 - channel) * amount) for channel in rgb)

def _fetch_image_bytes(url):
    """Best-effort fetch for an optional logo/photo. A data: URI is decoded
    locally (no network); an http(s) URL is fetched with a short timeout.
    Any failure -- bad URL, timeout, unreadable image -- returns None so a
    broken optional image can never crash an export."""
    if not url or not isinstance(url, str):
        return None
    try:
        if url.startswith('data:'):
            header, _, data = url.partition(',')
            if ';base64' not in header:
                return None
            return BytesIO(base64.b64decode(data))
        if url.startswith('http://') or url.startswith('https://'):
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return BytesIO(response.content)
    except Exception:
        return None
    return None

def _bar_comparison_chart(columns, rows, primary_rgb, accent_rgb):
    """A horizontal two-series bar chart PNG (Strategy vs. Index, etc.) built
    from a data_table's own columns/rows. Returns None -- rendering falls
    back to the table alone -- when the shape doesn't fit a two-series chart
    or matplotlib can't be imported (never let an optional chart block an
    otherwise-valid export)."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    if len(columns) < 3 or not rows:
        return None

    labels, series_a, series_b = [], [], []
    for row in rows:
        if len(row) < 3:
            continue
        try:
            a_value = float(str(row[1]).rstrip('%'))
            b_value = float(str(row[2]).rstrip('%'))
        except (TypeError, ValueError):
            continue
        labels.append(_pdf_safe(row[0]))
        series_a.append(a_value)
        series_b.append(b_value)
    if not labels:
        return None

    primary = tuple(channel / 255 for channel in (primary_rgb or (13, 107, 95)))
    accent = tuple(channel / 255 for channel in (accent_rgb or (201, 189, 154)))

    fig_height = max(1.6, 0.42 * len(labels) + 0.6)
    fig, ax = plt.subplots(figsize=(7.0, fig_height), dpi=150)
    positions = range(len(labels))
    bar_height = 0.34
    ax.barh([p + bar_height / 2 for p in positions], series_a, height=bar_height, color=primary, label=_pdf_safe(columns[1]))
    ax.barh([p - bar_height / 2 for p in positions], series_b, height=bar_height, color=accent, label=_pdf_safe(columns[2]))
    ax.set_yticks(list(positions))
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.legend(loc='lower right', fontsize=7, frameon=False)
    for side in ('top', 'right', 'left'):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis='y', length=0)
    ax.tick_params(axis='x', labelsize=7)
    fig.tight_layout()

    buffer = BytesIO()
    fig.savefig(buffer, format='png', transparent=True)
    plt.close(fig)
    buffer.seek(0)
    return buffer

class _ReportPDF(FPDF):
    """FPDF calls header()/footer() automatically on every add_page(), which
    is what makes the banner and footer repeat on every page -- the plain
    FPDF class used before this only ever drew a one-time title block on
    page 1. header_config/footer_config/theme_config are template-level and
    optional; with none set this renders identically to the pre-engine
    behavior (plain text, no banner fill, no logo)."""

    def __init__(self, header_config, footer_config, theme_config):
        super().__init__()
        self._header_config = header_config or {}
        self._footer_config = footer_config or {}
        self._theme_config = theme_config or {}

    def header(self):
        title = self._header_config.get('title')
        subtitle = self._header_config.get('subtitle')
        if not title and not subtitle:
            return

        primary_rgb = _hex_to_rgb(self._theme_config.get('primary_color'))
        banner_height = 22
        if primary_rgb:
            self.set_fill_color(*primary_rgb)
            self.rect(0, 0, self.w, banner_height, style='F')
            title_rgb, subtitle_rgb = (255, 255, 255), (235, 235, 235)
        else:
            title_rgb, subtitle_rgb = (0, 0, 0), (100, 100, 100)

        text_right_edge = self.w - self.r_margin
        logo_bytes = _fetch_image_bytes(self._theme_config.get('logo_url'))
        if logo_bytes:
            logo_h = banner_height - 8
            try:
                self.image(logo_bytes, x=self.w - self.r_margin - logo_h, y=4, h=logo_h)
                text_right_edge -= logo_h + 6
            except Exception:
                pass

        self.set_xy(self.l_margin, 5)
        if title:
            self.set_font("Helvetica", size=12, style="B")
            self.set_text_color(*title_rgb)
            self.cell(text_right_edge - self.l_margin, 8, _pdf_safe(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if subtitle:
            self.set_x(self.l_margin)
            self.set_font("Helvetica", size=9)
            self.set_text_color(*subtitle_rgb)
            self.cell(text_right_edge - self.l_margin, 6, _pdf_safe(subtitle), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0, 0, 0)

        if primary_rgb:
            self.set_y(banner_height + 6)
        else:
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
    theme_config = content.get('theme_config') or {}
    primary_rgb = _hex_to_rgb(theme_config.get('primary_color'))
    accent_rgb = _hex_to_rgb(theme_config.get('accent_color'))

    pdf = _ReportPDF(header_config, footer_config, theme_config)
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
        if primary_rgb:
            pdf.set_text_color(*primary_rgb)
        pdf.cell(0, 10, _pdf_safe(component['title']), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", size=10)

        if component['type'] == 'text_block':
            pdf.multi_cell(0, 6, _pdf_safe(component.get('text', '')))
        elif component['type'] == 'people_grid':
            for person in component.get('people', []):
                photo_bytes = _fetch_image_bytes(person.get('photo_url'))
                text_x = pdf.l_margin
                if photo_bytes:
                    photo_size = 14
                    try:
                        pdf.image(photo_bytes, x=pdf.l_margin, y=pdf.get_y(), w=photo_size, h=photo_size)
                        text_x = pdf.l_margin + photo_size + 4
                    except Exception:
                        photo_bytes = None
                start_y = pdf.get_y()
                pdf.set_xy(text_x, start_y)
                pdf.set_font("Helvetica", size=10, style="B")
                pdf.cell(0, 6, _pdf_safe(person.get('name', '')), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_x(text_x)
                pdf.set_font("Helvetica", size=9)
                subtitle = ' - '.join(part for part in [person.get('title'), person.get('detail')] if part)
                if subtitle:
                    pdf.cell(0, 6, _pdf_safe(subtitle), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                if photo_bytes:
                    pdf.set_y(max(pdf.get_y(), start_y + 14))
                pdf.ln(1)
        else:
            columns = component.get('columns', [])
            rows = component.get('rows', [])

            if component.get('chart_type') == 'bar_comparison':
                chart = _bar_comparison_chart(columns, rows, primary_rgb, accent_rgb)
                if chart:
                    try:
                        chart_width = pdf.w - pdf.l_margin - pdf.r_margin
                        pdf.image(chart, x=pdf.l_margin, w=chart_width)
                        pdf.ln(3)
                    except Exception:
                        pass

            if columns:
                headings_style = None
                if primary_rgb:
                    from fpdf.fonts import FontFace
                    headings_style = FontFace(fill_color=_tint(primary_rgb), color=(0, 0, 0))
                table_data = [columns] + [[str(cell) for cell in row] for row in rows]
                with pdf.table(headings_style=headings_style) if headings_style else pdf.table() as table:
                    for data_row in table_data:
                        row = table.row()
                        for cell in data_row:
                            row.cell(_pdf_safe(cell))
        pdf.ln(4)

    return bytes(pdf.output())
