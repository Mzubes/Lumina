# The system-role vocabulary (permissions within the app), kept separate from
# workflow groups (models.WorkflowGroup -- who does the next step of
# production work). 'compliance' is deliberately not a system role: it's an
# ordinary, optional, firm-created workflow group like any other, so a firm
# without a formal compliance function isn't forced to have one.
#
# Not yet wired into app.py's CLI / routes/users.py's VALID_ROLES / the test
# fixtures -- those still accept the legacy 'compliance' role until the
# `flask migrate-workflow-diagrams` rollout command (which rewrites existing
# role='compliance' users to 'editor' + Compliance-group membership) has run,
# so an existing compliance user can't be locked out of an unrelated profile
# edit mid-rollout by a vocabulary that no longer accepts their current role.
SYSTEM_ROLES = {'admin', 'editor', 'viewer', 'client'}
