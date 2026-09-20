"""Project the demo data into the v2 semantic layer.

The canvas's field picker reads `Dataset` / `DatasetField` / `DisplaySpec`,
and nothing outside the tests had ever created one -- so the picker was
correct and empty, which is the same as broken for anyone trying to use it.

This projects what `seed_demo` already loaded (`Holding`,
`PerformanceSnapshot`) into the v2 shapes, with the field metadata written
out properly: a label rather than a column name, a data type, an
aggregation, an alignment. That metadata is the entire point of the layer
-- it is what lets the canvas show "Market Value, currency, right-aligned,
sample 48,250,000" instead of "MKT_VAL_BASE".

**This is a projection, not a migration.** It reads the v1 tables and
writes v2 rows; it does not move ownership, and the v1 tables remain the
source the app serves from. The real cutover is its own piece of work.
"""

import datetime
import json

from database import db_session
from models import FundData, Holding, PerformanceSnapshot
from schema_v2 import (DataLoad, Dataset, DatasetField, DatasetRow, DataSource,
                       DisplaySpec, Firm)

DEFAULT_FIRM_CODE = 'default'

# (source_column, name, short_name, role, data_type, aggregation,
#  precomputed, alignment)
HOLDING_FIELDS = (
    ('SECURITY_NAME', 'Security', None, 'dimension', 'string', 'none', 0, 'left'),
    ('ASSET_CLASS', 'Asset class', 'Class', 'dimension', 'string', 'none', 0, 'left'),
    ('CURRENCY', 'Currency', 'CCY', 'dimension', 'string', 'none', 0, 'left'),
    ('MARKET_VALUE', 'Market value', 'Mkt value', 'measure', 'currency', 'sum', 0, 'right'),
    ('WEIGHT_PCT', 'Weight', '%', 'measure', 'percent', 'sum', 0, 'right'),
    ('QUANTITY', 'Quantity', 'Qty', 'measure', 'number', 'sum', 0, 'right'),
    ('SECURITY_ID', 'Security ID', None, 'key', 'string', 'none', 0, 'left'),
)

PERFORMANCE_FIELDS = (
    ('PERIOD_TYPE', 'Period', None, 'dimension', 'string', 'none', 0, 'left'),
    # Pre-computed, so NOT aggregatable -- the schema enforces the pairing,
    # and adding two time-weighted returns is arithmetic nobody can defend.
    ('RETURN_PCT', 'Return', None, 'measure', 'percent', 'none', 1, 'right'),
    ('BENCHMARK_RETURN_PCT', 'Benchmark', 'Bmk', 'measure', 'percent', 'none', 1, 'right'),
    ('EXCESS_BPS', 'Excess', None, 'measure', 'basis_points', 'none', 1, 'right'),
)


def _number(value):
    return float(value) if value is not None else None


def _get_or_create(model, defaults=None, **lookup):
    row = db_session.query(model).filter_by(**lookup).first()
    if row is None:
        row = model(**lookup, **(defaults or {}))
        db_session.add(row)
        db_session.flush()
    return row


def _fields_for(firm, dataset, definitions):
    for order, (column, name, short, role, data_type, how, precomputed, align) in \
            enumerate(definitions):
        _get_or_create(
            DatasetField, dataset_id=dataset.id, source_column=column,
            defaults={
                'firm_id': firm.id, 'name': name, 'short_name': short,
                'field_role': role, 'data_type': data_type,
                'default_aggregation': how, 'is_precomputed': precomputed,
                'alignment': align, 'display_order': order,
                'format_spec': json.dumps({'decimals': 2 if data_type != 'number' else 0}),
            })


def _field_id(dataset, column):
    field = db_session.query(DatasetField).filter_by(
        dataset_id=dataset.id, source_column=column).first()
    return field.id if field else None


def seed_v2_semantic():
    """Idempotent. Returns True when it wrote something."""
    holdings = db_session.query(Holding).order_by(
        Holding.weight_pct.desc().nullslast()).all()
    performance = db_session.query(PerformanceSnapshot).all()
    if not holdings and not performance:
        return False

    firm = _get_or_create(Firm, code=DEFAULT_FIRM_CODE, defaults={'name': 'Default Firm'})
    if db_session.query(Dataset).filter_by(firm_id=firm.id).count():
        return False

    source = _get_or_create(
        DataSource, firm_id=firm.id, name='Demo warehouse',
        defaults={'source_type': 'manual', 'book': 'abor'})

    as_of = (holdings[0].as_of_date if holdings
             else performance[0].as_of_date) or datetime.date.today()
    fund = db_session.query(FundData).first()
    portfolio_name = fund.name if fund else 'Demo portfolio'

    positions = _get_or_create(
        Dataset, firm_id=firm.id, code='holdings',
        defaults={'source_id': source.id, 'name': 'Holdings',
                  'grain': 'portfolio_position', 'is_cached': 1,
                  'description': f'Positions held in {portfolio_name}.',
                  'source_object': 'REPORTING.V_HOLDINGS'})
    returns = _get_or_create(
        Dataset, firm_id=firm.id, code='performance',
        defaults={'source_id': source.id, 'name': 'Performance',
                  'grain': 'portfolio_period', 'is_cached': 1,
                  'description': 'Period returns against the benchmark.',
                  'source_object': 'REPORTING.V_PERFORMANCE'})

    _fields_for(firm, positions, HOLDING_FIELDS)
    _fields_for(firm, returns, PERFORMANCE_FIELDS)
    db_session.flush()

    load = _get_or_create(
        DataLoad, firm_id=firm.id, source_id=source.id, domain='position',
        as_of_date=as_of,
        defaults={'book': 'abor', 'loaded_at': datetime.datetime.utcnow(),
                  'row_count': len(holdings), 'reconciliation_status': 'reconciled',
                  'reconciled_at': datetime.datetime.utcnow(),
                  'reconciled_by_system': 'Demo warehouse'})

    for holding in holdings:
        db_session.add(DatasetRow(
            firm_id=firm.id, dataset_id=positions.id, as_of_date=holding.as_of_date,
            data_load_id=load.id,
            values=json.dumps({
                'SECURITY_ID': holding.security_id,
                'SECURITY_NAME': holding.security_name,
                'ASSET_CLASS': holding.asset_class,
                'CURRENCY': holding.currency,
                'MARKET_VALUE': _number(holding.market_value),
                'WEIGHT_PCT': _number(holding.weight_pct),
                'QUANTITY': _number(holding.quantity),
            })))

    for snapshot in performance:
        excess = None
        if snapshot.return_pct is not None and snapshot.benchmark_return_pct is not None:
            excess = round((_number(snapshot.return_pct)
                            - _number(snapshot.benchmark_return_pct)) * 100)
        db_session.add(DatasetRow(
            firm_id=firm.id, dataset_id=returns.id, as_of_date=snapshot.as_of_date,
            data_load_id=load.id,
            values=json.dumps({
                'PERIOD_TYPE': snapshot.period_type,
                'RETURN_PCT': _number(snapshot.return_pct),
                'BENCHMARK_RETURN_PCT': _number(snapshot.benchmark_return_pct),
                'EXCESS_BPS': excess,
            })))

    # Three specs over one dataset, which is the whole argument for the
    # layer: "top 10 by weight", "by asset class, subtotalled", "everything".
    _get_or_create(
        DisplaySpec, firm_id=firm.id, dataset_id=positions.id, code='top-10',
        defaults={
            'name': 'Top 10 holdings',
            'sort_by': json.dumps([
                {'field_id': _field_id(positions, 'WEIGHT_PCT'), 'direction': 'desc'}]),
            'totals': json.dumps({'grand_total': True,
                                  'fields': [_field_id(positions, 'MARKET_VALUE'),
                                             _field_id(positions, 'WEIGHT_PCT')]}),
            'row_limit': 10,
            'remainder_label': 'Other holdings',
        })
    _get_or_create(
        DisplaySpec, firm_id=firm.id, dataset_id=positions.id, code='by-asset-class',
        defaults={
            'name': 'By asset class',
            'group_by': json.dumps([{'field_id': _field_id(positions, 'ASSET_CLASS'),
                                     'sort': 'desc', 'show_subtotal': True}]),
            'sort_by': json.dumps([
                {'field_id': _field_id(positions, 'WEIGHT_PCT'), 'direction': 'desc'}]),
            'totals': json.dumps({'grand_total': True,
                                  'fields': [_field_id(positions, 'WEIGHT_PCT')]}),
        })
    _get_or_create(
        DisplaySpec, firm_id=firm.id, dataset_id=returns.id, code='periods',
        defaults={'name': 'Returns by period'})

    db_session.commit()
    return True
