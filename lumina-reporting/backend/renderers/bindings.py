"""Filling a v2 template's layout tree with data.

`layout_from_template()` produces structure with every element's `content`
set to None. This module fills it, which is the step that makes a
DocumentTemplate render. The legacy path skips it entirely -- its content
arrives already resolved on the component -- so the two models meet at the
same tree and the renderer cannot tell them apart.

**Page numbers are not resolved here.** `page_number` and `page_count` are
only known once the engine has laid the document out, so this marks them
and the renderer emits a CSS counter. Resolving them in Python would mean
guessing the page count before pagination, which is the bug that makes a
document say "Page 1 of 1" on every page of seven.
"""

from display_spec import apply_spec

# System values that exist before layout. The other two in the schema's
# SYSTEM_BINDINGS -- page_number, page_count -- deliberately do not.
LAYOUT_TIME_BINDINGS = ('page_number', 'page_count')


class MissingBinding(KeyError):
    """A binding that names something the context does not carry.

    Raised rather than rendered blank: a factsheet with a silently empty
    "as at" date is worse than one that fails to build.
    """


def _resolve_element(element, context, row=None):
    kind = element['binding_kind']
    if kind == 'none':
        return element.get('content')

    if kind == 'system':
        key = element['binding_key']
        if key in LAYOUT_TIME_BINDINGS:
            # The renderer turns this into counter(page) / counter(pages).
            return {'layout_time': key}
        values = context.get('system') or {}
        if key not in values:
            raise MissingBinding(f'system binding {key!r} is not in the render context')
        return {'value': values[key]}

    if kind == 'dataset_field':
        field_id = element['dataset_field_id']
        # Inside an iterating band the current row wins: that is what makes
        # "one card per holding" carry each holding's own values.
        if row is not None and field_id in row:
            return {'value': row[field_id]}
        values = context.get('fields') or {}
        if field_id not in values:
            raise MissingBinding(f'dataset field {field_id} is not in the render context')
        return {'value': values[field_id]}

    if kind == 'display_spec':
        spec_id = element['display_spec_id']
        source = (context.get('datasets') or {}).get(spec_id)
        if source is None:
            raise MissingBinding(f'display spec {spec_id} is not in the render context')
        return apply_spec(source.get('rows'), source.get('spec'),
                          source.get('fields'), source.get('columns'))

    raise MissingBinding(f'unknown binding kind {element["binding_kind"]!r}')


def resolve_tree(tree, context):
    """A tree with every element's content filled.

    A band bound to a display spec is expanded here rather than at render
    time -- N rows become N bands, so the renderer only ever sees a flat
    list of bands and never has to know about iteration.
    """
    resolved = []
    for section in tree:
        spec_id = section.get('iterate_display_spec_id')
        if spec_id is None:
            resolved.append({**section, 'elements': [
                {**element, 'content': _resolve_element(element, context)}
                for element in section['elements']
            ]})
            continue

        source = (context.get('datasets') or {}).get(spec_id)
        if source is None:
            raise MissingBinding(f'display spec {spec_id} drives a repeating band '
                                 f'but is not in the render context')
        result = apply_spec(source.get('rows'), source.get('spec'),
                            source.get('fields'), source.get('columns'))
        for index, row in enumerate(result['rows']):
            resolved.append({**section, 'iteration': index, 'elements': [
                {**element, 'content': _resolve_element(element, context, row)}
                for element in section['elements']
            ]})
    return resolved
