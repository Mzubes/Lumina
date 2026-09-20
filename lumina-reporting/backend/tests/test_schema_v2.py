"""Exercises the v2 schema against a real database.

These are not unit tests of Python objects -- every one of them creates the
tables for real and lets the database enforce (or reject) the row, because a
CheckConstraint that SQLAlchemy accepts but SQLite silently ignores is worth
nothing. SQLite needs foreign_keys pragma ON, which conftest_v2 below does.
"""

import datetime

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import schema_v2 as v2

TODAY = datetime.date(2026, 6, 30)


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'v2.sqlite'}")

    # SQLite ignores foreign keys unless asked, and a schema test that can't
    # see FK violations is testing nothing.
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
def load(db, firm):
    """A reconciled position load -- the normal case."""
    source = v2.DataSource(firm_id=firm.id, name='Custodian SFTP', source_type='sftp', book='custodian')
    db.add(source)
    db.flush()
    record = v2.DataLoad(
        firm_id=firm.id, source_id=source.id, domain='position', book='custodian',
        as_of_date=TODAY, loaded_at=datetime.datetime.utcnow(), row_count=42,
        reconciliation_status='reconciled', reconciled_at=datetime.datetime.utcnow(),
        reconciled_by_system='Recon Engine', reconciliation_reference='RUN-88123',
    )
    db.add(record)
    db.commit()
    return record


def _client(db, firm, name='Meridian Pension Partners'):
    record = v2.Client(firm_id=firm.id, name=name)
    db.add(record)
    db.flush()
    return record


def _portfolio(db, firm, client=None, code='MPP-GSCV', portfolio_type='separate_account'):
    record = v2.Portfolio(
        firm_id=firm.id, name=code, code=code, portfolio_type=portfolio_type,
        client_id=client.id if client else None, base_currency='USD',
    )
    db.add(record)
    db.flush()
    return record


def _instrument(db, firm, identifier='US5949181045', name='Microsoft Corp'):
    record = v2.Instrument(firm_id=firm.id, name=name, primary_identifier=identifier,
                           instrument_type='equity', currency='USD')
    db.add(record)
    db.flush()
    return record




def _dataset(db, firm, load, code='holdings', grain='portfolio_position', **kwargs):
    kwargs.setdefault('source_object', 'REPORTING.V_HOLDINGS')
    record = v2.Dataset(firm_id=firm.id, source_id=load.source_id, name=code.title(),
                        code=code, grain=grain, **kwargs)
    db.add(record)
    db.flush()
    return record


def _field(db, firm, dataset, source_column, name, **kwargs):
    record = v2.DatasetField(firm_id=firm.id, dataset_id=dataset.id,
                             source_column=source_column, name=name, **kwargs)
    db.add(record)
    db.flush()
    return record


# ---------------------------------------------------------------------------
# The structural fix: one axis, and a client can hold several mandates
# ---------------------------------------------------------------------------

def test_one_client_can_hold_two_portfolios_in_the_same_strategy(db, firm):
    """The thing today's schema cannot represent at all."""
    strategy = v2.Strategy(firm_id=firm.id, name='Global Small Cap Value', code='GSCV')
    db.add(strategy)
    db.flush()
    client = _client(db, firm)

    for code in ('MPP-GSCV-A', 'MPP-GSCV-B'):
        portfolio = _portfolio(db, firm, client, code=code)
        portfolio.strategy_id = strategy.id
    db.commit()

    owned = db.scalars(select(v2.Portfolio).where(v2.Portfolio.client_id == client.id)).all()
    assert len(owned) == 2
    assert {p.strategy_id for p in owned} == {strategy.id}


def test_a_separate_account_must_have_a_client(db, firm):
    db.add(v2.Portfolio(firm_id=firm.id, name='Orphan', code='ORPH',
                        portfolio_type='separate_account', client_id=None))
    with pytest.raises(IntegrityError):
        db.commit()


def test_a_pooled_fund_must_not_have_a_client(db, firm):
    client = _client(db, firm)
    db.add(v2.Portfolio(firm_id=firm.id, name='Fund', code='FND',
                        portfolio_type='pooled_fund', client_id=client.id))
    with pytest.raises(IntegrityError):
        db.commit()


def test_a_fund_and_a_separate_account_share_one_row_shape(db, firm, load):
    """One axis. Both are portfolios, and dataset rows key off the same
    column for either -- which is what today's client_id/fund_id pair makes
    impossible."""
    fund = _portfolio(db, firm, None, code='GSCV-FUND', portfolio_type='pooled_fund')
    sma = _portfolio(db, firm, _client(db, firm))
    dataset = _dataset(db, firm, load)
    for portfolio in (fund, sma):
        db.add(v2.DatasetRow(firm_id=firm.id, dataset_id=dataset.id, portfolio_id=portfolio.id,
                             as_of_date=TODAY, data_load_id=load.id, values='{"MKT_VAL": 1}'))
    db.commit()
    rows = db.scalars(select(v2.DatasetRow)).all()
    assert {r.portfolio_id for r in rows} == {fund.id, sma.id}


def test_a_clients_stake_in_a_fund_is_an_ordinary_instrument(db, firm):
    """No special case: the fund's share class is an instrument, so a client
    holding it is just another row."""
    fund = _portfolio(db, firm, None, code='GSCV-FUND', portfolio_type='pooled_fund')
    unit = _instrument(db, firm, identifier='IE00BXXXXX01', name='GSCV Fund I USD Acc')
    db.add(v2.ShareClass(firm_id=firm.id, portfolio_id=fund.id, instrument_id=unit.id,
                         name='I USD Acc', code='I-USD-ACC', currency='USD'))
    db.commit()
    share_class = db.scalars(select(v2.ShareClass)).one()
    assert share_class.instrument_id == unit.id


# ---------------------------------------------------------------------------
# The semantic layer: display without a migration
# ---------------------------------------------------------------------------

def test_a_new_warehouse_column_is_displayable_without_a_migration(db, firm, load):
    """The reason the typed fact tables were the wrong shape. A firm adds
    ESG_SCORE to its view; it becomes presentable by inserting one metadata
    row, not by altering a table."""
    dataset = _dataset(db, firm, load)
    _field(db, firm, dataset, 'MKT_VAL_BASE', 'Market Value',
           field_role='measure', data_type='currency', default_aggregation='sum')
    db.add(v2.DatasetRow(firm_id=firm.id, dataset_id=dataset.id, as_of_date=TODAY,
                         data_load_id=load.id,
                         values='{"MKT_VAL_BASE": 48000000, "ESG_SCORE": 7.4}'))
    db.commit()

    _field(db, firm, dataset, 'ESG_SCORE', 'ESG Score',
           field_role='measure', data_type='number', default_aggregation='avg')
    db.commit()

    fields = db.scalars(select(v2.DatasetField.name)
                        .where(v2.DatasetField.dataset_id == dataset.id)).all()
    assert set(fields) == {'Market Value', 'ESG Score'}
    # The value was already in the row before the field existed.
    assert 'ESG_SCORE' in db.scalars(select(v2.DatasetRow)).one().values


def test_a_dataset_must_name_exactly_one_source(db, firm, load):
    # Naming both leaves it ambiguous which one runs.
    db.add(v2.Dataset(firm_id=firm.id, source_id=load.source_id, name='Both', code='both',
                      grain='reference', source_object='V_X', source_statement='SELECT 1'))
    with pytest.raises(IntegrityError):
        db.commit()


def test_a_dataset_must_name_at_least_one_source(db, firm, load):
    db.add(v2.Dataset(firm_id=firm.id, source_id=load.source_id, name='Neither', code='neither',
                      grain='reference'))
    with pytest.raises(IntegrityError):
        db.commit()


def test_a_precomputed_measure_cannot_be_re_aggregated(db, firm, load):
    """Averaging a column of delivered returns is arithmetic nobody can
    defend, so the database refuses to configure it."""
    dataset = _dataset(db, firm, load, code='returns', grain='portfolio_period')
    with pytest.raises(IntegrityError):
        _field(db, firm, dataset, 'YTD_RETURN', 'YTD Return', field_role='measure',
               data_type='percent', is_precomputed=1, default_aggregation='avg')


def test_a_precomputed_measure_is_fine_when_left_alone(db, firm, load):
    dataset = _dataset(db, firm, load, code='returns', grain='portfolio_period')
    _field(db, firm, dataset, 'YTD_RETURN', 'YTD Return', field_role='measure',
           data_type='percent', is_precomputed=1, default_aggregation='none')
    db.commit()
    assert db.scalars(select(v2.DatasetField)).one().is_precomputed == 1


def test_a_delivered_market_value_may_be_summed_for_display(db, firm, load):
    """The line: summing delivered values into a sector total is display.
    Deriving a return is not."""
    dataset = _dataset(db, firm, load)
    _field(db, firm, dataset, 'MKT_VAL_BASE', 'Market Value', field_role='measure',
           data_type='currency', is_precomputed=0, default_aggregation='sum')
    db.commit()
    assert db.scalars(select(v2.DatasetField)).one().default_aggregation == 'sum'


def test_an_unknown_aggregation_is_rejected(db, firm, load):
    dataset = _dataset(db, firm, load)
    with pytest.raises(IntegrityError):
        _field(db, firm, dataset, 'X', 'X', default_aggregation='twr')


def test_fields_carry_the_formatting_that_makes_a_page_client_ready(db, firm, load):
    """A number rendered 0.0691 where it should read +6.91% is not a data
    problem, and it is the difference between a pack and a database dump."""
    dataset = _dataset(db, firm, load, code='returns', grain='portfolio_period')
    field = _field(db, firm, dataset, 'YTD_RETURN', 'Year to Date', short_name='YTD',
                   field_role='measure', data_type='percent', is_precomputed=1,
                   alignment='right', display_order=3,
                   format_spec='{"decimals": 2, "show_sign": true, "negative_style": "parentheses"}')
    db.commit()
    stored = db.get(v2.DatasetField, field.id)
    assert stored.short_name == 'YTD' and stored.alignment == 'right'
    assert 'parentheses' in stored.format_spec


# ---------------------------------------------------------------------------
# Sorting, grouping and display flexibility
# ---------------------------------------------------------------------------

def test_one_dataset_carries_several_named_ways_of_showing_it(db, firm, load):
    """"Top 10 by weight", "grouped by sector with subtotals" and "everything
    over 1%, sorted by country" are three specs over one dataset."""
    dataset = _dataset(db, firm, load)
    weight = _field(db, firm, dataset, 'WEIGHT_PCT', 'Weight', field_role='measure',
                    data_type='percent', default_aggregation='sum')
    sector = _field(db, firm, dataset, 'SECTOR', 'Sector', field_role='dimension')

    db.add_all([
        v2.DisplaySpec(
            firm_id=firm.id, dataset_id=dataset.id, name='Top 10 Holdings', code='top10',
            sort_by=f'[{{"field_id": {weight.id}, "direction": "desc"}}]',
            row_limit=10, remainder_label='Other holdings',
        ),
        v2.DisplaySpec(
            firm_id=firm.id, dataset_id=dataset.id, name='By Sector', code='by-sector',
            group_by=f'[{{"field_id": {sector.id}, "sort": "desc", "show_subtotal": true}}]',
            totals=f'{{"grand_total": true, "fields": [{weight.id}]}}',
        ),
        v2.DisplaySpec(
            firm_id=firm.id, dataset_id=dataset.id, name='Material Positions', code='over-1pct',
            filters=f'[{{"field_id": {weight.id}, "op": "gte", "value": 1.0}}]',
        ),
    ])
    db.commit()

    specs = db.scalars(select(v2.DisplaySpec.code)
                       .where(v2.DisplaySpec.dataset_id == dataset.id)).all()
    assert set(specs) == {'top10', 'by-sector', 'over-1pct'}


def test_grouping_can_nest_several_levels(db, firm, load):
    """Arity is open -- a fixed group_by_1..3 would be both limiting and
    mostly null."""
    import json
    dataset = _dataset(db, firm, load)
    levels = [_field(db, firm, dataset, column, column.title()).id
              for column in ('REGION', 'COUNTRY', 'SECTOR')]
    db.add(v2.DisplaySpec(firm_id=firm.id, dataset_id=dataset.id, name='Nested', code='nested',
                          group_by=json.dumps([{'field_id': i, 'show_subtotal': True} for i in levels])))
    db.commit()
    spec = db.scalars(select(v2.DisplaySpec)).one()
    assert [level['field_id'] for level in json.loads(spec.group_by)] == levels


def test_a_truncated_table_says_it_is_truncated(db, firm, load):
    """A top-10 that silently drops the tail misrepresents the portfolio."""
    dataset = _dataset(db, firm, load)
    db.add(v2.DisplaySpec(firm_id=firm.id, dataset_id=dataset.id, name='Top 10', code='t10',
                          row_limit=10, remainder_label='Other 43 holdings'))
    db.commit()
    assert db.scalars(select(v2.DisplaySpec)).one().remainder_label


def test_dimension_grouping_runs_as_sql_not_a_json_scan(db, firm, load):
    """The reason dimension keys are real columns: grouping by portfolio is
    an indexed query even though the measures live in JSON."""
    from sqlalchemy import func
    dataset = _dataset(db, firm, load)
    a = _portfolio(db, firm, _client(db, firm, 'A'), code='A')
    b = _portfolio(db, firm, _client(db, firm, 'B'), code='B')
    for portfolio, count in ((a, 3), (b, 1)):
        for _ in range(count):
            db.add(v2.DatasetRow(firm_id=firm.id, dataset_id=dataset.id,
                                 portfolio_id=portfolio.id, as_of_date=TODAY,
                                 data_load_id=load.id, values='{"MKT_VAL": 1}'))
    db.commit()

    grouped = dict(db.execute(
        select(v2.DatasetRow.portfolio_id, func.count(v2.DatasetRow.id))
        .group_by(v2.DatasetRow.portfolio_id)
    ).all())
    assert grouped == {a.id: 3, b.id: 1}


def test_a_dataset_row_can_be_keyed_to_a_benchmark_instead_of_a_portfolio(db, firm, load):
    """Grain drives which dimension keys are populated -- a benchmark series
    has no portfolio."""
    benchmark = v2.Benchmark(firm_id=firm.id, name='MSCI ACWI', code='ACWI')
    db.add(benchmark)
    db.flush()
    dataset = _dataset(db, firm, load, code='bench-returns', grain='benchmark_period')
    db.add(v2.DatasetRow(firm_id=firm.id, dataset_id=dataset.id, benchmark_id=benchmark.id,
                         as_of_date=TODAY, period_start=datetime.date(2026, 1, 1),
                         data_load_id=load.id, values='{"RETURN_PCT": 8.1}'))
    db.commit()
    row = db.scalars(select(v2.DatasetRow)).one()
    assert row.benchmark_id == benchmark.id and row.portfolio_id is None


# ---------------------------------------------------------------------------
# Provenance and the reconciliation gate
# ---------------------------------------------------------------------------

def test_every_cached_row_is_tied_to_a_load(db, firm, load):
    dataset = _dataset(db, firm, load)
    db.add(v2.DatasetRow(firm_id=firm.id, dataset_id=dataset.id, as_of_date=TODAY,
                         values='{"X": 1}'))
    with pytest.raises(IntegrityError):
        db.commit()


def test_a_reconciled_load_is_publishable(load):
    assert load.is_publishable is True


def test_an_unreconciled_load_is_not_publishable(db, load):
    load.reconciliation_status = 'unreconciled'
    db.commit()
    assert load.is_publishable is False


def test_a_waiver_must_carry_a_reason(db, load):
    load.reconciliation_status = 'waived'
    load.waiver_reason = None
    with pytest.raises(IntegrityError):
        db.commit()


def test_a_waiver_with_a_reason_is_publishable(db, load):
    load.reconciliation_status = 'waived'
    load.waiver_reason = 'Custodian file late; PM signed off for the pack.'
    load.waived_by_user_id = 1
    db.commit()
    assert load.is_publishable is True


def test_a_superseded_load_is_not_publishable_even_when_reconciled(db, load):
    load.is_current = 0
    db.commit()
    assert load.is_publishable is False


def test_a_restatement_supersedes_rather_than_overwrites(db, firm, load):
    """What makes a distributed report reproducible: the original rows
    survive the correction."""
    dataset = _dataset(db, firm, load)
    db.add(v2.DatasetRow(firm_id=firm.id, dataset_id=dataset.id, as_of_date=TODAY,
                         data_load_id=load.id, values='{"MKT_VAL": 100}'))
    db.flush()

    corrected = v2.DataLoad(
        firm_id=firm.id, source_id=load.source_id, domain='position', book='custodian',
        as_of_date=TODAY, loaded_at=datetime.datetime.utcnow(),
        reconciliation_status='reconciled', supersedes_id=load.id, is_current=1,
    )
    db.add(corrected)
    load.is_current = 0
    db.flush()
    db.add(v2.DatasetRow(firm_id=firm.id, dataset_id=dataset.id, as_of_date=TODAY,
                         data_load_id=corrected.id, values='{"MKT_VAL": 110}'))
    db.commit()

    values = sorted(r.values for r in db.scalars(select(v2.DatasetRow)).all())
    assert values == ['{"MKT_VAL": 100}', '{"MKT_VAL": 110}']
    current = db.scalars(select(v2.DataLoad).where(v2.DataLoad.is_current == 1)).all()
    assert [record.id for record in current] == [corrected.id]


def test_load_rejects_an_unknown_book(db, load):
    load.book = 'guesswork'
    with pytest.raises(IntegrityError):
        db.commit()


def test_the_same_date_can_carry_both_an_ibor_and_a_custodian_view(db, firm, load):
    source = db.get(v2.DataSource, load.source_id)
    db.add(v2.DataLoad(firm_id=firm.id, source_id=source.id, domain='position', book='ibor',
                       as_of_date=TODAY, loaded_at=datetime.datetime.utcnow(),
                       reconciliation_status='reconciled'))
    db.commit()
    assert {row.book for row in db.scalars(select(v2.DataLoad)).all()} == {'custodian', 'ibor'}


def test_a_warehouse_load_records_the_query_and_the_point_in_time_it_read(db, load):
    """Enough to re-run the exact read later via Time Travel, rather than
    merely describing it."""
    load.source_query_reference = '01b2c3d4-0000-abcd-0000-000000000001'
    load.source_as_of_timestamp = datetime.datetime(2026, 7, 1, 6, 0, 0)
    load.source_statement = 'SELECT * FROM REPORTING.V_HOLDINGS WHERE AS_OF_DATE = %(d)s'
    db.commit()
    reread = db.get(v2.DataLoad, load.id)
    assert reread.source_query_reference.startswith('01b2c3d4')


def test_warehouse_provenance_is_optional(load):
    """A manual upload has no query id and must not invent one."""
    assert load.source_query_reference is None
    assert load.is_publishable is True


# ---------------------------------------------------------------------------
# Benchmarks and composites
# ---------------------------------------------------------------------------

def test_a_benchmark_has_an_identity_not_just_a_number(db, firm):
    benchmark = v2.Benchmark(firm_id=firm.id, name='MSCI ACWI ex-USA Small Cap Value (Net)',
                             code='ACWIXUS-SCV-N', provider='MSCI', return_variant='net')
    db.add(benchmark)
    db.commit()
    stored = db.scalars(select(v2.Benchmark)).one()
    # The thing today's bare Numeric cannot answer.
    assert stored.name.startswith('MSCI') and stored.return_variant == 'net'


def test_a_portfolios_benchmark_is_effective_dated(db, firm):
    portfolio = _portfolio(db, firm, _client(db, firm))
    old = v2.Benchmark(firm_id=firm.id, name='Old Index', code='OLD')
    new = v2.Benchmark(firm_id=firm.id, name='New Index', code='NEW')
    db.add_all([old, new])
    db.flush()
    db.add_all([
        v2.PortfolioBenchmark(firm_id=firm.id, portfolio_id=portfolio.id, benchmark_id=old.id,
                              effective_from=datetime.date(2020, 1, 1),
                              effective_to=datetime.date(2025, 12, 31)),
        v2.PortfolioBenchmark(firm_id=firm.id, portfolio_id=portfolio.id, benchmark_id=new.id,
                              effective_from=datetime.date(2026, 1, 1)),
    ])
    db.commit()

    asked = datetime.date(2024, 6, 30)
    in_force = db.scalars(
        select(v2.PortfolioBenchmark)
        .where(v2.PortfolioBenchmark.portfolio_id == portfolio.id)
        .where(v2.PortfolioBenchmark.effective_from <= asked)
    ).all()
    live = [row for row in in_force if row.effective_to is None or row.effective_to >= asked]
    assert [row.benchmark_id for row in live] == [old.id]


def test_composite_membership_is_dated_so_history_cannot_be_rewritten(db, firm):
    composite = v2.Composite(firm_id=firm.id, name='Global Small Cap Value Composite', code='GSCV-C')
    db.add(composite)
    db.flush()
    portfolio = _portfolio(db, firm, _client(db, firm))
    db.add(v2.CompositeMembership(
        firm_id=firm.id, composite_id=composite.id, portfolio_id=portfolio.id,
        effective_from=datetime.date(2022, 1, 1), effective_to=datetime.date(2025, 6, 30),
        exclusion_reason='Client terminated the mandate',
    ))
    db.commit()
    row = db.scalars(select(v2.CompositeMembership)).one()
    assert row.effective_to == datetime.date(2025, 6, 30) and row.exclusion_reason


def test_a_composite_completeness_check_is_expressible(db, firm):
    """GIPS: every discretionary, fee-paying portfolio must be in at least
    one composite. Today's schema cannot even ask."""
    client = _client(db, firm)
    member = _portfolio(db, firm, client, code='IN')
    _portfolio(db, firm, client, code='OUT')
    composite = v2.Composite(firm_id=firm.id, name='C', code='C')
    db.add(composite)
    db.flush()
    db.add(v2.CompositeMembership(firm_id=firm.id, composite_id=composite.id,
                                  portfolio_id=member.id, effective_from=TODAY))
    db.commit()

    missing = db.scalars(
        select(v2.Portfolio.code)
        .where(v2.Portfolio.is_discretionary == 1, v2.Portfolio.is_fee_paying == 1)
        .where(v2.Portfolio.id.notin_(select(v2.CompositeMembership.portfolio_id)))
    ).all()
    assert missing == ['OUT']


def test_one_instrument_carries_many_identifiers(db, firm):
    """The fix for the same security arriving from two feeds as two rows that
    never aggregate."""
    instrument = _instrument(db, firm)
    db.add_all([
        v2.InstrumentIdentifier(firm_id=firm.id, instrument_id=instrument.id,
                                id_type='isin', id_value='US5949181045'),
        v2.InstrumentIdentifier(firm_id=firm.id, instrument_id=instrument.id,
                                id_type='cusip', id_value='594918104'),
        v2.InstrumentIdentifier(firm_id=firm.id, instrument_id=instrument.id,
                                id_type='ticker', id_value='MSFT'),
    ])
    db.commit()
    for id_type, value in (('isin', 'US5949181045'), ('cusip', '594918104'), ('ticker', 'MSFT')):
        found = db.scalars(
            select(v2.InstrumentIdentifier)
            .where(v2.InstrumentIdentifier.id_type == id_type,
                   v2.InstrumentIdentifier.id_value == value)
        ).one()
        assert found.instrument_id == instrument.id


# ---------------------------------------------------------------------------
# Frozen snapshots
# ---------------------------------------------------------------------------

def _snapshot(db, firm, report_id=1, version=1, payload='{"components": []}'):
    record = v2.ReportSnapshot(
        firm_id=firm.id, report_id=report_id, version=version,
        as_of_date=datetime.datetime(2026, 6, 30), frozen_at=datetime.datetime.utcnow(),
        payload=payload, content_hash='a' * 64,
    )
    db.add(record)
    db.flush()
    return record


def test_a_snapshot_freezes_the_resolved_content_not_just_the_rendering(db, firm, load):
    snapshot = _snapshot(db, firm, payload='{"top_holdings": [{"name": "Microsoft", "weight": 7.8}]}')
    db.add(v2.ReportDataBinding(firm_id=firm.id, report_snapshot_id=snapshot.id,
                                data_load_id=load.id))
    db.commit()
    assert 'Microsoft' in db.scalars(select(v2.ReportSnapshot)).one().payload
    assert [b.data_load_id for b in db.scalars(select(v2.ReportDataBinding)).all()] == [load.id]


def test_a_reissue_is_a_new_version_never_an_overwrite(db, firm):
    _snapshot(db, firm, report_id=7, version=1, payload='{"nav": 1000000}')
    _snapshot(db, firm, report_id=7, version=2, payload='{"nav": 1010000}')
    db.commit()
    versions = db.scalars(select(v2.ReportSnapshot)
                          .where(v2.ReportSnapshot.report_id == 7)).all()
    assert sorted(v.version for v in versions) == [1, 2]


def test_two_snapshots_cannot_share_a_version(db, firm):
    _snapshot(db, firm, report_id=7, version=1)
    # _snapshot flushes, so the constraint fires on the insert itself.
    with pytest.raises(IntegrityError):
        _snapshot(db, firm, report_id=7, version=1)


def test_the_publish_gate_is_checkable_across_every_bound_load(db, firm, load):
    """One unattested load must not slip into a pack alongside three good
    ones -- only enforceable if the check runs over the whole set."""
    source = db.get(v2.DataSource, load.source_id)
    bad = v2.DataLoad(firm_id=firm.id, source_id=source.id, domain='performance', book='abor',
                      as_of_date=TODAY, loaded_at=datetime.datetime.utcnow(),
                      reconciliation_status='unreconciled')
    db.add(bad)
    db.commit()

    intended = [load, bad]
    assert all(record.is_publishable for record in intended) is False
    assert [r.domain for r in intended if not r.is_publishable] == ['performance']


# ---------------------------------------------------------------------------
# Brand kits -- the marketing-quality half
# ---------------------------------------------------------------------------

def test_a_firm_default_brand_kit_and_a_client_override_coexist(db, firm):
    client = _client(db, firm)
    db.add_all([
        v2.BrandKit(firm_id=firm.id, client_id=None, is_firm_default=1, name='House Style',
                    colors='{"primary": "#1447E6", "chart_series": ["#1447E6", "#38BDF8"]}'),
        v2.BrandKit(firm_id=firm.id, client_id=client.id, name='Meridian White Label',
                    logo_uri='s3://brand/meridian.svg'),
    ])
    db.commit()

    default = db.scalars(select(v2.BrandKit).where(v2.BrandKit.client_id.is_(None))).one()
    override = db.scalars(select(v2.BrandKit).where(v2.BrandKit.client_id == client.id)).one()
    assert default.is_firm_default == 1
    assert override.logo_uri.endswith('meridian.svg')


def test_a_client_cannot_have_two_brand_kits(db, firm):
    client = _client(db, firm)
    db.add_all([
        v2.BrandKit(firm_id=firm.id, client_id=client.id, name='One'),
        v2.BrandKit(firm_id=firm.id, client_id=client.id, name='Two'),
    ])
    with pytest.raises(IntegrityError):
        db.commit()


def test_a_brand_kit_carries_a_separate_numeric_typeface(db, firm):
    """Figures in a holdings table need tabular digits or the columns don't
    line up, and most brand body faces are proportional."""
    db.add(v2.BrandKit(
        firm_id=firm.id, is_firm_default=1, name='House Style',
        typography='{"heading_family": "Canela", "body_family": "Graphik", '
                   '"numeric_family": "Graphik Tabular"}',
    ))
    db.commit()
    assert 'Tabular' in db.scalars(select(v2.BrandKit)).one().typography


def test_every_table_carries_its_tenant(db):
    """The column a row-level-security policy keys on. A table without it is
    a table that leaks across firms."""
    missing = [
        name for name, table in v2.metadata.tables.items()
        if name != 'firm' and 'firm_id' not in table.columns
    ]
    assert missing == []
