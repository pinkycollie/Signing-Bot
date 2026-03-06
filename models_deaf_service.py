"""
Models for the ASL Customer Support service.

This module defines the database models for users, support tickets,
job applications, video submissions, and more.
"""

import enum
from typing import Dict, Any, List, Optional
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum, JSON, func
)
from sqlalchemy.orm import relationship

from app import Base


class UserRole(enum.Enum):
    """Enum for user roles."""
    USER = "user"
    INTERPRETER = "interpreter"
    ADMIN = "admin"


class TicketStatus(enum.Enum):
    """Enum for support ticket status."""
    NEW = "new"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_CUSTOMER = "waiting_for_customer"
    RESOLVED = "resolved"
    CLOSED = "closed"


class VideoSubmissionStatus(enum.Enum):
    """Enum for video submission status."""
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class ConversionType(enum.Enum):
    """Enum for conversion types."""
    SPEECH_TO_SIGN = "speech_to_sign"
    SIGN_TO_SPEECH = "sign_to_speech"
    SIGN_TO_TEXT = "sign_to_text"
    TEXT_TO_SIGN = "text_to_sign"
    TEXT_TO_VIDEO = "text_to_video"


class User(Base):
    """User model."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    replit_id = Column(String(100), unique=True, nullable=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=True)
    display_name = Column(String(100), nullable=True)
    profile_image = Column(String(255), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.USER)
    preferences = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    tickets = relationship("SupportTicket", back_populates="user")
    video_submissions = relationship("VideoSubmission", back_populates="user")
    service_connections = relationship("ServiceProviderConnection", back_populates="user")
    conversations = relationship("Conversation", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.username}>"
    
    @property
    def is_interpreter(self):
        """Check if user is an interpreter."""
        return self.role == UserRole.INTERPRETER
    
    @property
    def is_admin(self):
        """Check if user is an admin."""
        return self.role == UserRole.ADMIN


class SupportTicket(Base):
    """Support ticket model."""
    __tablename__ = "support_tickets"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TicketStatus), default=TicketStatus.NEW)
    category = Column(String(100), nullable=True)
    priority = Column(Integer, default=1)  # 1: Low, 2: Medium, 3: High
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="tickets")
    videos = relationship("VideoSubmission", back_populates="ticket")
    
    def __repr__(self):
        return f"<SupportTicket {self.id}: {self.title}>"


class VideoSubmission(Base):
    """Video submission model."""
    __tablename__ = "video_submissions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    ticket_id = Column(Integer, ForeignKey("support_tickets.id"), nullable=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    file_path = Column(String(512), nullable=False)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    duration = Column(Integer, nullable=True)  # Duration in seconds
    status = Column(Enum(VideoSubmissionStatus), default=VideoSubmissionStatus.UPLOADING)
    processing_result = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="video_submissions")
    ticket = relationship("SupportTicket", back_populates="videos")
    conversation = relationship("Conversation", back_populates="videos")
    conversions = relationship("Conversion", back_populates="source_video")
    
    def __repr__(self):
        return f"<VideoSubmission {self.id}: {self.title or 'Untitled'}>"


class ServiceProvider(Base):
    """Service provider model."""
    __tablename__ = "service_providers"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    logo = Column(String(255), nullable=True)
    url = Column(String(512), nullable=True)
    api_url = Column(String(512), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    connections = relationship("ServiceProviderConnection", back_populates="provider")
    
    def __repr__(self):
        return f"<ServiceProvider {self.id}: {self.name}>"


class ServiceProviderConnection(Base):
    """Service provider connection model."""
    __tablename__ = "service_provider_connections"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider_id = Column(Integer, ForeignKey("service_providers.id"), nullable=False)
    connection_data = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="service_connections")
    provider = relationship("ServiceProvider", back_populates="connections")
    
    def __repr__(self):
        return f"<ServiceProviderConnection {self.id}: user_id={self.user_id}, provider_id={self.provider_id}>"


class Conversation(Base):
    """Conversation model for the AI chatbot."""
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    videos = relationship("VideoSubmission", back_populates="conversation")
    conversions = relationship("Conversion", back_populates="conversation")
    
    def __repr__(self):
        return f"<Conversation {self.id}: {self.title or 'Untitled'}>"


class Message(Base):
    """Message model for the AI chatbot."""
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    is_user = Column(Boolean, default=True)  # True for user, False for bot
    content = Column(Text, nullable=False)
    media_url = Column(String(512), nullable=True)
    media_type = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    
    def __repr__(self):
        return f"<Message {self.id}: conversation_id={self.conversation_id}, is_user={self.is_user}>"


class Conversion(Base):
    """Model for language conversions (speech/sign/text)."""
    __tablename__ = "conversions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    source_video_id = Column(Integer, ForeignKey("video_submissions.id"), nullable=True)
    conversion_type = Column(Enum(ConversionType), nullable=False)
    source_content = Column(Text, nullable=True)
    result_content = Column(Text, nullable=True)
    result_video_path = Column(String(512), nullable=True)
    result_audio_path = Column(String(512), nullable=True)
    processing_status = Column(String(50), default="processing")
    processing_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User")
    conversation = relationship("Conversation", back_populates="conversions")
    source_video = relationship("VideoSubmission", back_populates="conversions")
    
    def __repr__(self):
        return f"<Conversion {self.id}: type={self.conversion_type}, status={self.processing_status}>"