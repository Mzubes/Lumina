from flask import Flask
from routes.auth import auth_blueprint
from routes.data_hub import data_hub_blueprint
from routes.reports import reports_blueprint
from routes.approvals import approvals_blueprint
from routes.distribution import distribution_blueprint

app = Flask(__name__)

# Register blueprints (modular routing)
app.register_blueprint(auth_blueprint)
app.register_blueprint(data_hub_blueprint)
app.register_blueprint(reports_blueprint)
app.register_blueprint(approvals_blueprint)
app.register_blueprint(distribution_blueprint)

if __name__ == '__main__':
    app.run(debug=True)
