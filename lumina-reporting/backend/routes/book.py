import datetime

from flask import Blueprint, jsonify

from database import db_session
from models import Client, Holding, PerformanceSnapshot, Report
from routes.auth import require_auth
import workflow_engine

book_blueprint = Blueprint('book', __name__)

def _client_aum(client_id):
    latest_date = (
        db_session.query(Holding.as_of_date)
        .filter_by(client_id=client_id)
        .order_by(Holding.as_of_date.desc())
        .limit(1)
        .scalar()
    )
    if not latest_date:
        return None, None
    total = (
        db_session.query(Holding)
        .filter_by(client_id=client_id, as_of_date=latest_date)
        .with_entities(Holding.market_value)
        .all()
    )
    return sum(float(row[0]) for row in total), latest_date

def _client_latest_performance(client_id):
    # Prefer YTD when it exists (the figure a relationship manager actually
    # reports on), otherwise whatever period is most recently on file.
    snapshots = (
        db_session.query(PerformanceSnapshot)
        .filter_by(client_id=client_id)
        .order_by(PerformanceSnapshot.as_of_date.desc())
        .all()
    )
    if not snapshots:
        return None
    ytd = next((s for s in snapshots if s.period_type == 'YTD'), None)
    return ytd or snapshots[0]

def _client_last_report(client_id):
    return (
        db_session.query(Report)
        .filter_by(client_id=client_id)
        .order_by(Report.updated_at.desc())
        .first()
    )

@book_blueprint.get('/api/book')
@require_auth(roles=['admin', 'editor', 'viewer'])
def get_book():
    """Aggregate 'book of business' view across every client -- there's no
    per-relationship-manager territory concept in the data model yet, so
    this is the firm's whole book, not a filtered-to-caller one; scoping it
    to an individual RM is a natural follow-up once that assignment exists.
    """
    clients = db_session.query(Client).order_by(Client.name.asc()).all()
    now = datetime.datetime.utcnow()

    total_aum = 0.0
    underperforming = 0
    reports_mtd = 0
    rows = []

    for client in clients:
        aum, as_of = _client_aum(client.id)
        performance = _client_latest_performance(client.id)
        last_report = _client_last_report(client.id)

        return_pct = float(performance.return_pct) if performance and performance.return_pct is not None else None
        benchmark_pct = (
            float(performance.benchmark_return_pct)
            if performance and performance.benchmark_return_pct is not None else None
        )
        is_underperforming = (
            return_pct is not None and benchmark_pct is not None and return_pct < benchmark_pct
        )
        if is_underperforming:
            underperforming += 1
        if aum:
            total_aum += aum

        if (
            last_report and workflow_engine.report_is_distributed(last_report)
            and last_report.updated_at and last_report.updated_at.year == now.year
            and last_report.updated_at.month == now.month
        ):
            reports_mtd += 1

        rows.append({
            'client': client.serialize(),
            'aum': aum,
            'asOfDate': as_of.isoformat() if as_of else None,
            'performance': {
                'periodType': performance.period_type if performance else None,
                'returnPct': return_pct,
                'benchmarkReturnPct': benchmark_pct,
                'isUnderperforming': is_underperforming,
            } if performance else None,
            'lastReport': {
                'id': last_report.id,
                'title': last_report.title,
                'status': last_report.status,
                'updatedAt': last_report.updated_at.isoformat() if last_report.updated_at else None,
                'isDistributed': workflow_engine.report_is_distributed(last_report),
            } if last_report else None,
        })

    # Highest AUM first -- an RM's most important relationships belong at
    # the top of their book, same convention as ReportsTable's default sort.
    rows.sort(key=lambda row: row['aum'] or 0, reverse=True)

    return jsonify({
        'totalAum': total_aum,
        'clientCount': len(clients),
        'underperformingCount': underperforming,
        'reportsDeliveredMtd': reports_mtd,
        'clients': rows,
    })

@book_blueprint.get('/api/book/<int:client_id>')
@require_auth(roles=['admin', 'editor', 'viewer'])
def get_book_client(client_id):
    """Drill-down for one client: full holdings + performance history,
    plus every report on file for them -- the data behind a book row's
    expand."""
    client = db_session.query(Client).filter_by(id=client_id).first()
    if not client:
        return jsonify({'message': 'Client not found'}), 404

    aum, as_of = _client_aum(client_id)
    holdings = (
        db_session.query(Holding).filter_by(client_id=client_id, as_of_date=as_of).all()
        if as_of else []
    )
    holdings.sort(key=lambda h: float(h.weight_pct or 0), reverse=True)

    snapshots = (
        db_session.query(PerformanceSnapshot)
        .filter_by(client_id=client_id)
        .order_by(PerformanceSnapshot.as_of_date.desc())
        .all()
    )
    latest_by_period = {}
    for snapshot in snapshots:
        latest_by_period.setdefault(snapshot.period_type, snapshot)

    reports = (
        db_session.query(Report)
        .filter_by(client_id=client_id)
        .order_by(Report.updated_at.desc())
        .limit(10)
        .all()
    )

    return jsonify({
        'client': client.serialize(),
        'aum': aum,
        'asOfDate': as_of.isoformat() if as_of else None,
        'holdings': [holding.serialize() for holding in holdings[:10]],
        'performance': [snapshot.serialize() for snapshot in latest_by_period.values()],
        'reports': [
            {
                'id': report.id, 'title': report.title, 'status': report.status,
                'updatedAt': report.updated_at.isoformat() if report.updated_at else None,
                'isDistributed': workflow_engine.report_is_distributed(report),
            }
            for report in reports
        ],
    })
