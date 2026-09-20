"""The template API: what the canvas loads and saves.

A template is a tree — one row for the template, one per band, one per
element — and the canvas edits all three levels at once. So the write
endpoint takes the whole tree and replaces it, rather than offering
per-element CRUD that would make one drag into three round trips and leave
the canvas responsible for keeping an id map in sync.

**The same validator the renderer uses.** A tree is checked by
`renderers.layout.validate` before anything is written, so the API refuses
exactly the trees the renderer would refuse. Storing a template that
cannot be drawn just moves the failure to whoever opens the PDF.
"""

import json

from flask import Blueprint, g, jsonify, request
from sqlalchemy import select

from database import db_session
from renderers.layout import validate
from routes.auth import require_auth
from schema_v2 import DocumentTemplate, Firm, TemplateElement, TemplateSection
from schema_v2.templates import (BINDING_KINDS, BREAK_RULES, ELEMENT_TYPES,
                                 LAYOUT_MODES, ORIENTATIONS, PAGE_SIZES,
                                 REPEAT_MODES, SYSTEM_BINDINGS)

document_templates_blueprint = Blueprint('document_templates', __name__)

# v2 requires a tenant on every row; models.py has no tenant concept yet.
# Until the multi-tenant core lands, every template belongs to this one
# firm — which is honest about the state of things and keeps firm_id
# NOT NULL rather than making it nullable and then having to tighten it.
DEFAULT_FIRM_CODE = 'default'


def _firm_id():
    firm = db_session.execute(
        select(Firm).where(Firm.code == DEFAULT_FIRM_CODE)).scalar_one_or_none()
    if firm is None:
        firm = Firm(name='Default Firm', code=DEFAULT_FIRM_CODE)
        db_session.add(firm)
        db_session.flush()
    return firm.id


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _element_json(element):
    return {
        'id': element.id,
        'element_type': element.element_type,
        'x_mm': float(element.x_mm), 'y_mm': float(element.y_mm),
        'w_mm': float(element.w_mm), 'h_mm': float(element.h_mm),
        'z_index': element.z_index,
        'binding_kind': element.binding_kind,
        'dataset_field_id': element.dataset_field_id,
        'display_spec_id': element.display_spec_id,
        'binding_key': element.binding_key,
        'static_text': element.static_text,
        'style_token': element.style_token,
        'options': json.loads(element.options) if element.options else None,
        'is_visible': bool(element.is_visible),
    }


def _section_json(section, elements):
    return {
        'id': section.id,
        'ordinal': section.ordinal,
        'name': section.name,
        'layout_mode': section.layout_mode,
        'height_mm': float(section.height_mm) if section.height_mm is not None else None,
        'repeat_mode': section.repeat_mode,
        'break_before': section.break_before,
        'break_after': section.break_after,
        'iterate_display_spec_id': section.iterate_display_spec_id,
        'elements': [_element_json(element) for element in elements],
    }


def _template_json(template, sections=None):
    payload = {
        'id': template.id,
        'name': template.name,
        'code': template.code,
        'description': template.description,
        'version': template.version,
        'is_published': bool(template.is_published),
        'brand_kit_id': template.brand_kit_id,
        'page': {
            'size': template.page_size,
            'orientation': template.orientation,
            'margins': {
                'top': float(template.margin_top_mm),
                'bottom': float(template.margin_bottom_mm),
                'left': float(template.margin_left_mm),
                'right': float(template.margin_right_mm),
            },
        },
    }
    if sections is not None:
        payload['sections'] = sections
    return payload


def _load_tree(template):
    sections = db_session.execute(
        select(TemplateSection)
        .where(TemplateSection.template_id == template.id)
        .order_by(TemplateSection.ordinal)).scalars().all()
    elements = db_session.execute(
        select(TemplateElement)
        .where(TemplateElement.section_id.in_([s.id for s in sections] or [-1]))
        .order_by(TemplateElement.z_index, TemplateElement.id)).scalars().all()
    by_section = {}
    for element in elements:
        by_section.setdefault(element.section_id, []).append(element)
    return [_section_json(section, by_section.get(section.id, [])) for section in sections]


def _validation_error(payload):
    """Everything wrong with a submitted tree, as one message.

    Reported together rather than one at a time: an author who fixed three
    problems and got a fourth rejection would reasonably conclude the API
    was guessing.
    """
    problems = []
    page = payload.get('page') or {}
    if page.get('size') and page['size'] not in PAGE_SIZES:
        problems.append(f"unknown page size {page['size']!r}")
    if page.get('orientation') and page['orientation'] not in ORIENTATIONS:
        problems.append(f"unknown orientation {page['orientation']!r}")

    for index, section in enumerate(payload.get('sections') or []):
        where = f"section {section.get('ordinal', index)}"
        if section.get('layout_mode') not in LAYOUT_MODES:
            problems.append(f"{where}: unknown layout mode {section.get('layout_mode')!r}")
        if section.get('repeat_mode', 'none') not in REPEAT_MODES:
            problems.append(f"{where}: unknown repeat mode {section.get('repeat_mode')!r}")
        for rule in ('break_before', 'break_after'):
            if section.get(rule, 'auto') not in BREAK_RULES:
                problems.append(f"{where}: unknown {rule} {section.get(rule)!r}")
        for element in section.get('elements') or []:
            if element.get('element_type') not in ELEMENT_TYPES:
                problems.append(f"{where}: unknown element type {element.get('element_type')!r}")
            if element.get('binding_kind', 'none') not in BINDING_KINDS:
                problems.append(f"{where}: unknown binding kind {element.get('binding_kind')!r}")
            key = element.get('binding_key')
            if key and key not in SYSTEM_BINDINGS:
                problems.append(f"{where}: unknown system binding {key!r}")
            token = element.get('style_token')
            if token and (':' in token or ';' in token):
                problems.append(f"{where}: style_token {token!r} is a CSS declaration, "
                                f"not a brand-kit token")

    # The renderer's own check, on the same shape it will later draw.
    # `validate` indexes the keys it needs rather than getting them, so the
    # submitted dicts are filled in first: a missing `element_type` is a
    # validation failure to report, not a KeyError to hand back as a 500.
    problems.extend(validate([
        {
            'ordinal': section.get('ordinal', index),
            'layout_mode': section.get('layout_mode'),
            'height_mm': section.get('height_mm'),
            'repeat_mode': section.get('repeat_mode', 'none'),
            'elements': [
                {**element, 'element_type': element.get('element_type')}
                for element in (section.get('elements') or [])
            ],
        }
        for index, section in enumerate(payload.get('sections') or [])
    ]))
    return '; '.join(dict.fromkeys(problems)) or None


@document_templates_blueprint.get('/api/document-templates')
@require_auth(roles=['admin', 'editor', 'viewer'])
def list_templates():
    templates = db_session.execute(
        select(DocumentTemplate)
        .where(DocumentTemplate.is_active == 1)
        .order_by(DocumentTemplate.name)).scalars().all()
    return jsonify([_template_json(template) for template in templates])


@document_templates_blueprint.get('/api/document-templates/<int:template_id>')
@require_auth(roles=['admin', 'editor', 'viewer'])
def get_template(template_id):
    template = db_session.get(DocumentTemplate, template_id)
    if template is None or not template.is_active:
        return jsonify({'message': 'Template not found'}), 404
    return jsonify(_template_json(template, _load_tree(template)))


@document_templates_blueprint.post('/api/document-templates')
@require_auth(roles=['admin', 'editor'])
def create_template():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    code = (data.get('code') or '').strip()
    if not name or not code:
        return jsonify({'message': 'name and code are required'}), 400

    error = _validation_error(data)
    if error:
        return jsonify({'message': error}), 400

    page = data.get('page') or {}
    margins = page.get('margins') or {}
    template = DocumentTemplate(
        firm_id=_firm_id(), name=name, code=code,
        description=data.get('description'),
        page_size=page.get('size', 'a4'),
        orientation=page.get('orientation', 'portrait'),
        margin_top_mm=_number(margins.get('top'), 26),
        margin_bottom_mm=_number(margins.get('bottom'), 20),
        margin_left_mm=_number(margins.get('left'), 16),
        margin_right_mm=_number(margins.get('right'), 16),
    )
    db_session.add(template)
    db_session.flush()
    _write_tree(template, data.get('sections') or [])
    db_session.commit()
    return jsonify(_template_json(template, _load_tree(template))), 201


def _write_tree(template, sections):
    """Replace a template's bands and elements.

    Wholesale rather than a diff: the canvas holds the authoritative tree
    and sends it entire, and reconciling ids would add a failure mode
    (a stale id, a half-applied edit) for no behaviour the author can see.
    Row ids are therefore not stable across a save, which the response
    makes plain by returning the tree that was written.
    """
    existing = db_session.execute(
        select(TemplateSection).where(TemplateSection.template_id == template.id)
    ).scalars().all()
    if existing:
        # Deleted through the session rather than with a core DELETE. A
        # core delete leaves the removed rows in the identity map, and
        # SQLite hands their primary keys straight back to the sections
        # written below -- so the flush would find a stale object already
        # sitting under a live id. Trees are small; one statement per row
        # is the right trade for not having a resurrection bug.
        for section in existing:
            for element in db_session.execute(
                    select(TemplateElement).where(
                        TemplateElement.section_id == section.id)).scalars().all():
                db_session.delete(element)
            db_session.delete(section)
        db_session.flush()

    for ordinal, payload in enumerate(sections):
        section = TemplateSection(
            firm_id=template.firm_id, template_id=template.id,
            ordinal=payload.get('ordinal', ordinal),
            name=payload.get('name'),
            layout_mode=payload.get('layout_mode', 'flow'),
            height_mm=payload.get('height_mm'),
            repeat_mode=payload.get('repeat_mode', 'none'),
            break_before=payload.get('break_before', 'auto'),
            break_after=payload.get('break_after', 'auto'),
            iterate_display_spec_id=payload.get('iterate_display_spec_id'),
        )
        db_session.add(section)
        db_session.flush()
        for element in payload.get('elements') or []:
            options = element.get('options')
            db_session.add(TemplateElement(
                firm_id=template.firm_id, section_id=section.id,
                element_type=element.get('element_type', 'text'),
                x_mm=_number(element.get('x_mm')), y_mm=_number(element.get('y_mm')),
                w_mm=_number(element.get('w_mm'), 10), h_mm=_number(element.get('h_mm'), 10),
                z_index=int(element.get('z_index') or 0),
                binding_kind=element.get('binding_kind', 'none'),
                dataset_field_id=element.get('dataset_field_id'),
                display_spec_id=element.get('display_spec_id'),
                binding_key=element.get('binding_key'),
                static_text=element.get('static_text'),
                style_token=element.get('style_token'),
                options=json.dumps(options) if options else None,
                is_visible=1 if element.get('is_visible', True) else 0,
            ))


@document_templates_blueprint.put('/api/document-templates/<int:template_id>')
@require_auth(roles=['admin', 'editor'])
def save_template(template_id):
    template = db_session.get(DocumentTemplate, template_id)
    if template is None or not template.is_active:
        return jsonify({'message': 'Template not found'}), 404
    if template.is_published:
        # A published template is immutable; an edit makes a new version,
        # so a pack can record which version rendered it.
        return jsonify({'message': 'This template is published. Create a new version to edit it.'}), 409

    data = request.get_json(silent=True) or {}
    error = _validation_error(data)
    if error:
        return jsonify({'message': error}), 400

    if data.get('name'):
        template.name = data['name'].strip()
    template.description = data.get('description', template.description)
    page = data.get('page') or {}
    margins = page.get('margins') or {}
    template.page_size = page.get('size', template.page_size)
    template.orientation = page.get('orientation', template.orientation)
    template.margin_top_mm = _number(margins.get('top'), float(template.margin_top_mm))
    template.margin_bottom_mm = _number(margins.get('bottom'), float(template.margin_bottom_mm))
    template.margin_left_mm = _number(margins.get('left'), float(template.margin_left_mm))
    template.margin_right_mm = _number(margins.get('right'), float(template.margin_right_mm))

    _write_tree(template, data.get('sections') or [])
    db_session.commit()
    return jsonify(_template_json(template, _load_tree(template)))


@document_templates_blueprint.post('/api/document-templates/<int:template_id>/versions')
@require_auth(roles=['admin', 'editor'])
def new_version(template_id):
    """A published template's successor: same code, version n+1, a copy of
    its tree. The published one stays exactly as it was, because packs
    already rendered from it."""
    source = db_session.get(DocumentTemplate, template_id)
    if source is None or not source.is_active:
        return jsonify({'message': 'Template not found'}), 404

    latest = db_session.execute(
        select(DocumentTemplate.version)
        .where(DocumentTemplate.firm_id == source.firm_id,
               DocumentTemplate.code == source.code)
        .order_by(DocumentTemplate.version.desc())).scalars().first() or source.version

    clone = DocumentTemplate(
        firm_id=source.firm_id, name=source.name, code=source.code,
        description=source.description, version=latest + 1, is_published=0,
        brand_kit_id=source.brand_kit_id, page_size=source.page_size,
        orientation=source.orientation,
        margin_top_mm=source.margin_top_mm, margin_bottom_mm=source.margin_bottom_mm,
        margin_left_mm=source.margin_left_mm, margin_right_mm=source.margin_right_mm,
    )
    db_session.add(clone)
    db_session.flush()
    _write_tree(clone, _load_tree(source))
    db_session.commit()
    return jsonify(_template_json(clone, _load_tree(clone))), 201


@document_templates_blueprint.post('/api/document-templates/<int:template_id>/publish')
@require_auth(roles=['admin'])
def publish_template(template_id):
    template = db_session.get(DocumentTemplate, template_id)
    if template is None or not template.is_active:
        return jsonify({'message': 'Template not found'}), 404
    sections = _load_tree(template)
    if not sections:
        return jsonify({'message': 'A template with no sections cannot be published.'}), 400
    template.is_published = 1
    db_session.commit()
    return jsonify(_template_json(template, sections))


@document_templates_blueprint.delete('/api/document-templates/<int:template_id>')
@require_auth(roles=['admin'])
def delete_template(template_id):
    template = db_session.get(DocumentTemplate, template_id)
    if template is None or not template.is_active:
        return jsonify({'message': 'Template not found'}), 404
    # Soft: a pack may record having been rendered from it.
    template.is_active = 0
    db_session.commit()
    return jsonify({'ok': True})
