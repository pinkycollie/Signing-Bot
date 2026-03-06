"""
Database initialization and session management for the ASL Customer Support application.
"""

import logging
from typing import Any
from flask import current_app, g
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, Session

from app import db

# Set up logging
logger = logging.getLogger(__name__)

def get_db() -> Session:
    """
    Get a database session.
    
    Returns:
        SQLAlchemy session
    """
    if "db" not in g:
        g.db = db.session
    
    return g.db

def init_db() -> None:
    """
    Initialize the database - create all tables.
    """
    logger.info("Initializing database tables")
    
    try:
        with current_app.app_context():
            db.create_all()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def shutdown_db() -> None:
    """
    Close the database session.
    """
    if hasattr(g, "db"):
        g.db.close()
        logger.debug("Database session closed")