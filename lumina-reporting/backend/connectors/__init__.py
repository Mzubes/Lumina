from connectors import api_connector, snowflake_connector

CONNECTORS = {
    'snowflake': snowflake_connector.sync,
    'api': api_connector.sync,
}
