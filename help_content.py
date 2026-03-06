"""
Help Content Module

This module provides a centralized place for storing and managing
help text content used in the contextual help tooltip system.
"""

# Dictionary of help text content keyed by feature identifier
HELP_TEXT = {
    # Home page help
    "home_welcome": "Welcome to our application! This is a simple task management app that helps you organize your items and projects.",
    "home_login": "Click 'Log in with Replit' to access your personalized dashboard. Authentication is handled securely through Replit.",
    
    # Dashboard help
    "recent_projects": "View your most recently created projects. Click 'View All' to see and manage all your projects.",
    "recent_items": "View your most recently created items. Check the box to mark items as complete or incomplete.",
    "ai_suggestions": "These are AI-generated suggestions based on your existing items and projects. Click any suggestion to create a new item.",
    
    # Items page help
    "add_item": "Create a new item by providing a title and optional description. Click 'Add Item' to save it.",
    "item_list": "View all your items here. You can mark items as complete, edit their details, or delete them.",
    "item_status": "Click the checkbox to mark an item as complete or incomplete.",
    "edit_item": "Click the pencil icon to edit an item's title and description.",
    "delete_item": "Click the trash icon to permanently delete an item. This action cannot be undone.",
    
    # Projects page help
    "create_project": "Create a new project by entering a title, description, and selecting a status. Projects help organize related items.",
    "project_list": "View all your projects here. You can filter by status or search for specific projects.",
    "project_title": "Give your project a clear, descriptive title that summarizes its purpose.",
    "project_description": "Provide details about your project's goals, scope, and other relevant information.",
    "project_status": "Set your project's current state: Active (in progress), Completed (finished), or Archived (no longer active).",
    
    # AI Suggestions
    "suggestions": "These are AI-generated suggestions based on your existing items. Click any suggestion to create a new item with that text.",
    "refresh_suggestions": "Click the refresh icon to generate new AI suggestions.",
    
    # Other features
    "navigation": "Use the navigation menu to move between different sections of the application.",
    "logout": "Click 'Log out' to end your session and secure your account.",
    "form_validation": "Fields marked with * are required and must be filled out before submitting the form."
}


def get_help_text(key, default=None):
    """
    Get help text for a specific feature by its key.
    
    Args:
        key: The identifier for the help text
        default: Default text to return if key is not found
        
    Returns:
        The help text string for the given key, or the default
    """
    return HELP_TEXT.get(key, default or f"Help text for '{key}' not found.")