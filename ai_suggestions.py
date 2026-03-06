"""
AI-powered suggestion module for the Flask application.
Provides next action suggestions based on item data.
Supports multiple AI providers (OpenAI, Cursor AI, and local fallbacks).
"""

import os
import random
import json
import requests
from typing import List, Dict, Any, Optional, Union
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check for OpenAI and Cursor AI availability
OPENAI_AVAILABLE = False
OPENAI_CLIENT = None

# Try to import OpenAI
try:
    from openai import OpenAI
    # Only set available if we have a key
    if os.environ.get("OPENAI_API_KEY"):
        OPENAI_AVAILABLE = True
        OPENAI_CLIENT = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    else:
        logger.info("OpenAI package found but no API key available")
except ImportError:
    logger.warning("OpenAI package not found, will try Cursor AI or fallback to default suggestions")

# Define flag for Cursor AI availability
CURSOR_AI_AVAILABLE = os.environ.get("CURSOR_API_KEY") is not None

# Categories for suggestions when OpenAI is not available
FALLBACK_SUGGESTIONS = {
    "productivity": [
        "Break this task into smaller steps",
        "Set a deadline for this item",
        "Share this task with a team member",
        "Schedule focused time for this task",
        "Prioritize this for tomorrow morning",
    ],
    "learning": [
        "Research related topics",
        "Create study notes for this subject",
        "Find a tutorial on this topic",
        "Practice this skill for 30 minutes",
        "Teach someone what you've learned",
    ],
    "health": [
        "Take a short break before starting",
        "Drink water before tackling this task",
        "Stand up and stretch while working on this",
        "Go for a walk after completing this",
        "Set a timer to avoid burnout",
    ],
    "organization": [
        "Create a checklist for this item",
        "Gather all resources needed",
        "Clear your workspace before starting",
        "Document your progress",
        "Archive this when completed",
    ],
}

def get_cursor_ai_suggestions(items_context: str, focus_prompt: str) -> List[str]:
    """
    Generate suggestions using Cursor AI API.
    
    Args:
        items_context: String context of all items
        focus_prompt: The specific prompt for generating suggestions
        
    Returns:
        List of suggestion strings
    """
    try:
        cursor_api_key = os.environ.get("CURSOR_API_KEY")
        if not cursor_api_key:
            return []
            
        cursor_api_url = "https://api.cursor.sh/v1/ai/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {cursor_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "cursor-ai",
            "messages": [
                {"role": "system", "content": "You are a helpful productivity assistant that provides specific, actionable next step suggestions."},
                {"role": "user", "content": f"Here is my to-do list:\n{items_context}\n\n{focus_prompt}"}
            ],
            "max_tokens": 150,
            "temperature": 0.7
        }
        
        response = requests.post(cursor_api_url, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        suggestions_text = result["choices"][0]["message"]["content"]
        suggestions = [s.strip() for s in suggestions_text.split("\n") if s.strip()]
        
        # Clean up suggestions
        cleaned_suggestions = []
        for suggestion in suggestions:
            if suggestion.startswith(("1.", "2.", "3.", "-", "*", "•")):
                suggestion = suggestion[2:].strip()
            suggestion = suggestion.strip('"\'')
            cleaned_suggestions.append(suggestion)
            
        return cleaned_suggestions[:3]
        
    except Exception as e:
        logger.error(f"Error generating Cursor AI suggestions: {e}")
        return []

def prepare_item_context(items: List[Any]) -> str:
    """
    Prepare context from items.
    
    Args:
        items: List of item objects
        
    Returns:
        String context of all items
    """
    # Prepare context from items
    item_descriptions = []
    for item in items:
        # Handle both dictionary and object access patterns
        if isinstance(item, dict):
            status = "completed" if item.get("is_completed") else "pending"
            title = item.get("title", "Untitled")
            description = item.get("description") or "No description"
        else:
            status = "completed" if getattr(item, "is_completed", False) else "pending"
            title = getattr(item, "title", "Untitled")
            description = getattr(item, "description", "No description") or "No description"
            
        item_descriptions.append(f"- {title}: {description} ({status})")
    
    return "\n".join(item_descriptions)

def get_ai_suggestions(items: List[Any], current_item: Optional[Any] = None) -> List[str]:
    """
    Generate AI-powered suggestions for next actions based on items and optionally
    focused on a specific current item.
    
    Args:
        items: List of item objects
        current_item: Optional specific item to generate suggestions for
    
    Returns:
        List of suggestion strings
    """
    # Prepare items context
    items_context = prepare_item_context(items)
    
    # Focus prompt on current item if provided
    if current_item:
        # Handle both dictionary and object access patterns
        if isinstance(current_item, dict):
            title = current_item.get("title", "Untitled")
            description = current_item.get("description") or "No description"
        else:
            title = getattr(current_item, "title", "Untitled")
            description = getattr(current_item, "description", "No description") or "No description"
            
        focus_prompt = f"""
        Based on the user's to-do list, generate 3 helpful and specific next action suggestions 
        for the item "{title}": {description}.
        Make suggestions specific, actionable, and relevant to the item's context.
        Format each suggestion as a short action phrase (5-8 words).
        """
    else:
        focus_prompt = """
        Based on the user's to-do list, generate 3 helpful and specific next action suggestions
        they might want to take. Consider incomplete items as priorities.
        Make suggestions specific, actionable, and relevant to the items' context.
        Format each suggestion as a short action phrase (5-8 words).
        """
    
    # Try Cursor AI first if available
    if CURSOR_AI_AVAILABLE:
        cursor_suggestions = get_cursor_ai_suggestions(items_context, focus_prompt)
        if cursor_suggestions:
            return cursor_suggestions
    
    # Fall back to OpenAI if Cursor AI is not available or failed
    if OPENAI_AVAILABLE:
        try:
            openai_key = os.environ.get("OPENAI_API_KEY")
            if not openai_key:
                logger.info("No OpenAI API key found, using fallback suggestions")
                return get_fallback_suggestions()
            
            client = OpenAI(api_key=openai_key)
                
            # Make API call to generate suggestions
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful productivity assistant that provides specific, actionable next step suggestions."},
                    {"role": "user", "content": f"Here is my to-do list:\n{items_context}\n\n{focus_prompt}"}
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            # Parse suggestions from response
            suggestions_text = response.choices[0].message.content
            suggestions = [s.strip() for s in suggestions_text.split("\n") if s.strip()]
            
            # Clean up suggestions (remove numbering, etc.)
            cleaned_suggestions = []
            for suggestion in suggestions:
                # Remove numbering and special characters
                if suggestion.startswith(("1.", "2.", "3.", "-", "*", "•")):
                    suggestion = suggestion[2:].strip()
                # Remove quotes if present
                suggestion = suggestion.strip('"\'')
                cleaned_suggestions.append(suggestion)
                
            # Limit to 3 suggestions
            return cleaned_suggestions[:3]
            
        except Exception as e:
            logger.error(f"Error generating OpenAI suggestions: {e}")
    
    # If all AI methods fail, use fallback suggestions
    return get_fallback_suggestions()

def get_fallback_suggestions(category: Optional[str] = None) -> List[str]:
    """
    Get fallback suggestions when AI is not available.
    
    Args:
        category: Optional category to filter suggestions
    
    Returns:
        List of suggestion strings
    """
    # Randomly select a category if none provided
    selected_category = category or random.choice(list(FALLBACK_SUGGESTIONS.keys()))
    
    # Get suggestions for the category
    available_suggestions = FALLBACK_SUGGESTIONS.get(
        selected_category, 
        FALLBACK_SUGGESTIONS["productivity"]
    )
    
    # Randomly select 3 unique suggestions
    selected_suggestions = random.sample(
        available_suggestions, 
        min(3, len(available_suggestions))
    )
    
    return selected_suggestions