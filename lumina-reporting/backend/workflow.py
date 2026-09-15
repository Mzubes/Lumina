from database import db_session
from models import ReportTransition

class InvalidTransition(Exception):
    pass

# Client/prospect-facing content routes through Compliance before it can be
# approved; internal-only report types skip straight to approved, same as
# before this stage existed.
COMPLIANCE_REQUIRED_TYPES = {'factsheet', 'marketing', 'pitchbook', 'meeting_pack'}

def requires_compliance(report):
    return report.report_type in COMPLIANCE_REQUIRED_TYPES

TRANSITIONS = {
    ('draft', 'submit'): 'review',
    ('review', 'reject'): 'draft',
    ('compliance', 'certify'): 'approved',
    ('compliance', 'request_changes'): 'draft',
    ('approved', 'distribute'): 'distributed',
    # ('review', 'approve') is resolved dynamically in apply_transition,
    # since its destination depends on the report's own report_type.
}

def apply_transition(report, action, actor_id, note=None):
    if (report.status, action) == ('review', 'approve'):
        target = 'compliance' if requires_compliance(report) else 'approved'
    else:
        target = TRANSITIONS.get((report.status, action))

    if target is None:
        raise InvalidTransition(f"Cannot {action} a report in status '{report.status}'")

    from_status = report.status
    report.status = target
    db_session.add(ReportTransition(
        report_id=report.id,
        from_status=from_status,
        to_status=report.status,
        actor_id=actor_id,
        note=note,
    ))
    db_session.commit()
    return report
