"""
Routes for the ASL Customer Support application.

This module defines the routes for the ASL Customer Support service, including
support tickets, language conversion, service provider integration, and more.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, jsonify, current_app, session, g, Response, stream_with_context
)
from sqlalchemy.orm import Session
from werkzeug.utils import secure_filename

from app import db
from app.models_deaf_service import (
    User, SupportTicket, VideoSubmission, ServiceProvider,
    ServiceProviderConnection, Conversation, Message,
    Conversion, ConversionType, VideoSubmissionStatus, TicketStatus
)
from app.utils import (
    get_current_user, get_or_create_user, allowed_file, save_uploaded_file,
    ALLOWED_VIDEO_EXTENSIONS, ALLOWED_AUDIO_EXTENSIONS
)
from app.language_conversion_service import (
    process_conversion, create_conversion
)
from replit_auth import require_login, replit_user

logger = logging.getLogger(__name__)

# Create blueprint
deaf_service_bp = Blueprint('deaf_service', __name__, url_prefix='')


# Helper function for route security
def require_user(view_func):
    """
    Decorator to require a user to be authenticated and have a user record.
    
    Args:
        view_func: The view function to decorate
        
    Returns:
        Decorated function
    """
    @require_login
    def decorated_function(*args, **kwargs):
        user_data = replit_user()
        if not user_data:
            flash("Authentication required", "danger")
            return redirect(url_for("replit_bp.login"))
        
        user = get_or_create_user(user_data)
        if not user:
            flash("Unable to find or create user record", "danger")
            return redirect(url_for("deaf_service.index"))
        
        # Store user in request context
        g.user = user
        
        return view_func(*args, **kwargs)
    
    return decorated_function


# Public routes
@deaf_service_bp.route('/')
def index():
    """Render the index page."""
    return render_template('index.html')


# User routes
@deaf_service_bp.route('/dashboard')
@require_user
def dashboard():
    """Render the dashboard page."""
    user = g.user
    
    # Get active tickets
    active_tickets = db.session.query(SupportTicket).filter(
        SupportTicket.user_id == user.id,
        SupportTicket.status != TicketStatus.CLOSED
    ).order_by(SupportTicket.updated_at.desc()).limit(5).all()
    
    # Get service providers
    service_providers = db.session.query(ServiceProvider).filter(
        ServiceProvider.is_active == True
    ).all()
    
    # Get recent videos
    recent_videos = db.session.query(VideoSubmission).filter(
        VideoSubmission.user_id == user.id
    ).order_by(VideoSubmission.created_at.desc()).limit(6).all()
    
    # Get active conversations
    active_conversations = db.session.query(Conversation).filter(
        Conversation.user_id == user.id,
        Conversation.is_active == True
    ).order_by(Conversation.updated_at.desc()).limit(3).all()
    
    return render_template(
        'deaf_service/dashboard.html',
        user=user,
        active_tickets=active_tickets,
        service_providers=service_providers,
        recent_videos=recent_videos,
        active_conversations=active_conversations
    )


# Conversion routes
@deaf_service_bp.route('/language-access')
@require_user
def language_access():
    """Render the language access page."""
    user = g.user
    
    # Get recent conversions
    recent_conversions = db.session.query(Conversion).filter(
        Conversion.user_id == user.id
    ).order_by(Conversion.created_at.desc()).limit(10).all()
    
    return render_template(
        'deaf_service/language_access.html',
        user=user,
        recent_conversions=recent_conversions
    )


@deaf_service_bp.route('/language-access/speech-to-sign', methods=['GET', 'POST'])
@require_user
def speech_to_sign():
    """Handle speech to sign language conversion."""
    user = g.user
    
    if request.method == 'POST':
        # Handle file upload
        if 'audio' in request.files:
            audio_file = request.files['audio']
            
            # Save audio file
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'audio', str(user.id))
            success, file_path = save_uploaded_file(audio_file, upload_dir, ALLOWED_AUDIO_EXTENSIONS)
            
            if not success:
                flash(f"Error uploading audio: {file_path}", "danger")
                return redirect(request.url)
            
            # Create video submission record
            video = VideoSubmission(
                user_id=user.id,
                file_path=file_path,
                mime_type=audio_file.content_type,
                file_size=os.path.getsize(os.path.join(current_app.static_folder, file_path)),
                status=VideoSubmissionStatus.PROCESSING,
                title="Speech to Sign Language Conversion",
                description="Audio file uploaded for speech to sign language conversion"
            )
            db.session.add(video)
            db.session.commit()
            
            # Create conversion record
            conversion = create_conversion(
                db_session=db.session,
                user_id=user.id,
                conversion_type=ConversionType.SPEECH_TO_SIGN,
                source_video_id=video.id
            )
            
            # Process conversion asynchronously (in a real app, this would be done by a background worker)
            result = process_conversion(db.session, conversion.id)
            
            if result["success"]:
                flash("Speech converted to sign language video successfully", "success")
            else:
                flash(f"Error converting speech: {result.get('error')}", "danger")
            
            return redirect(url_for('deaf_service.view_conversion', conversion_id=conversion.id))
        
        # Handle text input
        elif 'text' in request.form and request.form['text'].strip():
            text = request.form['text'].strip()
            
            # Create conversion record
            conversion = create_conversion(
                db_session=db.session,
                user_id=user.id,
                conversion_type=ConversionType.TEXT_TO_SIGN,
                source_content=text
            )
            
            # Process conversion asynchronously
            result = process_conversion(db.session, conversion.id)
            
            if result["success"]:
                flash("Text converted to sign language video successfully", "success")
            else:
                flash(f"Error converting text: {result.get('error')}", "danger")
            
            return redirect(url_for('deaf_service.view_conversion', conversion_id=conversion.id))
        
        else:
            flash("Please provide audio or text input", "warning")
            return redirect(request.url)
    
    return render_template('deaf_service/speech_to_sign.html', user=user)


@deaf_service_bp.route('/language-access/sign-to-speech', methods=['GET', 'POST'])
@require_user
def sign_to_speech():
    """Handle sign language to speech conversion."""
    user = g.user
    
    if request.method == 'POST':
        # Handle file upload
        if 'video' in request.files:
            video_file = request.files['video']
            
            # Save video file
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'video', str(user.id))
            success, file_path = save_uploaded_file(video_file, upload_dir, ALLOWED_VIDEO_EXTENSIONS)
            
            if not success:
                flash(f"Error uploading video: {file_path}", "danger")
                return redirect(request.url)
            
            # Create video submission record
            video = VideoSubmission(
                user_id=user.id,
                file_path=file_path,
                mime_type=video_file.content_type,
                file_size=os.path.getsize(os.path.join(current_app.static_folder, file_path)),
                status=VideoSubmissionStatus.PROCESSING,
                title="Sign Language to Speech Conversion",
                description="Video file uploaded for sign language to speech conversion"
            )
            db.session.add(video)
            db.session.commit()
            
            # Create conversion record
            conversion = create_conversion(
                db_session=db.session,
                user_id=user.id,
                conversion_type=ConversionType.SIGN_TO_SPEECH,
                source_video_id=video.id
            )
            
            # Process conversion asynchronously
            result = process_conversion(db.session, conversion.id)
            
            if result["success"]:
                flash("Sign language converted to speech successfully", "success")
            else:
                flash(f"Error converting sign language: {result.get('error')}", "danger")
            
            return redirect(url_for('deaf_service.view_conversion', conversion_id=conversion.id))
        
        else:
            flash("Please provide a video input", "warning")
            return redirect(request.url)
    
    return render_template('deaf_service/sign_to_speech.html', user=user)


@deaf_service_bp.route('/language-access/sign-to-text', methods=['GET', 'POST'])
@require_user
def sign_to_text():
    """Handle sign language to text conversion."""
    user = g.user
    
    if request.method == 'POST':
        # Handle file upload
        if 'video' in request.files:
            video_file = request.files['video']
            
            # Save video file
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'video', str(user.id))
            success, file_path = save_uploaded_file(video_file, upload_dir, ALLOWED_VIDEO_EXTENSIONS)
            
            if not success:
                flash(f"Error uploading video: {file_path}", "danger")
                return redirect(request.url)
            
            # Create video submission record
            video = VideoSubmission(
                user_id=user.id,
                file_path=file_path,
                mime_type=video_file.content_type,
                file_size=os.path.getsize(os.path.join(current_app.static_folder, file_path)),
                status=VideoSubmissionStatus.PROCESSING,
                title="Sign Language to Text Conversion",
                description="Video file uploaded for sign language to text conversion"
            )
            db.session.add(video)
            db.session.commit()
            
            # Create conversion record
            conversion = create_conversion(
                db_session=db.session,
                user_id=user.id,
                conversion_type=ConversionType.SIGN_TO_TEXT,
                source_video_id=video.id
            )
            
            # Process conversion asynchronously
            result = process_conversion(db.session, conversion.id)
            
            if result["success"]:
                flash("Sign language converted to text successfully", "success")
            else:
                flash(f"Error converting sign language: {result.get('error')}", "danger")
            
            return redirect(url_for('deaf_service.view_conversion', conversion_id=conversion.id))
        
        else:
            flash("Please provide a video input", "warning")
            return redirect(request.url)
    
    return render_template('deaf_service/sign_to_text.html', user=user)


@deaf_service_bp.route('/language-access/text-to-sign', methods=['GET', 'POST'])
@require_user
def text_to_sign():
    """Handle text to sign language video conversion."""
    user = g.user
    
    if request.method == 'POST':
        # Handle text input
        if 'text' in request.form and request.form['text'].strip():
            text = request.form['text'].strip()
            
            # Create conversion record
            conversion = create_conversion(
                db_session=db.session,
                user_id=user.id,
                conversion_type=ConversionType.TEXT_TO_SIGN,
                source_content=text
            )
            
            # Process conversion asynchronously
            result = process_conversion(db.session, conversion.id)
            
            if result["success"]:
                flash("Text converted to sign language video successfully", "success")
            else:
                flash(f"Error converting text: {result.get('error')}", "danger")
            
            return redirect(url_for('deaf_service.view_conversion', conversion_id=conversion.id))
        
        else:
            flash("Please provide text input", "warning")
            return redirect(request.url)
    
    return render_template('deaf_service/text_to_sign.html', user=user)


@deaf_service_bp.route('/language-access/text-to-visual', methods=['GET', 'POST'])
@require_user
def text_to_visual():
    """Handle text to visual aid conversion."""
    user = g.user
    
    if request.method == 'POST':
        # Handle text input
        if 'text' in request.form and request.form['text'].strip():
            text = request.form['text'].strip()
            
            # Create conversion record
            conversion = create_conversion(
                db_session=db.session,
                user_id=user.id,
                conversion_type=ConversionType.TEXT_TO_VIDEO,
                source_content=text
            )
            
            # Process conversion asynchronously
            result = process_conversion(db.session, conversion.id)
            
            if result["success"]:
                flash("Text converted to visual aid successfully", "success")
            else:
                flash(f"Error creating visual aid: {result.get('error')}", "danger")
            
            return redirect(url_for('deaf_service.view_conversion', conversion_id=conversion.id))
        
        else:
            flash("Please provide text input", "warning")
            return redirect(request.url)
    
    return render_template('deaf_service/text_to_visual.html', user=user)


@deaf_service_bp.route('/language-access/conversion/<int:conversion_id>')
@require_user
def view_conversion(conversion_id):
    """View a specific conversion."""
    user = g.user
    
    conversion = db.session.query(Conversion).filter(
        Conversion.id == conversion_id,
        Conversion.user_id == user.id
    ).first()
    
    if not conversion:
        flash("Conversion not found", "danger")
        return redirect(url_for('deaf_service.language_access'))
    
    return render_template(
        'deaf_service/view_conversion.html',
        user=user,
        conversion=conversion
    )


# Chatbot routes
@deaf_service_bp.route('/chatbot')
@require_user
def chatbot():
    """Render the AI chatbot page."""
    user = g.user
    
    # Get or create an active conversation
    conversation = db.session.query(Conversation).filter(
        Conversation.user_id == user.id,
        Conversation.is_active == True
    ).order_by(Conversation.updated_at.desc()).first()
    
    if not conversation:
        conversation = Conversation(
            user_id=user.id,
            title=f"Conversation {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        )
        db.session.add(conversation)
        db.session.commit()
        
        # Add welcome message
        welcome_message = Message(
            conversation_id=conversation.id,
            is_user=False,
            content="Hello! I'm your ASL Support Assistant. I can help you with service provider connections, support tickets, job applications, and more. How can I assist you today?"
        )
        db.session.add(welcome_message)
        db.session.commit()
    
    # Get messages for the conversation
    messages = db.session.query(Message).filter(
        Message.conversation_id == conversation.id
    ).order_by(Message.created_at).all()
    
    return render_template(
        'deaf_service/chatbot.html',
        user=user,
        conversation=conversation,
        messages=messages
    )


@deaf_service_bp.route('/chatbot/message', methods=['POST'])
@require_user
def chatbot_message():
    """Handle chatbot message submission."""
    user = g.user
    
    conversation_id = request.form.get('conversation_id')
    message_content = request.form.get('message')
    
    if not message_content:
        return jsonify({"success": False, "error": "Message content is required"})
    
    # Get or create conversation
    if conversation_id:
        conversation = db.session.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id
        ).first()
        
        if not conversation:
            return jsonify({"success": False, "error": "Conversation not found"})
    else:
        conversation = Conversation(
            user_id=user.id,
            title=f"Conversation {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        )
        db.session.add(conversation)
        db.session.commit()
    
    # Create user message
    user_message = Message(
        conversation_id=conversation.id,
        is_user=True,
        content=message_content
    )
    db.session.add(user_message)
    
    # Update conversation timestamp
    conversation.updated_at = datetime.utcnow()
    db.session.commit()
    
    # Process the message and generate a response
    # In a real implementation, this would call an AI service
    response_content = f"I received your message: \"{message_content}\". This is a placeholder response as the AI backend is not yet connected."
    
    # Create bot response
    bot_message = Message(
        conversation_id=conversation.id,
        is_user=False,
        content=response_content
    )
    db.session.add(bot_message)
    db.session.commit()
    
    # Return HTML for both messages
    return render_template(
        'deaf_service/partials/chat_messages.html',
        user_message=user_message,
        bot_message=bot_message
    )


@deaf_service_bp.route('/chatbot/video', methods=['POST'])
@require_user
def chatbot_video():
    """Handle video submission to chatbot."""
    user = g.user
    
    conversation_id = request.form.get('conversation_id')
    
    if 'video' not in request.files:
        return jsonify({"success": False, "error": "No video file provided"})
    
    video_file = request.files['video']
    
    # Get or create conversation
    if conversation_id:
        conversation = db.session.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id
        ).first()
        
        if not conversation:
            return jsonify({"success": False, "error": "Conversation not found"})
    else:
        conversation = Conversation(
            user_id=user.id,
            title=f"Video Conversation {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        )
        db.session.add(conversation)
        db.session.commit()
    
    # Save video file
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'video', str(user.id))
    success, file_path = save_uploaded_file(video_file, upload_dir, ALLOWED_VIDEO_EXTENSIONS)
    
    if not success:
        return jsonify({"success": False, "error": f"Error uploading video: {file_path}"})
    
    # Create video submission record
    video = VideoSubmission(
        user_id=user.id,
        file_path=file_path,
        mime_type=video_file.content_type,
        file_size=os.path.getsize(os.path.join(current_app.static_folder, file_path)),
        status=VideoSubmissionStatus.PROCESSING,
        title="Chatbot Video Submission",
        description="Video submitted via chatbot",
        conversation_id=conversation.id
    )
    db.session.add(video)
    db.session.commit()
    
    # Create user message referencing the video
    user_message = Message(
        conversation_id=conversation.id,
        is_user=True,
        content="[Video submission]",
        media_url=file_path,
        media_type="video"
    )
    db.session.add(user_message)
    
    # Update conversation timestamp
    conversation.updated_at = datetime.utcnow()
    db.session.commit()
    
    # Process the video (sign language to text)
    conversion = create_conversion(
        db_session=db.session,
        user_id=user.id,
        conversion_type=ConversionType.SIGN_TO_TEXT,
        source_video_id=video.id,
        conversation_id=conversation.id
    )
    
    # Process conversion
    result = process_conversion(db.session, conversion.id)
    
    # Generate response
    if result["success"] and conversion.result_content:
        response_content = f"I interpreted your sign language video as: \"{conversion.result_content}\". This is a placeholder response as the AI backend is not fully connected."
    else:
        response_content = "I received your video but was unable to process the sign language content. Could you please provide more context or try again with clearer signing?"
    
    # Create bot response
    bot_message = Message(
        conversation_id=conversation.id,
        is_user=False,
        content=response_content
    )
    db.session.add(bot_message)
    db.session.commit()
    
    # Return HTML for both messages
    return render_template(
        'deaf_service/partials/chat_messages.html',
        user_message=user_message,
        bot_message=bot_message
    )


# Service provider routes
@deaf_service_bp.route('/service-providers')
@require_user
def service_providers():
    """Render the service providers page."""
    user = g.user
    
    # Get all service providers
    service_providers = db.session.query(ServiceProvider).filter(
        ServiceProvider.is_active == True
    ).all()
    
    # Get user's connections
    connections = db.session.query(ServiceProviderConnection).filter(
        ServiceProviderConnection.user_id == user.id
    ).all()
    
    # Create a map of provider ID to connection
    connection_map = {conn.provider_id: conn for conn in connections}
    
    return render_template(
        'deaf_service/service_providers.html',
        user=user,
        service_providers=service_providers,
        connection_map=connection_map
    )


@deaf_service_bp.route('/service-providers/connect/<int:provider_id>', methods=['POST'])
@require_user
def connect_service_provider(provider_id):
    """Connect a user to a service provider."""
    user = g.user
    
    provider = db.session.query(ServiceProvider).filter(
        ServiceProvider.id == provider_id,
        ServiceProvider.is_active == True
    ).first()
    
    if not provider:
        flash("Service provider not found", "danger")
        return redirect(url_for('deaf_service.service_providers'))
    
    # Check if connection already exists
    existing_conn = db.session.query(ServiceProviderConnection).filter(
        ServiceProviderConnection.user_id == user.id,
        ServiceProviderConnection.provider_id == provider_id
    ).first()
    
    if existing_conn:
        flash(f"You are already connected to {provider.name}", "info")
        return redirect(url_for('deaf_service.service_providers'))
    
    # Create new connection
    username = request.form.get('username')
    password = request.form.get('password')  # In a real app, this would be handled securely
    
    if not username or not password:
        flash("Username and password are required", "warning")
        return redirect(url_for('deaf_service.service_providers'))
    
    # Store connection data (in a real app, credentials would be encrypted)
    connection_data = {
        "username": username,
        "connected_at": datetime.utcnow().isoformat()
    }
    
    connection = ServiceProviderConnection(
        user_id=user.id,
        provider_id=provider_id,
        connection_data=connection_data,
        is_active=True
    )
    db.session.add(connection)
    db.session.commit()
    
    flash(f"Successfully connected to {provider.name}", "success")
    return redirect(url_for('deaf_service.service_providers'))


# Support ticket routes - basic functionality
@deaf_service_bp.route('/tickets')
@require_user
def tickets():
    """Render the support tickets page."""
    user = g.user
    
    # Get all tickets for the user
    tickets = db.session.query(SupportTicket).filter(
        SupportTicket.user_id == user.id
    ).order_by(SupportTicket.updated_at.desc()).all()
    
    return render_template(
        'deaf_service/tickets.html',
        user=user,
        tickets=tickets
    )


@deaf_service_bp.route('/tickets/new', methods=['GET', 'POST'])
@require_user
def new_ticket():
    """Create a new support ticket."""
    user = g.user
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        priority = int(request.form.get('priority', 1))
        
        if not title:
            flash("Title is required", "warning")
            return redirect(request.url)
        
        # Create ticket
        ticket = SupportTicket(
            user_id=user.id,
            title=title,
            description=description,
            category=category,
            priority=priority,
            status=TicketStatus.NEW
        )
        db.session.add(ticket)
        db.session.commit()
        
        flash("Support ticket created successfully", "success")
        return redirect(url_for('deaf_service.view_ticket', ticket_id=ticket.id))
    
    return render_template('deaf_service/new_ticket.html', user=user)