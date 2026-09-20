"""The layout tree every renderer draws from.

Phase D's model (`schema_v2/templates.py`) describes a document as sections
containing anchored elements. Today's `ReportTemplate` describes it as a
flat list of components that stack. This module is the one place that knows
both, so nothing downstream has to.

    components  ->  layout_from_components()  ->  sections/elements
    v2 template ->  layout_from_template()    ->  sections/elements

The renderer reads the tree and nothing else. That is what makes the
cutover safe: the legacy path produces a tree that renders byte-identically
to what it produced before, so the two models can be compared on real
documents rather than on assertions about them.

**The tree is plain data**, the same shape the ORM rows carry -- dicts, not
model instances -- so a render needs no database and a unit test needs no
fixtures.
"""

from schema_v2.templates import ELEMENT_TYPES, LAYOUT_MODES

# A4 portrait at the default margins. The legacy path has no template row to
# read a page size from, so it uses the same geometry the Phase A stylesheet
# hard-coded.
DEFAULT_CONTENT_WIDTH_MM = 178

# The component types that are NOT tabular. Everything else is decided by
# shape, not by name.
#
# A type-keyed table was the first attempt and it was wrong: the resolver
# emits `holdings_table` and `performance_summary` too, and both quietly
# became empty bands -- real content missing from a client document. The
# old template never had that bug because it dispatched on whether the
# component had columns, so a tabular type it had never heard of still
# rendered. That property is worth keeping.
_NON_TABULAR = {
    'text_block': ('text',),
    'people_grid': ('people_grid',),
}


def _element_types(component):
    """Which elements a legacy component becomes."""
    named = _NON_TABULAR.get(component.get('type'))
    if named is not None:
        return named
    # Anything with columns is a table, whatever it calls itself.
    if component.get('columns'):
        return ('table',)
    return ()


def _element(element_type, component, width_mm, **extra):
    element = {
        'element_type': element_type,
        # Everything in the legacy path is full-width and stacked, so it
        # anchors at the section's origin. A designed template sets these
        # from the canvas instead.
        'x_mm': 0, 'y_mm': 0, 'w_mm': width_mm, 'h_mm': None,
        'z_index': 0,
        'binding_kind': 'none',
        'style_token': None,
        # The resolved values this element draws. In v2 these arrive through
        # a binding; during cutover they arrive already resolved on the
        # component, and the renderer cannot tell the difference.
        'content': component,
    }
    element.update(extra)
    return element


def _section(ordinal, elements, title=None):
    return {
        'ordinal': ordinal,
        'name': title,
        'layout_mode': 'flow',
        'height_mm': None,
        'repeat_mode': 'none',
        'break_before': 'auto',
        'break_after': 'auto',
        'elements': elements,
    }


def layout_from_components(components, width_mm=DEFAULT_CONTENT_WIDTH_MM):
    """Today's flat component list as a section tree.

    One section per component, because that is exactly what the flat list
    means: each component owns a band, and the bands stack. The section
    keeps the component's title so a heading still belongs to its content
    rather than floating between two of them.
    """
    sections = []
    for ordinal, component in enumerate(components or []):
        # A component that is neither a known non-tabular type nor shaped
        # like a table yields a band with nothing in it. The renderer says
        # so on the page; guessing would put a blank box in a client
        # document instead.
        elements = [
            _element(element_type, component, width_mm)
            for element_type in _element_types(component)
        ]
        # A table that also charts its rows is two elements in one band --
        # the same band, so a page break can never separate them.
        if component.get('chart'):
            elements.append(_element('chart', component, width_mm, z_index=1))
        sections.append(_section(ordinal, elements, component.get('title')))
    return sections


def layout_from_template(template, sections, elements):
    """A v2 DocumentTemplate's rows as the same tree.

    Takes already-loaded rows rather than a session, so the renderer never
    issues a query mid-render -- a half-rendered document that fails on a
    lazy load is the worst possible failure mode for this path.
    """
    by_section = {}
    for element in elements:
        by_section.setdefault(element.section_id, []).append(element)

    tree = []
    for section in sorted(sections, key=lambda row: row.ordinal):
        drawn = sorted(by_section.get(section.id, []),
                       key=lambda row: (row.z_index, row.id))
        tree.append({
            'ordinal': section.ordinal,
            'name': section.name,
            'layout_mode': section.layout_mode,
            'height_mm': float(section.height_mm) if section.height_mm is not None else None,
            'repeat_mode': section.repeat_mode,
            'break_before': section.break_before,
            'break_after': section.break_after,
            'elements': [
                {
                    'element_type': element.element_type,
                    'x_mm': float(element.x_mm), 'y_mm': float(element.y_mm),
                    'w_mm': float(element.w_mm), 'h_mm': float(element.h_mm),
                    'z_index': element.z_index,
                    'binding_kind': element.binding_kind,
                    'style_token': element.style_token,
                    # Filled by the resolver, not here: this module maps
                    # structure, never data.
                    'content': None,
                }
                for element in drawn if element.is_visible
            ],
        })
    return tree


def validate(tree):
    """Structural check, for a tree built in code rather than read from the
    database. Returns a list of problems, empty when sound."""
    problems = []
    for section in tree:
        if section['layout_mode'] not in LAYOUT_MODES:
            problems.append(f"section {section['ordinal']}: unknown layout mode "
                            f"{section['layout_mode']!r}")
        if (section['layout_mode'] == 'fixed') != (section['height_mm'] is not None):
            problems.append(f"section {section['ordinal']}: a fixed band declares a "
                            f"height and a flow band does not")
        for element in section['elements']:
            if element['element_type'] not in ELEMENT_TYPES:
                problems.append(f"section {section['ordinal']}: unknown element type "
                                f"{element['element_type']!r}")
            token = element.get('style_token')
            if token and (':' in token or ';' in token):
                problems.append(f"section {section['ordinal']}: style_token {token!r} "
                                f"is a CSS declaration, not a brand-kit token")
    return problems
