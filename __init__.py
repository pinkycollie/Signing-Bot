"""
Sign Language Video Platform - Flask Application
"""
import logging
import os
from typing import Optional

from flask import Flask, g, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='flask_app.log'
)

# Create base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy without binding to a specific Flask app
db = SQLAlchemy(model_class=Base)

def create_app(test_config: Optional[dict] = None) -> Flask:
    """
    Create and configure the Flask application.
    
    Args:
        test_config: Configuration for testing
        
    Returns:
        Configured Flask application
    """
    # Create the Flask application
    app = Flask(__name__, instance_relative_config=True)
    
    # Configure default settings
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('FLASK_SECRET_KEY', 'dev-key-change-in-production'),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:///app.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            'pool_recycle': 300,
            'pool_pre_ping': True
        },
        UPLOAD_FOLDER=os.path.join(app.static_folder, 'uploads'),
        NOTION_CLIENT_ID=os.environ.get('NOTION_CLIENT_ID'),
        NOTION_CLIENT_SECRET=os.environ.get('NOTION_CLIENT_SECRET')
    )
    
    # Override config with test config if provided
    if test_config:
        app.config.update(test_config)
    
    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    
    # Create database tables
    with app.app_context():
        # Import models to register them with SQLAlchemy
        from app.models.user import User
        from app.models.video import Video, VideoValidation
        from app.models.content import NotionWorkspace, NotionPage, NotionPagePurchase
        
        # Create tables
        db.create_all()
    
    # User loader
    @app.before_request
    def load_logged_in_user():
        """Load user data if user is logged in."""
        user_id = session.get('user_id')
        
        if user_id is None:
            g.user = None
        else:
            from app.models.user import User
            g.user = db.session.query(User).filter(User.id == user_id).first()
    
    # Close database connection
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """Remove the database session at the end of the request."""
        db.session.remove()
    
    # Register error handlers
    @app.errorhandler(403)
    def forbidden(e):
        """Handle 403 Forbidden errors."""
        return {
            'error': 'Forbidden',
            'message': 'You do not have access to this resource'
        }, 403
    
    # Register blueprints
    from app.routes import auth, main, sign_to_earn, notion_integration, widget, business_chatbot
    
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(sign_to_earn.bp)
    app.register_blueprint(notion_integration.bp)
    app.register_blueprint(widget.bp)
    app.register_blueprint(business_chatbot.bp)
    
    # Define routes at the app level
    @app.route('/health')
    def health_check():
        """Health check endpoint."""
        return {'status': 'healthy'}, 200
    
    return app