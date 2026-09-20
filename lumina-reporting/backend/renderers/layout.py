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

import json

from schema_v2.styling import option_problems, style_problems
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
        # This element came from the flat component list, not from a
        # designed template. The renderer needs to know, because a legacy
        # element's `content` is a whole resolved component (a table with
        # its columns, a chart) while a v2 element's is one binding's
        # value. `binding_kind` cannot carry that: a v2 element holding
        # static words is unbound too, and used to fall down the legacy
        # branch and render as nothing.
        'legacy': True,
        'static_text': None,
        'binding_key': None,
        'dataset_field_id': None,
        'display_spec_id': None,
        'options': None,
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
        'iterate_display_spec_id': None,
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
            'iterate_display_spec_id': section.iterate_display_spec_id,
            'elements': [
                {
                    'element_type': element.element_type,
                    'x_mm': float(element.x_mm), 'y_mm': float(element.y_mm),
                    'w_mm': float(element.w_mm), 'h_mm': float(element.h_mm),
                    'z_index': element.z_index,
                    'binding_kind': element.binding_kind,
                    'style_token': element.style_token,
                    # What the binding names. Carried even when unused by
                    # this element's kind, because the resolver indexes
                    # them and a tree missing one fails mid-render.
                    'dataset_field_id': element.dataset_field_id,
                    'display_spec_id': element.display_spec_id,
                    'binding_key': element.binding_key,
                    'static_text': element.static_text,
                    'options': json.loads(element.options) if element.options else None,
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
            where = f"section {section['ordinal']}"
            problems.extend(style_problems(element.get('style_token'), where))
            problems.extend(option_problems(element.get('options'), where))

    for index, section in enumerate(tree):
        if section.get('repeat_mode', 'none') == 'none':
            continue
        if index not in (0, len(tree) - 1):
            problems.append(
                f"section {section['ordinal']}: a repeating band must be the first "
                f"section (a page header) or the last (a page footer); one in the "
                f"middle of the flow has no page position to take")
    return problems


# Where a repeating band sits on the page. The schema says a band repeats;
# it does not say where, because a band's place is its ordinal in the flow.
# The only reading that survives is: the first band is the page header, the
# last is the page footer. A repeating band in the middle has no page
# position to take, and `validate()` rejects it rather than guessing.
PIN_TOP, PIN_BOTTOM = 'top', 'bottom'

# Which @page margin box a page number lands in, by where the author put
# it across the band.
_MARGIN_BOXES = {
    (PIN_TOP, 'left'): '@top-left', (PIN_TOP, 'center'): '@top-center',
    (PIN_TOP, 'right'): '@top-right',
    (PIN_BOTTOM, 'left'): '@bottom-left', (PIN_BOTTOM, 'center'): '@bottom-center',
    (PIN_BOTTOM, 'right'): '@bottom-right',
}


def _third(element, width_mm):
    centre = float(element['x_mm']) + float(element['w_mm']) / 2
    if centre < width_mm / 3:
        return 'left'
    return 'right' if centre > width_mm * 2 / 3 else 'center'


def pin_repeating_bands(tree, width_mm=DEFAULT_CONTENT_WIDTH_MM):
    """Resolve repeat_mode into a page position, and lift out the page
    numbers that cannot live in a repeating band.

    Returns (tree, margin_boxes, reserved). `reserved` is how much room
    the flow content has to leave at the top and bottom: a pinned band is
    out of flow, so without it the body starts at the top of the page and
    the band lands on top of the first table -- which is exactly what the
    first render did.

    A repeating band is drawn once and
    replicated by the engine, so a page counter inside one FREEZES --
    measured: every page of a seven-page document read "p 1 of 7". A
    `page_number` element in such a band is therefore moved into the @page
    margin box nearest where it was authored, which is the only place the
    counter resolves per page. The band keeps everything else.
    """
    out, margin_boxes = [], {}
    reserved = {'top': 0.0, 'bottom': 0.0}
    repeating = [index for index, section in enumerate(tree)
                 if section.get('repeat_mode', 'none') != 'none']

    for index, section in enumerate(tree):
        if index not in repeating:
            out.append(section)
            continue

        pin = PIN_TOP if index == 0 else PIN_BOTTOM if index == len(tree) - 1 else None
        kept = []
        for element in section['elements']:
            if element['element_type'] == 'page_number' and pin:
                margin_boxes[_MARGIN_BOXES[(pin, _third(element, width_mm))]] = {
                    'style_token': element.get('style_token'),
                }
                continue
            kept.append(element)
        if pin:
            reserved[pin] += float(section.get('height_mm') or 0)
        out.append({**section, 'pin': pin, 'elements': kept})
    return out, margin_boxes, reserved
