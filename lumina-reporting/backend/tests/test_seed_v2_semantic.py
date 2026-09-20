"""The projection that gives the canvas something to bind to.

Nothing outside the tests had ever created a v2 `Dataset`, so the field
picker was correct and empty -- which is indistinguishable from broken for
anyone trying to use it. This projects what `seed_demo` loads into the v2
shapes.
"""

import datetime
import json

from bindings_catalogue import build_catalogue
from database import db_session
from models import FundData, Holding, PerformanceSnapshot
from schema_v2 import Dataset, DatasetField, DatasetRow, DisplaySpec, Firm
from seed_v2_semantic import seed_v2_semantic

AS_OF = datetime.date(2026, 9, 30)


def _demo_rows():
    fund = FundData(name='Global Small Cap', asset_class='Equity', ticker='GSCX')
    db_session.add(fund)
    db_session.commit()
    db_session.add_all([
        Holding(fund_id=fund.id, as_of_date=AS_OF, security_id='ACME',
                security_name='Acme Industrial', asset_class='Equity',
                market_value=16500000, weight_pct=3.3, currency='USD'),
        Holding(fund_id=fund.id, as_of_date=AS_OF, security_id='BETA',
                security_name='Beta Components', asset_class='Equity',
                market_value=9200000, weight_pct=1.84, currency='USD'),
        PerformanceSnapshot(fund_id=fund.id, as_of_date=AS_OF, period_type='1Y',
                            return_pct=12.4, benchmark_return_pct=9.1),
    ])
    db_session.commit()


def test_nothing_to_project_is_not_an_error(app):
    with app.app_context():
        assert seed_v2_semantic() is False


def test_it_projects_holdings_and_performance(app):
    with app.app_context():
        _demo_rows()
        assert seed_v2_semantic() is True

        codes = {dataset.code for dataset in db_session.query(Dataset).all()}
        assert codes == {'holdings', 'performance'}
        assert db_session.query(DatasetRow).count() == 3


def test_it_is_idempotent(app):
    with app.app_context():
        _demo_rows()
        seed_v2_semantic()
        before = db_session.query(DatasetRow).count()
        assert seed_v2_semantic() is False
        assert db_session.query(DatasetRow).count() == before


def test_a_precomputed_return_is_not_aggregatable(app):
    """The schema forbids the pairing, and it is the rule that stops
    someone summing two time-weighted returns."""
    with app.app_context():
        _demo_rows()
        seed_v2_semantic()
        field = db_session.query(DatasetField).filter_by(source_column='RETURN_PCT').one()
        assert field.is_precomputed == 1
        assert field.default_aggregation == 'none'


def test_the_projected_rows_carry_real_values(app):
    with app.app_context():
        _demo_rows()
        seed_v2_semantic()
        firm = db_session.query(Firm).filter_by(code='default').one()
        catalogue = build_catalogue(db_session, firm.id)

    holdings = [d for d in catalogue['datasets'] if d['code'] == 'holdings'][0]
    by_name = {field['name']: field for field in holdings['fields']}
    assert by_name['Security']['sample_is_real'] is True
    assert by_name['Market value']['sample'] == 16500000.0
    # The demo holdings carry no quantity, so that one is honestly derived.
    assert by_name['Quantity']['sample_is_real'] is False


def test_excess_return_is_computed_in_basis_points(app):
    with app.app_context():
        _demo_rows()
        seed_v2_semantic()
        dataset = db_session.query(Dataset).filter_by(code='performance').one()
        values = json.loads(
            db_session.query(DatasetRow).filter_by(dataset_id=dataset.id).one().values)
    assert values['EXCESS_BPS'] == 330      # 12.4% - 9.1% = 3.3pp = 330bps


def test_the_specs_reference_real_field_ids(app):
    """A spec naming a field id that does not exist renders as a summary
    nobody can read and a table nobody can group."""
    with app.app_context():
        _demo_rows()
        seed_v2_semantic()
        ids = {field.id for field in db_session.query(DatasetField).all()}
        for spec in db_session.query(DisplaySpec).all():
            for column in (spec.group_by, spec.sort_by):
                for entry in json.loads(column) if column else []:
                    assert entry['field_id'] in ids, spec.name
