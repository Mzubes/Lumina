"""What the canvas's field picker is offered, and where the samples come from.

The picker is only as good as the metadata behind it, and the property
worth pinning down is not "the endpoint returns 200" -- it is that a
SYNTHESISED sample is never presented as a real one. An author who sizes a
column against a made-up number lays the page out twice; one who does it
without being told the number is made up may not lay it out again at all.
"""

import datetime
import json

import pytest

from bindings_catalogue import TYPE_SAMPLES, build_catalogue
from database import db_session
from schema_v2 import (DataLoad, Dataset, DatasetField, DatasetRow, DataSource,
                       DisplaySpec, Firm)

TODAY = datetime.date(2026, 9, 30)


@pytest.fixture()
def firm(app):
    with app.app_context():
        record = Firm(name='Test Firm', code='default')
        db_session.add(record)
        db_session.commit()
        return record.id


def _dataset(firm_id, code='holdings', cached_values=None):
    source = DataSource(firm_id=firm_id, name='Warehouse', source_type='manual')
    db_session.add(source)
    db_session.flush()
    # A dataset names exactly one source -- an object or a statement, never
    # both and never neither (ck_dataset_one_source).
    dataset = Dataset(firm_id=firm_id, source_id=source.id, name='Holdings',
                      code=code, grain='portfolio_position',
                      source_object='REPORTING.V_HOLDINGS')
    db_session.add(dataset)
    db_session.flush()
    db_session.add_all([
        DatasetField(firm_id=firm_id, dataset_id=dataset.id, source_column='SECTOR',
                     name='Sector', field_role='dimension', data_type='string',
                     display_order=0),
        DatasetField(firm_id=firm_id, dataset_id=dataset.id, source_column='MKT_VAL',
                     name='Market value', short_name='Mkt val', field_role='measure',
                     data_type='currency', default_aggregation='sum',
                     alignment='right', display_order=1),
    ])
    if cached_values is not None:
        load = DataLoad(firm_id=firm_id, source_id=source.id, domain='position',
                        book='abor', as_of_date=TODAY,
                        loaded_at=datetime.datetime.utcnow())
        db_session.add(load)
        db_session.flush()
        for values in cached_values:
            db_session.add(DatasetRow(firm_id=firm_id, dataset_id=dataset.id,
                                      as_of_date=TODAY, data_load_id=load.id,
                                      values=json.dumps(values)))
    db_session.commit()
    return dataset


def test_a_cached_value_is_a_real_sample(app, firm):
    with app.app_context():
        _dataset(firm, cached_values=[{'SECTOR': 'Technology', 'MKT_VAL': 48250000}])
        catalogue = build_catalogue(db_session, firm)

    dataset = catalogue['datasets'][0]
    assert dataset['has_cached_rows'] is True
    by_name = {field['name']: field for field in dataset['fields']}
    assert by_name['Sector']['sample'] == 'Technology'
    assert by_name['Sector']['sample_is_real'] is True
    assert by_name['Market value']['sample'] == 48250000


def test_a_derived_sample_is_flagged_as_derived(app, firm):
    """The property this module exists for. A stand-in that claims to be
    real is worse than no sample at all."""
    with app.app_context():
        _dataset(firm, cached_values=None)
        catalogue = build_catalogue(db_session, firm)

    dataset = catalogue['datasets'][0]
    assert dataset['has_cached_rows'] is False
    for field in dataset['fields']:
        assert field['sample_is_real'] is False
        assert field['sample'] == TYPE_SAMPLES[field['data_type']]


def test_a_sparse_column_falls_back_per_field_not_per_dataset(app, firm):
    """A null in row one is not a reason to synthesise: the column may
    simply be sparse, and the next row carries a real value."""
    with app.app_context():
        _dataset(firm, cached_values=[
            {'SECTOR': None, 'MKT_VAL': 100},
            {'SECTOR': 'Industrials', 'MKT_VAL': 200},
        ])
        catalogue = build_catalogue(db_session, firm)

    by_name = {field['name']: field for field in catalogue['datasets'][0]['fields']}
    assert by_name['Sector']['sample'] == 'Industrials'
    assert by_name['Sector']['sample_is_real'] is True


def test_a_column_absent_from_every_cached_row_is_derived(app, firm):
    with app.app_context():
        _dataset(firm, cached_values=[{'MKT_VAL': 100}])
        catalogue = build_catalogue(db_session, firm)

    by_name = {field['name']: field for field in catalogue['datasets'][0]['fields']}
    assert by_name['Sector']['sample_is_real'] is False
    assert by_name['Market value']['sample_is_real'] is True


def test_field_metadata_reaches_the_picker(app, firm):
    """The reason the semantic layer exists: the picker shows "Market value,
    currency, right-aligned", not "MKT_VAL"."""
    with app.app_context():
        _dataset(firm, cached_values=[{'MKT_VAL': 1}])
        catalogue = build_catalogue(db_session, firm)

    field = [f for f in catalogue['datasets'][0]['fields'] if f['name'] == 'Market value'][0]
    assert field['short_name'] == 'Mkt val'
    assert field['field_role'] == 'measure'
    assert field['data_type'] == 'currency'
    assert field['default_aggregation'] == 'sum'
    assert field['alignment'] == 'right'
    assert field['source_column'] == 'MKT_VAL'


def test_a_display_spec_is_described_by_its_fields_not_its_json(app, firm):
    with app.app_context():
        dataset = _dataset(firm, cached_values=[{'MKT_VAL': 1}])
        sector = db_session.query(DatasetField).filter_by(
            dataset_id=dataset.id, source_column='SECTOR').first()
        value = db_session.query(DatasetField).filter_by(
            dataset_id=dataset.id, source_column='MKT_VAL').first()
        db_session.add(DisplaySpec(
            firm_id=firm, dataset_id=dataset.id, name='Top 10 by sector', code='t10',
            group_by=json.dumps([{'field_id': sector.id, 'show_subtotal': True}]),
            sort_by=json.dumps([{'field_id': value.id, 'direction': 'desc'}]),
            row_limit=10))
        db_session.commit()
        catalogue = build_catalogue(db_session, firm)

    spec = catalogue['datasets'][0]['display_specs'][0]
    # "grouped by Sector, sorted by Market value, top 10" is checkable by a
    # human; {"group_by": [{"field_id": 12}]} is not.
    assert 'grouped by Sector' in spec['summary']
    assert 'sorted by Market value' in spec['summary']
    assert 'top 10' in spec['summary']


def test_a_spec_with_no_options_says_so_rather_than_being_blank(app, firm):
    with app.app_context():
        dataset = _dataset(firm)
        db_session.add(DisplaySpec(firm_id=firm, dataset_id=dataset.id,
                                   name='Everything', code='all'))
        db_session.commit()
        catalogue = build_catalogue(db_session, firm)

    assert catalogue['datasets'][0]['display_specs'][0]['summary'] == 'every row, unsorted'


def test_a_spec_naming_a_deleted_field_degrades_instead_of_raising(app, firm):
    with app.app_context():
        dataset = _dataset(firm)
        db_session.add(DisplaySpec(
            firm_id=firm, dataset_id=dataset.id, name='Stale', code='stale',
            group_by=json.dumps([{'field_id': 99999}])))
        db_session.commit()
        catalogue = build_catalogue(db_session, firm)

    assert 'field 99999' in catalogue['datasets'][0]['display_specs'][0]['summary']


def test_the_two_layout_time_system_values_are_marked(app, firm):
    with app.app_context():
        catalogue = build_catalogue(db_session, firm)

    by_key = {entry['key']: entry for entry in catalogue['system']}
    # These are resolved by the engine during pagination, never in Python,
    # so the canvas must not present their samples as values.
    assert by_key['page_number']['resolved_at_layout'] is True
    assert by_key['page_count']['resolved_at_layout'] is True
    assert by_key['client_name']['resolved_at_layout'] is False


def test_a_firm_with_no_datasets_gets_the_system_bindings_anyway(app, firm):
    with app.app_context():
        catalogue = build_catalogue(db_session, firm)
    assert catalogue['datasets'] == []
    assert len(catalogue['system']) == 8


def test_another_firms_datasets_are_not_offered(app, firm):
    with app.app_context():
        other = Firm(name='Other', code='other')
        db_session.add(other)
        db_session.commit()
        _dataset(other.id)
        catalogue = build_catalogue(db_session, firm)
    assert catalogue['datasets'] == []


def test_the_endpoint_serves_the_catalogue(client, auth_headers):
    response = client.get('/api/bindings', headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert {'system', 'datasets'} <= set(body)


def test_the_endpoint_needs_authentication(client):
    assert client.get('/api/bindings').status_code == 401
