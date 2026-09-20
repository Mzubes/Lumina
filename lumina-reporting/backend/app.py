import click
from flask import Flask, jsonify
from flask_cors import CORS

from database import configure_database, db_session, init_db, shutdown_session
from migrate_workflow_diagrams import migrate_workflow_diagrams
from models import User, WorkflowGroup, WorkflowGroupMembership
from roles import SYSTEM_ROLES
from seed_demo import seed_demo
from routes.activity import activity_blueprint
from routes.ai_assistant import ai_blueprint
from routes.auth import auth_blueprint
from routes.book import book_blueprint
from routes.clients import clients_blueprint
from routes.dashboard import dashboard_blueprint
from routes.data_hub import data_hub_blueprint
from routes.data_sources import data_sources_blueprint
from routes.disclosures import disclosures_blueprint
from routes.portfolio import portfolio_blueprint
from routes.public import public_blueprint
from routes.reports import reports_blueprint
from routes.templates import templates_blueprint
from routes.triage import triage_blueprint
from routes.users import users_blueprint
from routes.workflow_diagrams import workflow_diagrams_blueprint
from routes.document_templates import document_templates_blueprint
from routes.workflow_groups import workflow_groups_blueprint

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object('config.Config')
    if test_config:
        app.config.update(test_config)

    configure_database(app.config['SQLALCHEMY_DATABASE_URI'])
    init_db()
    app.teardown_appcontext(shutdown_session)
    CORS(app, resources={r'/api/*': {
        'origins': app.config['CORS_ORIGINS'],
        'expose_headers': ['Content-Disposition'],
    }})

    app.register_blueprint(activity_blueprint)
    app.register_blueprint(ai_blueprint)
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(book_blueprint)
    app.register_blueprint(dashboard_blueprint)
    app.register_blueprint(data_hub_blueprint)
    app.register_blueprint(data_sources_blueprint)
    app.register_blueprint(clients_blueprint)
    app.register_blueprint(reports_blueprint)
    app.register_blueprint(templates_blueprint)
    app.register_blueprint(triage_blueprint)
    app.register_blueprint(portfolio_blueprint)
    app.register_blueprint(disclosures_blueprint)
    app.register_blueprint(public_blueprint)
    app.register_blueprint(users_blueprint)
    app.register_blueprint(workflow_diagrams_blueprint)
    app.register_blueprint(workflow_groups_blueprint)
    app.register_blueprint(document_templates_blueprint)

    @app.get('/api/health')
    def health():
        return jsonify({'status': 'ok'})

    @app.cli.command('create-user')
    @click.option('--email', prompt=True)
    @click.option('--role', type=click.Choice(sorted(SYSTEM_ROLES)), default='admin')
    @click.option('--client-id', type=int, default=None, help="Required when --role client.")
    @click.option(
        '--group', 'group_names', multiple=True,
        help="Workflow group to add this user to (repeatable). Created if it doesn't already exist.",
    )
    @click.password_option()
    def create_user(email, role, client_id, group_names, password):
        normalized_email = email.strip().lower()
        if role == 'client' and client_id is None:
            raise click.ClickException('--client-id is required when --role client.')
        if db_session.query(User).filter_by(email=normalized_email).first():
            raise click.ClickException('A user with that email already exists.')
        user = User(email=normalized_email, client_id=client_id, role=role)
        user.set_password(password)
        db_session.add(user)
        db_session.flush()
        for name in group_names:
            group = db_session.query(WorkflowGroup).filter_by(name=name).first()
            if not group:
                group = WorkflowGroup(name=name, created_by=user.id)
                db_session.add(group)
                db_session.flush()
            db_session.add(WorkflowGroupMembership(user_id=user.id, group_id=group.id))
        db_session.commit()
        group_note = f" (groups: {', '.join(group_names)})" if group_names else ''
        click.echo(f'Created {role} user {normalized_email}{group_note}.')

    @app.cli.command('seed-demo')
    def seed_demo_command():
        """Seed a reverse-engineered Pzena factsheet, distributed end-to-end,
        plus admin/editor/compliance/client demo logins. Safe to re-run."""
        if seed_demo():
            click.echo(
                'Seeded demo data. Logins (all @lumina.test): '
                'admin/admin-pass, editor/editor-pass, compliance/compliance-pass, '
                'client/client-pass.'
            )
        else:
            click.echo('Demo data already present -- nothing to do.')

    @app.cli.command('migrate-workflow-diagrams')
    @click.option('--dry-run', is_flag=True, default=False, help='Report what would change without committing.')
    def migrate_workflow_diagrams_command(dry_run):
        """One-off rollout command: generates an auto-equivalent workflow
        diagram for every existing template that doesn't already have one,
        migrates any role='compliance' users to a 'Compliance' workflow
        group + role='editor', and pins existing reports to their
        template's new diagram. Safe to re-run -- a template that already
        has an active diagram is left untouched."""
        summary = migrate_workflow_diagrams(dry_run=dry_run)
        prefix = '[dry run] ' if dry_run else ''
        click.echo(
            f"{prefix}Migrated {summary['compliance_users_migrated']} compliance user(s), "
            f"rewrote {summary['components_rewritten']} component review reference(s), "
            f"generated diagrams for {summary['templates_migrated']} template(s), "
            f"backfilled {summary['reports_backfilled']} report(s)."
        )

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=app.config.get('DEBUG', False))
