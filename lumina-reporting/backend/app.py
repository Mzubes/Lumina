import click
from flask import Flask, jsonify
from flask_cors import CORS

from database import configure_database, db_session, init_db, shutdown_session
from models import User
from routes.auth import auth_blueprint
from routes.clients import clients_blueprint
from routes.dashboard import dashboard_blueprint
from routes.data_hub import data_hub_blueprint
from routes.data_sources import data_sources_blueprint
from routes.disclosures import disclosures_blueprint
from routes.portfolio import portfolio_blueprint
from routes.reports import reports_blueprint
from routes.templates import templates_blueprint

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

    app.register_blueprint(auth_blueprint)
    app.register_blueprint(dashboard_blueprint)
    app.register_blueprint(data_hub_blueprint)
    app.register_blueprint(data_sources_blueprint)
    app.register_blueprint(clients_blueprint)
    app.register_blueprint(reports_blueprint)
    app.register_blueprint(templates_blueprint)
    app.register_blueprint(portfolio_blueprint)
    app.register_blueprint(disclosures_blueprint)

    @app.get('/api/health')
    def health():
        return jsonify({'status': 'ok'})

    @app.cli.command('create-user')
    @click.option('--email', prompt=True)
    @click.option('--role', type=click.Choice(['admin', 'editor', 'viewer', 'client', 'compliance']), default='admin')
    @click.option('--client-id', type=int, default=None, help="Required when --role client.")
    @click.password_option()
    def create_user(email, role, client_id, password):
        normalized_email = email.strip().lower()
        if role == 'client' and client_id is None:
            raise click.ClickException('--client-id is required when --role client.')
        if db_session.query(User).filter_by(email=normalized_email).first():
            raise click.ClickException('A user with that email already exists.')
        user = User(email=normalized_email, client_id=client_id, role=role)
        user.set_password(password)
        db_session.add(user)
        db_session.commit()
        click.echo(f'Created {role} user {normalized_email}.')

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=app.config.get('DEBUG', False))
