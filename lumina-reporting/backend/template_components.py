COMPONENT_TYPES = {
    'holdings_table', 'performance_summary', 'text_block', 'report_reference',
    'data_table', 'people_grid',
}

def validate_components(components):
    if not isinstance(components, list) or not components:
        return 'components must be a non-empty list'

    seen_ids = set()
    for component in components:
        if not isinstance(component, dict):
            return 'each component must be an object'

        comp_id = component.get('id')
        comp_type = component.get('type')
        title = component.get('title')
        data_binding = component.get('data_binding')

        if not comp_id or comp_id in seen_ids:
            return 'each component needs a unique id'
        seen_ids.add(comp_id)

        if comp_type not in COMPONENT_TYPES:
            return f"invalid component type '{comp_type}'"
        if not title:
            return 'each component needs a title'
        if not isinstance(data_binding, dict):
            return 'each component needs a data_binding object'
        if comp_type == 'text_block' and not data_binding.get('static_text'):
            return 'text_block components need data_binding.static_text'
        if comp_type == 'report_reference' and not isinstance(data_binding.get('report_id'), int):
            return 'report_reference components need an integer data_binding.report_id'
        if comp_type == 'data_table':
            columns = data_binding.get('columns')
            rows = data_binding.get('rows')
            if not isinstance(columns, list) or not columns:
                return 'data_table components need a non-empty data_binding.columns list'
            if not isinstance(rows, list):
                return 'data_table components need a data_binding.rows list'
            if any(not isinstance(row, list) or len(row) != len(columns) for row in rows):
                return 'each data_table row must have one value per column'
        if comp_type == 'people_grid':
            people = data_binding.get('rows')
            if not isinstance(people, list) or not people:
                return 'people_grid components need a non-empty data_binding.rows list'
            if any(not isinstance(person, dict) or not person.get('name') for person in people):
                return 'each people_grid row needs at least a name'

    return None
