import datetime

from database import db_session
from models import Client, Holding, PerformanceSnapshot, Report, ReportTemplate

def _scoped(query, report):
    query = query.filter_by(client_id=report.client_id)
    if report.fund_id is not None:
        query = query.filter_by(fund_id=report.fund_id)
    return query

def _resolve_holdings_table(report, component):
    filters = component.get('data_binding', {}).get('filters', {})
    base_query = _scoped(db_session.query(Holding), report)

    as_of = filters.get('as_of', 'latest')
    if as_of == 'latest':
        latest_date = (
            base_query.with_entities(Holding.as_of_date)
            .order_by(Holding.as_of_date.desc())
            .limit(1)
            .scalar()
        )
        rows = base_query.filter_by(as_of_date=latest_date).all() if latest_date else []
    else:
        rows = base_query.filter_by(as_of_date=datetime.date.fromisoformat(as_of)).all()

    table_rows = [
        [
            holding.security_name or holding.security_id,
            holding.asset_class or '',
            float(holding.quantity) if holding.quantity is not None else '',
            float(holding.market_value),
            float(holding.weight_pct) if holding.weight_pct is not None else '',
        ]
        for holding in rows
    ]
    return {
        'type': 'holdings_table',
        'title': component.get('title', 'Holdings'),
        'columns': ['Security', 'Asset Class', 'Quantity', 'Market Value', 'Weight %'],
        'rows': table_rows,
    }

def _resolve_performance_summary(report, component):
    filters = component.get('data_binding', {}).get('filters', {})
    period_types = filters.get('period_types')

    query = _scoped(db_session.query(PerformanceSnapshot), report)
    if period_types:
        query = query.filter(PerformanceSnapshot.period_type.in_(period_types))
    snapshots = query.order_by(PerformanceSnapshot.as_of_date.desc()).all()

    latest_by_period = {}
    for snapshot in snapshots:
        latest_by_period.setdefault(snapshot.period_type, snapshot)

    table_rows = [
        [
            period,
            float(snapshot.return_pct),
            float(snapshot.benchmark_return_pct) if snapshot.benchmark_return_pct is not None else '',
        ]
        for period, snapshot in latest_by_period.items()
    ]
    return {
        'type': 'performance_summary',
        'title': component.get('title', 'Performance'),
        'columns': ['Period', 'Return %', 'Benchmark %'],
        'rows': table_rows,
    }

def _resolve_text_block(report, component):
    return {
        'type': 'text_block',
        'title': component.get('title', 'Commentary'),
        'text': component.get('data_binding', {}).get('static_text', ''),
    }

def _placeholder(title, text):
    return [{'type': 'text_block', 'title': title, 'text': text}]

def _resolve_referenced_components(referenced_report, referenced_template):
    """Resolve the referenced report's own components against ITS data. One
    level of inlining only -- a referenced report's own report_reference
    components (if any) become a placeholder rather than recursing, so a
    cycle can't be constructed and a deck can't balloon arbitrarily deep."""
    inlined = []
    for inner_component in referenced_template.components_list():
        inner_type = inner_component.get('type')
        if inner_type == 'report_reference':
            inlined.extend(_placeholder(
                inner_component.get('title', 'Referenced report'),
                '[Nested report references are not supported]',
            ))
            continue
        resolver = RESOLVERS.get(inner_type)
        if resolver:
            inlined.append(resolver(referenced_report, inner_component))
    return inlined

def _resolve_report_reference(report, component):
    data_binding = component.get('data_binding', {})
    referenced_id = data_binding.get('report_id')
    fallback_title = component.get('title', 'Referenced report')

    referenced_report = db_session.query(Report).filter_by(id=referenced_id).first()
    if not referenced_report or referenced_report.client_id != report.client_id:
        return _placeholder(fallback_title, '[Referenced report not found or not accessible]')
    if not referenced_report.template_id:
        return _placeholder(fallback_title, '[Referenced report has no structured content]')

    referenced_template = db_session.query(ReportTemplate).filter_by(id=referenced_report.template_id).first()
    if not referenced_template:
        return _placeholder(fallback_title, '[Referenced report template no longer exists]')

    return _resolve_referenced_components(referenced_report, referenced_template)

RESOLVERS = {
    'holdings_table': _resolve_holdings_table,
    'performance_summary': _resolve_performance_summary,
    'text_block': _resolve_text_block,
    'report_reference': _resolve_report_reference,
}

def resolve_report_content(report, template):
    client = db_session.query(Client).filter_by(id=report.client_id).first()
    components = []
    for component in template.components_list():
        resolver = RESOLVERS.get(component.get('type'))
        if not resolver:
            continue
        result = resolver(report, component)
        if isinstance(result, list):
            components.extend(result)
        else:
            components.append(result)
    return {
        'report_title': report.title,
        'client_name': client.name if client else None,
        'generated_at': datetime.datetime.utcnow().isoformat(),
        'components': components,
    }
