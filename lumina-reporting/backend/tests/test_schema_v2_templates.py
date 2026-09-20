"""The layout model, exercised against a real database.

Every constraint below is load-bearing design rather than hygiene, so each
one is proven by letting the database reject the row. A CheckConstraint
SQLAlchemy accepts but the engine ignores is worth nothing.
"""

import datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import schema_v2 as v2


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'templates.sqlite'}")

    @event.listens_for(engine, 'connect')
    def _fk_on(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()

    v2.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def firm(db):
    record = v2.Firm(name='Pzena Investment Management', code='PZN')
    db.add(record)
    db.commit()
    return record


@pytest.fixture()
def template(db, firm):
    record = v2.DocumentTemplate(firm_id=firm.id, name='Monthly Factsheet',
                                 code='factsheet', page_size='a4',
                                 orientation='portrait', margin_top_mm=26,
                                 margin_bottom_mm=20, margin_left_mm=16,
                                 margin_right_mm=16)
    db.add(record)
    db.commit()
    return record


@pytest.fixture()
def source(db, firm):
    record = v2.DataSource(firm_id=firm.id, name='Snowflake', source_type='snowflake')
    db.add(record)
    db.commit()
    return record


@pytest.fixture()
def dataset(db, firm, source):
    record = v2.Dataset(firm_id=firm.id, source_id=source.id, name='Holdings',
                        code='holdings', grain='portfolio_position',
                        source_object='ANALYTICS.HOLDINGS')
    db.add(record)
    db.commit()
    return record


@pytest.fixture()
def spec(db, firm, dataset):
    record = v2.DisplaySpec(firm_id=firm.id, dataset_id=dataset.id,
                            name='Top Ten', code='top_ten', row_limit=10)
    db.add(record)
    db.commit()
    return record


def section(db, template, ordinal=0, **overrides):
    values = {'firm_id': template.firm_id, 'template_id': template.id,
              'ordinal': ordinal, 'layout_mode': 'flow'}
    values.update(overrides)
    record = v2.TemplateSection(**values)
    db.add(record)
    db.commit()
    return record


def element(db, parent, **overrides):
    values = {'firm_id': parent.firm_id, 'section_id': parent.id,
              'element_type': 'text', 'x_mm': 0, 'y_mm': 0,
              'w_mm': 178, 'h_mm': 10, 'static_text': 'Hello'}
    values.update(overrides)
    record = v2.TemplateElement(**values)
    db.add(record)
    db.commit()
    return record


# ---------------------------------------------------------------------------
# Sections: what 'fixed' and 'flow' actually mean
# ---------------------------------------------------------------------------

def test_a_fixed_band_declares_a_height_and_a_flow_band_does_not(db, template):
    assert section(db, template, 0, layout_mode='flow', height_mm=None)
    assert section(db, template, 1, layout_mode='fixed', height_mm=32)


@pytest.mark.parametrize('layout_mode,height', [('fixed', None), ('flow', 40)])
def test_height_must_match_the_layout_mode(db, template, layout_mode, height):
    """A fixed band with no height has nothing to anchor against; a flow
    band with one is claiming a size its content decides."""
    with pytest.raises(IntegrityError):
        section(db, template, 0, layout_mode=layout_mode, height_mm=height)


def test_only_a_fixed_section_may_repeat_on_every_page(db, template):
    assert section(db, template, 0, layout_mode='fixed', height_mm=18,
                   repeat_mode='every_page')
    db.rollback()
    with pytest.raises(IntegrityError):
        # A band whose height is its content's cannot be drawn identically
        # on every page -- a running header that changes height is a broken
        # document, not a flexible one.
        section(db, template, 1, layout_mode='flow', repeat_mode='every_page')


def test_only_a_flow_section_may_iterate_a_display_spec(db, template, spec):
    assert section(db, template, 0, layout_mode='flow',
                   iterate_display_spec_id=spec.id)
    db.rollback()
    with pytest.raises(IntegrityError):
        # N rows means N bands, so the height is not knowable in advance --
        # which is exactly what 'fixed' promises it is.
        section(db, template, 1, layout_mode='fixed', height_mm=40,
                iterate_display_spec_id=spec.id)


def test_two_sections_cannot_share_an_ordinal(db, template):
    section(db, template, 0)
    with pytest.raises(IntegrityError):
        section(db, template, 0)


@pytest.mark.parametrize('field,value', [
    ('layout_mode', 'absolute'), ('repeat_mode', 'sometimes'),
    ('break_before', 'maybe'), ('break_after', 'maybe'),
])
def test_section_vocabularies_are_closed(db, template, field, value):
    with pytest.raises(IntegrityError):
        section(db, template, 0, **{field: value,
                                    **({'height_mm': 10} if value == 'absolute' else {})})


# ---------------------------------------------------------------------------
# Elements: the box
# ---------------------------------------------------------------------------

def test_an_element_is_positioned_within_its_section_in_both_modes(db, template):
    """Position is relative to the section's own corner either way. The
    difference between the modes is where that corner lands, not how
    elements sit inside it."""
    flowing = section(db, template, 0, layout_mode='flow')
    anchored = section(db, template, 1, layout_mode='fixed', height_mm=30)
    for parent in (flowing, anchored):
        assert element(db, parent, x_mm=12, y_mm=4, w_mm=40, h_mm=8)


@pytest.mark.parametrize('box', [
    {'x_mm': -1}, {'y_mm': -1}, {'w_mm': 0}, {'h_mm': 0}, {'w_mm': -5},
])
def test_an_element_box_cannot_be_negative_or_empty(db, template, box):
    parent = section(db, template, 0)
    with pytest.raises(IntegrityError):
        element(db, parent, **box)


def test_draw_order_is_explicit(db, template):
    """Left implicit, a PPTX shape tree (ordered) and an HTML stacking
    context (not) would disagree about what sits on top."""
    parent = section(db, template, 0)
    back = element(db, parent, element_type='box', z_index=0)
    front = element(db, parent, element_type='text', z_index=10)
    assert back.z_index < front.z_index


# ---------------------------------------------------------------------------
# Elements: the binding
# ---------------------------------------------------------------------------

def test_each_binding_kind_carries_exactly_its_own_reference(db, template, spec, dataset, firm):
    field = v2.DatasetField(firm_id=firm.id, dataset_id=dataset.id, name='Weight',
                            source_column='weight', field_role='measure',
                            data_type='percent', default_aggregation='sum')
    db.add(field)
    db.commit()

    parent = section(db, template, 0)
    assert element(db, parent, element_type='text', binding_kind='none')
    assert element(db, parent, element_type='field', binding_kind='dataset_field',
                   dataset_field_id=field.id)
    assert element(db, parent, element_type='table', binding_kind='display_spec',
                   display_spec_id=spec.id)
    assert element(db, parent, element_type='page_number', binding_kind='system',
                   binding_key='page_number')


def test_a_binding_cannot_claim_one_kind_and_carry_another(db, template, spec):
    """Without this the renderer has to guess which reference to honour."""
    parent = section(db, template, 0)
    with pytest.raises(IntegrityError):
        element(db, parent, element_type='table', binding_kind='dataset_field',
                display_spec_id=spec.id)


def test_a_binding_cannot_carry_two_references_at_once(db, template, spec):
    parent = section(db, template, 0)
    with pytest.raises(IntegrityError):
        element(db, parent, element_type='table', binding_kind='display_spec',
                display_spec_id=spec.id, binding_key='client_name')


def test_a_static_element_carries_no_reference(db, template, spec):
    parent = section(db, template, 0)
    with pytest.raises(IntegrityError):
        element(db, parent, binding_kind='none', display_spec_id=spec.id)


def test_system_bindings_are_a_closed_list(db, template):
    """An open one becomes a template language, and then an injection
    surface."""
    parent = section(db, template, 0)
    with pytest.raises(IntegrityError):
        element(db, parent, element_type='field', binding_kind='system',
                binding_key='os.environ')


# ---------------------------------------------------------------------------
# The renderer-agnostic rule, enforced
# ---------------------------------------------------------------------------

def test_a_style_names_a_brand_token(db, template):
    parent = section(db, template, 0)
    assert element(db, parent, style_token='heading_1')
    assert element(db, parent, style_token=None)


@pytest.mark.parametrize('css', [
    'font-size: 12pt', 'color:#0d6b5f', 'font-weight: 700; color: red',
    'margin-bottom:2mm;',
])
def test_a_style_cannot_be_a_css_declaration(db, template, css):
    """Two renderers consume this tree -- WeasyPrint today, PPTX in Phase G.
    An HTML-only template built by accident here would only be discovered
    when the second renderer ran, which is far too late. A token name never
    contains a colon or a semicolon; a declaration always does."""
    parent = section(db, template, 0)
    with pytest.raises(IntegrityError):
        element(db, parent, style_token=css)


def test_element_type_is_a_closed_list(db, template):
    parent = section(db, template, 0)
    with pytest.raises(IntegrityError):
        element(db, parent, element_type='iframe')


# ---------------------------------------------------------------------------
# The template itself
# ---------------------------------------------------------------------------

def test_a_template_version_is_unique_per_code(db, firm, template):
    with pytest.raises(IntegrityError):
        db.add(v2.DocumentTemplate(firm_id=firm.id, name='Clash',
                                   code=template.code, version=template.version))
        db.commit()


def test_a_new_version_of_the_same_code_is_allowed(db, firm, template):
    """A published template is immutable; an edit makes version n+1, so a
    pack can record which version rendered it."""
    db.add(v2.DocumentTemplate(firm_id=firm.id, name='Monthly Factsheet',
                               code=template.code, version=template.version + 1))
    db.commit()


@pytest.mark.parametrize('field,value', [
    ('page_size', 'a5'), ('orientation', 'sideways'),
])
def test_page_vocabularies_are_closed(db, firm, field, value):
    with pytest.raises(IntegrityError):
        db.add(v2.DocumentTemplate(firm_id=firm.id, name='X', code='x', **{field: value}))
        db.commit()


def test_margins_cannot_be_negative(db, firm):
    with pytest.raises(IntegrityError):
        db.add(v2.DocumentTemplate(firm_id=firm.id, name='X', code='x', margin_top_mm=-5))
        db.commit()


def test_measurements_are_millimetres_not_pixels(db, template):
    """A document is a physical artefact. mm converts cleanly to CSS mm, to
    PowerPoint's EMU and to PDF points; px bakes in a DPI only one of the
    three shares."""
    parent = section(db, template, 0, layout_mode='fixed', height_mm=29.7)
    drawn = element(db, parent, x_mm=10.5, y_mm=3.25, w_mm=88.9, h_mm=6.35)
    db.refresh(drawn)
    # Held to three decimal places, so a layout reproduces rather than
    # drifting a hair per element.
    assert float(drawn.x_mm) == pytest.approx(10.5)
    assert float(drawn.w_mm) == pytest.approx(88.9)
    assert float(parent.height_mm) == pytest.approx(29.7)
