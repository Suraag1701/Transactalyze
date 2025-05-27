import os
from flask import Flask
from uuid import uuid4
from datetime import timedelta
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def create_app():
    base_dir = os.path.abspath(os.path.dirname(__file__))
    template_dir = os.path.join(base_dir, "..",
                                "templates")  # Go up one level to root
    static_dir = os.path.join(base_dir, "..",
                              "static")  # Go up one level to root

    app = Flask(__name__,
                template_folder=template_dir,
                static_folder=static_dir)
    app.secret_key = str(uuid4())
    app.config['PROCESSED_FILES'] = {}

    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    app.permanent_session_lifetime = timedelta(hours=3)
    app.config['HASHED_RESULTS'] = {}  # Stores hash -> output

    limiter = Limiter(get_remote_address,
                      app=app,
                      default_limits=[])

    return app
