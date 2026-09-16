# The system-role vocabulary (permissions within the app), kept separate from
# workflow groups (models.WorkflowGroup -- who does the next step of
# production work). 'compliance' is deliberately not a system role: it's an
# ordinary, optional, firm-created workflow group like any other, so a firm
# without a formal compliance function isn't forced to have one.
#
# A deployment upgrading from before this change must run
# `flask migrate-workflow-diagrams` (which rewrites any existing
# role='compliance' users to 'editor' + Compliance-group membership) before
# or immediately after picking up this code, so no user is left with a role
# this vocabulary no longer accepts.
SYSTEM_ROLES = {'admin', 'editor', 'viewer', 'client'}
