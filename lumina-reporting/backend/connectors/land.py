from database import db_session
from models import Holding, PerformanceSnapshot
from connectors.errors import ConnectorError

def map_rows(raw_rows, column_map):
    """Map a connector's raw records (source column name -> value) to our
    target field names, using the business-user-authored column_map
    (a list of {source_column, target_field} pairs)."""
    mapping = {entry['source_column']: entry['target_field'] for entry in column_map}
    mapped_rows = []
    for raw_row in raw_rows:
        mapped_row = {}
        for source_column, value in raw_row.items():
            target_field = mapping.get(source_column)
            if target_field:
                mapped_row[target_field] = value
        mapped_rows.append(mapped_row)
    return mapped_rows

def replace_holdings(rows, client_id, fund_id, as_of_date, source_id):
    """Delete-and-replace so a re-sync for the same (client, fund, date)
    is idempotent rather than accumulating duplicates."""
    db_session.query(Holding).filter_by(
        client_id=client_id, fund_id=fund_id, as_of_date=as_of_date,
    ).delete()
    created = []
    for row in rows:
        if not row.get('security_id') or row.get('market_value') is None:
            raise ConnectorError(f"Holding row missing required security_id/market_value: {row}")
        holding = Holding(
            client_id=client_id,
            fund_id=fund_id,
            as_of_date=as_of_date,
            security_id=row['security_id'],
            security_name=row.get('security_name'),
            asset_class=row.get('asset_class'),
            quantity=row.get('quantity'),
            market_value=row['market_value'],
            currency=row.get('currency') or 'USD',
            weight_pct=row.get('weight_pct'),
            source_id=source_id,
        )
        db_session.add(holding)
        created.append(holding)
    db_session.commit()
    return created

def replace_performance(rows, client_id, fund_id, as_of_date, source_id):
    db_session.query(PerformanceSnapshot).filter_by(
        client_id=client_id, fund_id=fund_id, as_of_date=as_of_date,
    ).delete()
    created = []
    for row in rows:
        if not row.get('period_type') or row.get('return_pct') is None:
            raise ConnectorError(f"Performance row missing required period_type/return_pct: {row}")
        snapshot = PerformanceSnapshot(
            client_id=client_id,
            fund_id=fund_id,
            as_of_date=as_of_date,
            period_type=row['period_type'],
            return_pct=row['return_pct'],
            benchmark_return_pct=row.get('benchmark_return_pct'),
            source_id=source_id,
        )
        db_session.add(snapshot)
        created.append(snapshot)
    db_session.commit()
    return created
