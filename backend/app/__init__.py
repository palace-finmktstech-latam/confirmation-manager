# backend/app/__init__.py
from flask import Flask
from flask_cors import CORS
from .config import Config

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    CORS(app)
    
    # Import and register routes - do this inside function to avoid circular imports
    from .api.endpoints import emails
    app.register_blueprint(emails.emails)
    
    return app