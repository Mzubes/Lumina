from database import db_session
from models import ReportTransition

class InvalidTransition(Exception):
    pass

TRANSITIONS = {
    ('draft', 'submit'): 'review',
    ('review', 'approve'): 'approved',
    ('review', 'reject'): 'draft',
    ('approved', 'distribute'): 'distributed',
}

def apply_transition(report, action, actor_id, note=None):
    key = (report.status, action)
    if key not in TRANSITIONS:
        raise InvalidTransition(f"Cannot {action} a report in status '{report.status}'")
    from_status = report.status
    report.status = TRANSITIONS[key]
    db_session.add(ReportTransition(
        report_id=report.id,
        from_status=from_status,
        to_status=report.status,
        actor_id=actor_id,
        note=note,
    ))
    db_session.commit()
    return report
