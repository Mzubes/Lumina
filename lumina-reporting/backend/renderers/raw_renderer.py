import csv
import io
import json

def render_raw(content, raw_format='json'):
    if raw_format == 'csv':
        return _render_csv(content)
    return json.dumps(content, default=str).encode('utf-8')

def _render_csv(content):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['Report', content['report_title']])
    writer.writerow(['Client', content.get('client_name') or ''])
    writer.writerow(['Generated', content.get('generated_at') or ''])
    writer.writerow([])

    for component in content['components']:
        writer.writerow([f"# {component['title']}"])
        if component['type'] == 'text_block':
            writer.writerow([component.get('text', '')])
        else:
            writer.writerow(component.get('columns', []))
            for row in component.get('rows', []):
                writer.writerow(row)
        writer.writerow([])

    return buffer.getvalue().encode('utf-8')
