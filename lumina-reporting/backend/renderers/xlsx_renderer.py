from io import BytesIO

from openpyxl import Workbook

def _safe_sheet_name(title, used_names):
    name = (title or 'Sheet')[:31]
    original = name
    counter = 1
    while name in used_names:
        suffix = f" ({counter})"
        name = original[:31 - len(suffix)] + suffix
        counter += 1
    used_names.add(name)
    return name

def render_xlsx(content):
    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = 'Summary'
    summary_sheet.append(['Report', content['report_title']])
    summary_sheet.append(['Client', content.get('client_name') or ''])
    summary_sheet.append(['Generated', content.get('generated_at') or ''])
    summary_sheet.append([])

    used_names = {'Summary'}
    for component in content['components']:
        if component['type'] == 'text_block':
            summary_sheet.append([component['title']])
            summary_sheet.append([component.get('text', '')])
            summary_sheet.append([])
        elif component['type'] == 'people_grid':
            summary_sheet.append([component['title']])
            for person in component.get('people', []):
                subtitle = ' · '.join(part for part in [person.get('title'), person.get('detail')] if part)
                summary_sheet.append([person.get('name', ''), subtitle])
            summary_sheet.append([])
        else:
            sheet = workbook.create_sheet(_safe_sheet_name(component['title'], used_names))
            sheet.append(component.get('columns', []))
            for row in component.get('rows', []):
                sheet.append(row)

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
