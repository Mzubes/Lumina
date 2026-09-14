import datetime
import re

import snowflake.connector

from connectors.errors import ConnectorError
from connectors.land import map_rows, replace_holdings, replace_performance

IDENTIFIER_PATTERN = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

def _validate_identifier(value, field_name):
    # Table/column names can't be bound as query parameters, so they're
    # checked against a strict allowlist before ever reaching a query
    # string. The data-source route validates these at save time too;
    # this is defense in depth for any DataSource created another way.
    if not value or not IDENTIFIER_PATTERN.match(value):
        raise ConnectorError(f"Invalid {field_name}: {value!r}")
    return value

def sync(data_source, client_id, fund_id=None, as_of_date=None):
    as_of_date = as_of_date or datetime.date.today()
    config = data_source.config_dict()

    schema = _validate_identifier(config.get('schema'), 'schema')
    holdings_table = _validate_identifier(config.get('holdings_table'), 'holdings_table')
    performance_table = _validate_identifier(config.get('performance_table'), 'performance_table')
    client_column = _validate_identifier(config.get('client_column'), 'client_column')
    column_map = config.get('column_map') or []

    try:
        connection = snowflake.connector.connect(
            account=config.get('account'),
            user=config.get('user'),
            password=config.get('password'),
            warehouse=config.get('warehouse'),
            database=config.get('database'),
            schema=schema,
            role=config.get('role'),
        )
    except Exception as error:
        raise ConnectorError(f"Could not connect to Snowflake: {error}") from error

    try:
        cursor = connection.cursor(snowflake.connector.DictCursor)
        try:
            cursor.execute(
                f"SELECT * FROM {schema}.{holdings_table} WHERE {client_column} = %(client_ref)s",
                {'client_ref': client_id},
            )
            raw_holdings = cursor.fetchall()

            cursor.execute(
                f"SELECT * FROM {schema}.{performance_table} WHERE {client_column} = %(client_ref)s",
                {'client_ref': client_id},
            )
            raw_performance = cursor.fetchall()
        finally:
            cursor.close()
    except Exception as error:
        raise ConnectorError(f"Snowflake query failed: {error}") from error
    finally:
        connection.close()

    holdings = replace_holdings(
        map_rows(raw_holdings, column_map), client_id, fund_id, as_of_date, data_source.id,
    )
    performance = replace_performance(
        map_rows(raw_performance, column_map), client_id, fund_id, as_of_date, data_source.id,
    )

    return {'holdings_count': len(holdings), 'performance_count': len(performance)}
