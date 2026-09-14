COMPONENT_TYPES = {'holdings_table', 'performance_summary', 'text_block'}

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

    return None
