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
    # A commingled fund is owned by its unit holders, not by one client.
    # Letting a client_id sit on it is the ambiguity this schema removes.
    client = _client(db, firm)
    db.add(v2.Portfolio(firm_id=firm.id, name='Fund', code='FND',
                        portfolio_type='pooled_fund', client_id=client.id))
    with pytest.raises(IntegrityError):
        db.commit()


def test_a_clients_stake_in_a_fund_is_an_ordinary_position(db, firm, load):
    """No special case: the fund's share class is an instrument, and the
    client's holding of it is a position like any other."""
    fund = _portfolio(db, firm, None, code='GSCV-FUND', portfolio_type='pooled_fund')
    unit = _instrument(db, firm, identifier='IE00BXXXXX01', name='GSCV Fund I USD Acc')
    db.add(v2.ShareClass(firm_id=firm.id, portfolio_id=fund.id, instrument_id=unit.id,
                         name='I USD Acc', code='I-USD-ACC', currency='USD'))

    client = _client(db, firm)
    sma = _portfolio(db, firm, client)
    db.add(v2.Position(firm_id=firm.id, portfolio_id=sma.id, instrument_id=unit.id,
                       as_of_date=TODAY, data_load_id=load.id,
                       quantity=1000, base_market_value=1_250_000))
    db.commit()

    held = db.scalars(select(v2.Position).where(v2.Position.portfolio_id == sma.id)).one()
    assert held.instrument_id == unit.id


def test_a_fund_holds_its_own_positions_on_the_same_table(db, firm, load):
    fund = _portfolio(db, firm, None, code='GSCV-FUND', portfolio_type='pooled_fund')
    instrument = _instrument(db, firm)
    db.add(v2.Position(firm_id=firm.id, portfolio_id=fund.id, instrument_id=instrument.id,
                       as_of_date=TODAY, data_load_id=load.id, base_market_value=48_000_000))
    db.commit()
    assert db.scalars(select(v2.Position).where(v2.Position.portfolio_id == fund.id)).one()


# ---------------------------------------------------------------------------
# Provenance and the reconciliation gate
# ---------------------------------------------------------------------------

def test_every_fact_is_tied_to_a_load(db, firm):
    portfolio = _portfolio(db, firm, _client(db, firm))
    instrument = _instrument(db, firm)
    db.add(v2.Position(firm_id=firm.id, portfolio_id=portfolio.id, instrument_id=instrument.id,
                       as_of_date=TODAY, base_market_value=1))
    with pytest.raises(IntegrityError):
        db.commit()


def test_a_reconciled_load_is_publishable(load):
    assert load.is_publishable is True


def test_an_unreconciled_load_is_not_publishable(db, firm, load):
    load.reconciliation_status = 'unreconciled'
    db.commit()
    assert load.is_publishable is False


def test_a_waiver_must_carry_a_reason(db, firm, load):
    # An unexplained override of the publishing gate would make the gate
    # meaningless, so the database refuses one.
    load.reconciliation_status = 'waived'
    load.waiver_reason = None
    with pytest.raises(IntegrityError):
        db.commit()


def test_a_waiver_with_a_reason_is_publishable(db, firm, load):
    load.reconciliation_status = 'waived'
    load.waiver_reason = 'Custodian file late; PM signed off on IBOR positions for the pack.'
    load.waived_by_user_id = 1
    db.commit()
    assert load.is_publishable is True


def test_a_superseded_load_is_not_publishable_even_when_reconciled(db, firm, load):
    load.is_current = 0
    db.commit()
    assert load.is_publishable is False


def test_a_restatement_supersedes_rather_than_overwrites(db, firm, load):
    """The property that makes a distributed report reproducible: the
    original rows survive the correction."""
    portfolio = _portfolio(db, firm, _client(db, firm))
    instrument = _instrument(db, firm)
    db.add(v2.Position(firm_id=firm.id, portfolio_id=portfolio.id, instrument_id=instrument.id,
                       as_of_date=TODAY, data_load_id=load.id, base_market_value=100))
    db.flush()

    corrected = v2.DataLoad(
        firm_id=firm.id, source_id=load.source_id, domain='position', book='custodian',
        as_of_date=TODAY, loaded_at=datetime.datetime.utcnow(),
        reconciliation_status='reconciled', supersedes_id=load.id, is_current=1,
    )
    db.add(corrected)
    load.is_current = 0
    db.flush()
    db.add(v2.Position(firm_id=firm.id, portfolio_id=portfolio.id, instrument_id=instrument.id,
                       as_of_date=TODAY, data_load_id=corrected.id, base_market_value=110))
    db.commit()

    # Both versions of the same business date still exist...
    rows = db.scalars(select(v2.Position).where(v2.Position.as_of_date == TODAY)).all()
    assert sorted(float(r.base_market_value) for r in rows) == [100.0, 110.0]
    # ...and exactly one load is live.
    current = db.scalars(select(v2.DataLoad).where(v2.DataLoad.is_current == 1)).all()
    assert [record.id for record in current] == [corrected.id]


def test_load_rejects_an_unknown_book(db, firm, load):
    load.book = 'guesswork'
    with pytest.raises(IntegrityError):
        db.commit()


def test_the_same_date_can_carry_both_an_ibor_and_a_custodian_view(db, firm, load):
    """Two books legitimately disagree; the schema records both rather than
    forcing a winner."""
    source = db.get(v2.DataSource, load.source_id)
    ibor = v2.DataLoad(firm_id=firm.id, source_id=source.id, domain='position', book='ibor',
                       as_of_date=TODAY, loaded_at=datetime.datetime.utcnow(),
                       reconciliation_status='reconciled')
    db.add(ibor)
    db.commit()
    books = {row.book for row in db.scalars(select(v2.DataLoad)).all()}
    assert books == {'custodian', 'ibor'}


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------

def test_a_benchmark_has_an_identity_not_just_a_number(db, firm, load):
    benchmark = v2.Benchmark(firm_id=firm.id, name='MSCI ACWI ex-USA Small Cap Value (Net)',
                             code='ACWIXUS-SCV-N', provider='MSCI', return_variant='net')
    db.add(benchmark)
    db.flush()
    db.add(v2.BenchmarkReturn(firm_id=firm.id, benchmark_id=benchmark.id, as_of_date=TODAY,
                              data_load_id=load.id, period_type='YTD', return_pct=8.1))
    db.commit()

    row = db.scalars(select(v2.BenchmarkReturn)).one()
    assert row.benchmark_id == benchmark.id
    # The thing today's bare Numeric cannot answer.
    assert db.get(v2.Benchmark, row.benchmark_id).name.startswith('MSCI')


def test_a_portfolios_benchmark_is_effective_dated(db, firm):
    """A mandate that changes benchmark must not retro-point old reports at
    the new one."""
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


# ---------------------------------------------------------------------------
# Composites
# ---------------------------------------------------------------------------

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
    # The portfolio has left, but the period it was managed is still on record.
    assert row.effective_to == datetime.date(2025, 6, 30)
    assert row.exclusion_reason


def test_composite_returns_carry_the_gips_statistics(db, firm, load):
    composite = v2.Composite(firm_id=firm.id, name='C', code='C')
    db.add(composite)
    db.flush()
    db.add(v2.CompositeReturn(
        firm_id=firm.id, composite_id=composite.id, as_of_date=TODAY, data_load_id=load.id,
        period_type='YTD', method='twr', return_basis='net', return_pct=7.2,
        portfolio_count=14, composite_assets=812_000_000, firm_assets=2_840_000_000,
        dispersion_pct=0.4, three_year_std_dev_pct=16.1,
    ))
    db.commit()
    row = db.scalars(select(v2.CompositeReturn)).one()
    assert row.portfolio_count == 14 and row.dispersion_pct is not None


def test_a_composite_completeness_check_is_expressible(db, firm):
    """GIPS: every discretionary, fee-paying portfolio must be in at least
    one composite. Today's schema cannot even ask the question."""
    client = _client(db, firm)
    member = _portfolio(db, firm, client, code='IN')
    orphan = _portfolio(db, firm, client, code='OUT')
    composite = v2.Composite(firm_id=firm.id, name='C', code='C')
    db.add(composite)
    db.flush()
    db.add(v2.CompositeMembership(firm_id=firm.id, composite_id=composite.id,
                                  portfolio_id=member.id, effective_from=TODAY))
    db.commit()

    in_a_composite = select(v2.CompositeMembership.portfolio_id)
    missing = db.scalars(
        select(v2.Portfolio.code)
        .where(v2.Portfolio.is_discretionary == 1, v2.Portfolio.is_fee_paying == 1)
        .where(v2.Portfolio.id.notin_(in_a_composite))
    ).all()
    assert missing == ['OUT']


# ---------------------------------------------------------------------------
# Returns, currency and vocabularies
# ---------------------------------------------------------------------------

def test_gross_and_net_twr_coexist_for_one_period(db, firm, load):
    portfolio = _portfolio(db, firm, _client(db, firm))
    for basis, value in (('gross', 7.4), ('net', 6.9)):
        db.add(v2.PerformanceReturn(
            firm_id=firm.id, portfolio_id=portfolio.id, as_of_date=TODAY, data_load_id=load.id,
            period_type='YTD', method='twr', return_basis=basis, return_pct=value,
        ))
    db.commit()
    rows = {r.return_basis: float(r.return_pct) for r in db.scalars(select(v2.PerformanceReturn)).all()}
    assert rows == {'gross': 7.4, 'net': 6.9}


def test_twr_and_mwr_are_distinguishable(db, firm, load):
    # Labelling one as the other is a compliance problem, so the column is
    # required rather than assumed.
    portfolio = _portfolio(db, firm, _client(db, firm))
    for method in ('twr', 'mwr'):
        db.add(v2.PerformanceReturn(
            firm_id=firm.id, portfolio_id=portfolio.id, as_of_date=TODAY, data_load_id=load.id,
            period_type='YTD', method=method, return_basis='net', return_pct=6.9,
        ))
    db.commit()
    assert len(db.scalars(select(v2.PerformanceReturn)).all()) == 2


def test_an_unknown_return_method_is_rejected(db, firm, load):
    portfolio = _portfolio(db, firm, _client(db, firm))
    db.add(v2.PerformanceReturn(
        firm_id=firm.id, portfolio_id=portfolio.id, as_of_date=TODAY, data_load_id=load.id,
        period_type='YTD', method='vibes', return_basis='net', return_pct=1,
    ))
    with pytest.raises(IntegrityError):
        db.commit()


def test_an_unknown_transaction_type_is_rejected(db, firm, load):
    portfolio = _portfolio(db, firm, _client(db, firm))
    db.add(v2.Transaction(
        firm_id=firm.id, portfolio_id=portfolio.id, as_of_date=TODAY, data_load_id=load.id,
        transaction_type='teleport', base_amount=1,
    ))
    with pytest.raises(IntegrityError):
        db.commit()


def test_money_is_exact_not_floating_point(db, firm, load):
    """Numeric, not Float: a client report that sums to $1,000,000.00000001
    is a support ticket."""
    from decimal import Decimal
    portfolio = _portfolio(db, firm, _client(db, firm))
    instrument = _instrument(db, firm)
    db.add(v2.Position(firm_id=firm.id, portfolio_id=portfolio.id, instrument_id=instrument.id,
                       as_of_date=TODAY, data_load_id=load.id,
                       base_market_value=Decimal('0.1')))
    db.commit()
    stored = db.scalars(select(v2.Position)).one().base_market_value
    assert isinstance(stored, Decimal)
    assert stored == Decimal('0.1000')


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


def test_valuation_stated_nav_is_kept_beside_the_position_sum(db, firm, load):
    """Both are recorded; the administrator's struck NAV is authoritative and
    Lumina does not silently replace it with its own arithmetic."""
    portfolio = _portfolio(db, firm, _client(db, firm))
    instrument = _instrument(db, firm)
    db.add(v2.Position(firm_id=firm.id, portfolio_id=portfolio.id, instrument_id=instrument.id,
                       as_of_date=TODAY, data_load_id=load.id, base_market_value=999_000))
    db.add(v2.Valuation(firm_id=firm.id, portfolio_id=portfolio.id, as_of_date=TODAY,
                        data_load_id=load.id, base_currency='USD',
                        total_market_value=1_000_000, net_asset_value=998_500))
    db.commit()

    valuation = db.scalars(select(v2.Valuation)).one()
    position_sum = sum(float(p.base_market_value) for p in db.scalars(select(v2.Position)).all())
    assert float(valuation.total_market_value) == 1_000_000
    assert position_sum == 999_000  # a surfaceable variance, not a resolved one


def test_every_table_carries_its_tenant(db):
    """The column a row-level-security policy keys on. A table without it is
    a table that leaks across firms."""
    exempt = {'firm'}
    missing = [
        name for name, table in v2.metadata.tables.items()
        if name not in exempt and 'firm_id' not in table.columns
    ]
    assert missing == []
