import os
from flask import Flask
from uuid import uuid4
from datetime import timedelta
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import secrets

db = SQLAlchemy()
login_manager = LoginManager()


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

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)

    app.permanent_session_lifetime = timedelta(hours=3)
    app.config['HASHED_RESULTS'] = {}  # Stores hash -> output

    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", secrets.token_hex(16))
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        from .models import User  # import inside context

        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))

        db.create_all()
    limiter = Limiter(get_remote_address, app=app, default_limits=[])

    return app
