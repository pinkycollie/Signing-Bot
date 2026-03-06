"""
Database models for ASL Customer Support Application
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app import db

class Item(db.Model):
    """Base item model previously defined in the application."""
    __tablename__ = "items"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Item {self.id}: {self.title}>"
    
    def to_dict(self):
        """Convert item to dictionary for API responses"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "is_completed": self.is_completed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class Project(db.Model):
    """Project model previously defined in the application."""
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="active")  # active, archived, completed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    replit_user_id = Column(String(50), nullable=True)  # Store the Replit user ID
    
    def __repr__(self):
        return f"<Project {self.id}: {self.title}>"
    
    def to_dict(self):
        """Convert project to dictionary for API responses"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

# New models for ASL customer support

class User(db.Model):
    """User model for storing user data."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    replit_id = Column(String(50), unique=True, nullable=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=True)
    is_deaf = Column(Boolean, default=False)
    is_interpreter = Column(Boolean, default=False)
    preferred_language = Column(String(10), default="en")  # en, asl, es, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    tickets = relationship("SupportTicket", back_populates="user")
    chat_messages = relationship("ChatMessage", back_populates="user")
    job_applications = relationship("JobApplication", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.id}: {self.username}>"

class SupportTicket(db.Model):
    """Support ticket model for ASL Customer Support."""
    __tablename__ = "support_tickets"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="new")  # new, in_progress, pending, resolved
    priority = Column(String(20), default="medium")  # low, medium, high, urgent
    service_type = Column(String(50), nullable=True)  # video_relay, interpreting, captioning
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    anytype_sync_id = Column(String(100), nullable=True)  # ID for Anytype sync
    
    # Relationships
    user = relationship("User", back_populates="tickets")
    messages = relationship("TicketMessage", back_populates="ticket")
    videos = relationship("VideoSubmission", back_populates="ticket")
    
    def __repr__(self):
        return f"<SupportTicket {self.id}: {self.subject}>"

class TicketMessage(db.Model):
    """Message within a support ticket."""
    __tablename__ = "ticket_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("support_tickets.id"), nullable=False)
    sender_type = Column(String(20), nullable=False)  # user, staff, system, ai
    sender_id = Column(Integer, nullable=True)  # User ID if sender_type is user or staff
    message_text = Column(Text, nullable=True)
    message_type = Column(String(20), default="text")  # text, video, image
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_internal = Column(Boolean, default=False)  # Whether message is internal note
    
    # Relationships
    ticket = relationship("SupportTicket", back_populates="messages")
    video = relationship("VideoSubmission", back_populates="message", uselist=False)
    
    def __repr__(self):
        return f"<TicketMessage {self.id}: {self.message_text[:30]}...>"

class VideoSubmission(db.Model):
    """Model for storing video submissions and processing results."""
    __tablename__ = "video_submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("support_tickets.id"), nullable=True)
    message_id = Column(Integer, ForeignKey("ticket_messages.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_path = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=True)  # Size in bytes
    duration = Column(Float, nullable=True)  # Duration in seconds
    mime_type = Column(String(100), nullable=True)
    video_type = Column(String(20), default="asl")  # asl, speech
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Processing results
    transcription = Column(Text, nullable=True)  # Speech-to-text or ASL-to-text
    summary = Column(Text, nullable=True)  # Summary of video content
    confidence_score = Column(Float, nullable=True)  # 0-1 confidence in transcription
    
    # Relationships
    ticket = relationship("SupportTicket", back_populates="videos")
    message = relationship("TicketMessage", back_populates="video")
    user = relationship("User", backref="video_submissions")
    
    def __repr__(self):
        return f"<VideoSubmission {self.id}: {self.status}>"

class ChatMessage(db.Model):
    """Model for storing chat messages in the AI chatbot."""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message_text = Column(Text, nullable=True)
    message_type = Column(String(20), default="text")  # text, video, image
    role = Column(String(20), nullable=False)  # user, system, assistant
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    conversation_id = Column(String(100), nullable=True)  # Group messages in conversations
    
    # AI processing results (if applicable)
    processed_text = Column(Text, nullable=True)  # Text after processing (ASL-to-text)
    ai_response = Column(Text, nullable=True)  # AI response to message
    
    # Relationships
    user = relationship("User", back_populates="chat_messages")
    
    def __repr__(self):
        return f"<ChatMessage {self.id}: {self.message_text[:30]}...>"

class JobApplication(db.Model):
    """Model for storing job applications for ASL interpreters."""
    __tablename__ = "job_applications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    position = Column(String(100), nullable=False)
    company = Column(String(100), nullable=True)
    status = Column(String(20), default="applied")  # applied, interviewing, offered, rejected
    application_date = Column(DateTime(timezone=True), server_default=func.now())
    interview_date = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    anytype_sync_id = Column(String(100), nullable=True)  # ID for Anytype sync
    
    # Relationships
    user = relationship("User", back_populates="job_applications")
    
    def __repr__(self):
        return f"<JobApplication {self.id}: {self.position} at {self.company}>"

class ServiceProvider(db.Model):
    """Model for storing information about ASL service providers."""
    __tablename__ = "service_providers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    provider_type = Column(String(50), nullable=False)  # video_relay, interpreting, captioning
    website = Column(String(255), nullable=True)
    api_endpoint = Column(String(255), nullable=True)
    logo_path = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<ServiceProvider {self.id}: {self.name}>"

class AnytypeSyncStatus(db.Model):
    """Model for tracking Anytype synchronization status."""
    __tablename__ = "anytype_sync_status"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    data_type = Column(String(50), nullable=False)  # tickets, jobs
    last_export_time = Column(DateTime(timezone=True), nullable=True)
    last_import_time = Column(DateTime(timezone=True), nullable=True)
    export_count = Column(Integer, default=0)
    import_count = Column(Integer, default=0)
    last_sync_status = Column(String(20), default="none")  # success, error, none
    error_message = Column(Text, nullable=True)
    sync_file = Column(String(255), nullable=True)  # Path to sync file
    
    def __repr__(self):
        return f"<AnytypeSyncStatus {self.id}: {self.data_type} for user {self.user_id}>"

class AIModel(db.Model):
    """Model for storing information about AI models for ASL recognition and processing."""
    __tablename__ = "ai_models"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    model_type = Column(String(50), nullable=False)  # asl_recognition, speech_to_text, text_to_speech
    version = Column(String(50), nullable=False)
    accuracy = Column(Float, nullable=True)  # 0-1 accuracy score
    model_path = Column(String(255), nullable=True)  # Path to model files
    api_endpoint = Column(String(255), nullable=True)  # If using external API
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<AIModel {self.id}: {self.name} v{self.version}>"