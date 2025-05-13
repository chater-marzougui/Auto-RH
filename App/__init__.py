import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from celery import Celery

from config import config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
socketio = SocketIO(cors_allowed_origins="*")
celery = Celery(__name__)

def create_app(config_name='default'):
    """Application factory function."""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config.config[config_name])
    
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    socketio.init_app(app)
    
    # Configure Celery
    celery.conf.update(app.config)
    
    # Register blueprints
    from app.routes.auth import auth_bp as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/api/auth')
    
    from app.routes.user import user as user_blueprint
    app.register_blueprint(user_blueprint, url_prefix='/api/user')
    
    from app.routes.entreprise import enterprise_bp as enterprise_blueprint
    app.register_blueprint(enterprise_blueprint, url_prefix='/api/enterprise')
    
    from app.routes.interview import interview as interview_blueprint
    app.register_blueprint(interview_blueprint, url_prefix='/api/interview')
    
    from app.routes.dashboard import dashboard as dashboard_blueprint
    app.register_blueprint(dashboard_blueprint, url_prefix='/api/dashboard')
    
    from app.routes.job import job as job_blueprint
    app.register_blueprint(job_blueprint, url_prefix='/api/job')
    
    from app.routes.careur import career as career_blueprint
    app.register_blueprint(career_blueprint, url_prefix='/api/career')
    
    # Register main blueprint for home routes
    from app.routes.main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # Register error handlers
    register_error_handlers(app)
    
    # Initialize Socket.IO events
    from app.sockets import initialize_sockets
    initialize_sockets(socketio)
    
    return app

def register_error_handlers(app):
    """Register error handlers for the application."""
    @app.errorhandler(404)
    def not_found(error):
        return {"error": "Not Found"}, 404
    
    @app.errorhandler(400)
    def bad_request(error):
        return {"error": "Bad Request"}, 400
    
    @app.errorhandler(500)
    def internal_server_error(error):
        return {"error": "Internal Server Error"}, 500

# Make Celery work with Flask app context
class FlaskCelery(Celery):
    def __init__(self, *args, **kwargs):
        super(FlaskCelery, self).__init__(*args, **kwargs)
        self.app = None
        
    def init_app(self, app):
        self.app = app
        self.conf.update(app.config)
        
        class ContextTask(self.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        
        self.Task = ContextTask
        
        # Update Celery config
        self.conf.update(
            broker_url=app.config['CELERY_BROKER_URL'],
            result_backend=app.config['CELERY_RESULT_BACKEND']
        )