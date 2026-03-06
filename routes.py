"""
Route definitions for the ASL Customer Support application.
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, flash, session, g

from app.language_conversion_service import LanguageConversionService

# Set up logging
logger = logging.getLogger(__name__)

# Create blueprints
main_bp = Blueprint('main', __name__)
api_bp = Blueprint('api', __name__)

# Initialize language conversion service
language_service = LanguageConversionService()

# Main routes
@main_bp.route('/')
def index():
    """Render the home page."""
    return render_template('index.html')

@main_bp.route('/voice-to-sign')
def voice_to_sign_page():
    """Render the voice to sign language translation page."""
    return render_template('voice_to_sign.html')

@main_bp.route('/credits')
def credits():
    """Render the credits and open source acknowledgments page."""
    return render_template('credits.html')

# API routes
@api_bp.route('/voice-to-text', methods=['POST'])
async def voice_to_text():
    """
    Convert voice/audio to text.
    
    Expects audio data in the request files.
    Returns JSON with transcription data.
    """
    if 'audio' not in request.files:
        return jsonify({
            'success': False,
            'error': 'No audio file provided',
            'timestamp': datetime.utcnow().isoformat()
        }), 400
    
    try:
        audio_file = request.files['audio']
        audio_data = audio_file.read()
        
        # Process the audio using the language service
        result = await language_service.voice_to_text(audio_data)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in voice-to-text endpoint: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@api_bp.route('/text-to-sign', methods=['POST'])
async def text_to_sign():
    """
    Convert text to sign language gestures.
    
    Expects JSON with 'text' field.
    Returns JSON with gesture sequence data.
    """
    data = request.json
    
    if not data or 'text' not in data:
        return jsonify({
            'success': False,
            'error': 'No text provided',
            'timestamp': datetime.utcnow().isoformat()
        }), 400
    
    try:
        text = data['text']
        
        # Process the text using the language service
        result = await language_service.text_to_sign_sequence(text)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in text-to-sign endpoint: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@api_bp.route('/voice-to-sign-preview', methods=['POST'])
async def voice_to_sign_preview():
    """
    Complete voice to sign language translation pipeline.
    
    1. Converts voice to text
    2. Converts text to sign language gestures
    
    Expects audio data in the request files.
    Returns JSON with both transcription and gesture data.
    """
    if 'audio' not in request.files:
        return jsonify({
            'success': False,
            'error': 'No audio file provided',
            'timestamp': datetime.utcnow().isoformat()
        }), 400
    
    try:
        audio_file = request.files['audio']
        audio_data = audio_file.read()
        
        # Step 1: Convert voice to text
        voice_to_text_result = await language_service.voice_to_text(audio_data)
        
        if not voice_to_text_result.get('success', False):
            # If voice to text failed, return the error
            return jsonify(voice_to_text_result), 500
        
        # Step 2: Convert text to sign language gestures
        text = voice_to_text_result['text']
        text_to_sign_result = await language_service.text_to_sign_sequence(text)
        
        # Combine the results
        result = {
            'success': text_to_sign_result.get('success', False),
            'voice_to_text': voice_to_text_result,
            'text_to_sign': text_to_sign_result,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in voice-to-sign-preview endpoint: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

# Initialize gesture feedback service
from app.services.gesture_feedback import GestureFeedbackService
gesture_feedback_service = GestureFeedbackService()

@api_bp.route('/gesture-feedback', methods=['POST'])
async def submit_gesture_feedback():
    """
    Submit gesture-based feedback.
    
    Expects:
    - video file in request.files['video']
    - feedbackType as form data
    - additional metadata as form data
    
    Returns JSON with submission status.
    """
    if 'video' not in request.files:
        return jsonify({
            'success': False,
            'error': 'No video file provided',
            'timestamp': datetime.utcnow().isoformat()
        }), 400
    
    try:
        video_file = request.files['video']
        video_data = video_file.read()
        
        # Get form data
        feedback_type = request.form.get('feedbackType', 'general')
        
        # Collect additional metadata
        metadata = {
            'pageUrl': request.form.get('pageUrl', request.referrer or ''),
            'timestamp': request.form.get('timestamp', datetime.utcnow().isoformat()),
            'userAgent': request.user_agent.string,
            'ipAddress': request.remote_addr,
            'context': request.form.get('context', ''),
            'contextId': request.form.get('contextId', '')
        }
        
        # Add user information if authenticated
        if hasattr(g, 'user') and g.user:
            metadata['userId'] = g.user.id
            metadata['username'] = g.user.username
        
        # Process the feedback
        success, result = await gesture_feedback_service.process_feedback(
            video_data,
            feedback_type,
            metadata
        )
        
        if success:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Error processing gesture feedback: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500