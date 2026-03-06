"""
Utility functions for the ASL Customer Support application.
"""

import os
import uuid
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from flask import session, g, current_app
from werkzeug.utils import secure_filename

from app import db
from app.models_deaf_service import (
    User, UserRole, ServiceProvider, VideoSubmissionStatus
)

logger = logging.getLogger(__name__)

# Valid file extensions for uploads
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov', 'avi'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'ogg', 'm4a'}
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}


def get_current_user() -> Optional[User]:
    """
    Get the current authenticated user from the session.
    
    Returns:
        User object if authenticated, None otherwise
    """
    if "replit_user" not in session:
        return None
    
    # Try to get user from cache
    if hasattr(g, 'user'):
        return g.user
    
    replit_user = session["replit_user"]
    user = db.session.query(User).filter_by(replit_id=replit_user["id"]).first()
    
    if user:
        # Store in request context
        g.user = user
        return user
    
    return None


def get_or_create_user(replit_user: Dict[str, Any]) -> User:
    """
    Get or create a user from Replit user data.
    
    Args:
        replit_user: Replit user data from the session
        
    Returns:
        User object
    """
    # Check if user exists
    user = db.session.query(User).filter_by(replit_id=replit_user["id"]).first()
    
    if user:
        # Update user information
        user.username = replit_user.get("username", user.username)
        user.display_name = replit_user.get("name", user.display_name)
        user.email = replit_user.get("email", user.email)
        user.profile_image = replit_user.get("profile_image", user.profile_image)
        db.session.commit()
        return user
    
    # Create new user
    user = User(
        replit_id=replit_user["id"],
        username=replit_user.get("username", f"user_{replit_user['id']}"),
        display_name=replit_user.get("name"),
        email=replit_user.get("email"),
        profile_image=replit_user.get("profile_image"),
        role=UserRole.USER
    )
    
    db.session.add(user)
    db.session.commit()
    
    return user


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """
    Check if a file has an allowed extension.
    
    Args:
        filename: The filename to check
        allowed_extensions: Set of allowed extensions
        
    Returns:
        Boolean indicating if the file is allowed
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def save_uploaded_file(file, directory: str, allowed_extensions: set) -> Tuple[bool, str]:
    """
    Save an uploaded file.
    
    Args:
        file: File object from request.files
        directory: Directory to save the file
        allowed_extensions: Set of allowed extensions
        
    Returns:
        Tuple of (success, file_path or error_message)
    """
    if not file:
        return False, "No file provided"
    
    if file.filename == '':
        return False, "No file selected"
    
    if not allowed_file(file.filename, allowed_extensions):
        return False, f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
    
    try:
        # Create a unique filename
        filename = secure_filename(file.filename)
        filename = f"{uuid.uuid4()}_{filename}"
        
        # Create directory if it doesn't exist
        os.makedirs(directory, exist_ok=True)
        
        # Save the file
        file_path = os.path.join(directory, filename)
        file.save(file_path)
        
        # Return relative path from static folder
        rel_path = os.path.relpath(file_path, current_app.static_folder)
        return True, rel_path
        
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        return False, f"Error saving file: {str(e)}"


def init_default_data() -> None:
    """
    Initialize default data in the database.
    
    This function creates default service providers if they don't exist.
    """
    try:
        # Create default service providers
        providers = [
            {
                "name": "Purple Communications",
                "description": "Video relay and text services for deaf and hard-of-hearing individuals.",
                "logo": "images/purple_logo.svg",
                "url": "https://purplevrs.com"
            },
            {
                "name": "Sorenson Communications",
                "description": "Video relay services and videophone technology for the deaf community.",
                "logo": "images/sorenson_logo.svg",
                "url": "https://www.sorensonvrs.com"
            },
            {
                "name": "Convo",
                "description": "Deaf-owned and operated video relay service (VRS) provider.",
                "logo": "images/convos_logo.svg",
                "url": "https://www.convorelay.com"
            }
        ]
        
        for provider_data in providers:
            provider = db.session.query(ServiceProvider).filter_by(name=provider_data["name"]).first()
            
            if not provider:
                provider = ServiceProvider(
                    name=provider_data["name"],
                    description=provider_data["description"],
                    logo=provider_data["logo"],
                    url=provider_data["url"],
                    is_active=True
                )
                db.session.add(provider)
        
        db.session.commit()
        logger.info("Default data initialized successfully")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error initializing default data: {str(e)}")


def format_datetime(dt: datetime, format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
    """
    Format a datetime object as a string.
    
    Args:
        dt: Datetime object
        format_str: Format string
        
    Returns:
        Formatted datetime string
    """
    if not dt:
        return ""
    
    return dt.strftime(format_str)


def get_file_size_display(size_bytes: int) -> str:
    """
    Convert file size in bytes to a human-readable format.
    
    Args:
        size_bytes: File size in bytes
        
    Returns:
        Human-readable file size
    """
    if not size_bytes:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024
        i += 1
    
    return f"{size_bytes:.2f} {units[i]}"