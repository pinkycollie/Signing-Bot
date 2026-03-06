"""
Anytype Integration Module for ASL Customer Support Application

This module handles the integration between the Flask app and Anytype's local JSON data.
Since Anytype doesn't have a direct API yet, this implementation uses file-based
synchronization with JSON files that can be imported to and exported from Anytype.
"""

import os
import json
import logging
import shutil
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from sqlalchemy.orm import Session

# Configure logging
logger = logging.getLogger(__name__)

# Default directory for Anytype sync files
DEFAULT_SYNC_DIR = os.path.join(os.getcwd(), 'anytype_sync')

def check_sync_directory() -> bool:
    """
    Check if the Anytype sync directory exists and is writable
    
    Returns:
        Boolean indicating if the directory is ready
    """
    sync_dir = os.environ.get('ANYTYPE_SYNC_DIR', DEFAULT_SYNC_DIR)
    
    # Create the directory if it doesn't exist
    if not os.path.exists(sync_dir):
        try:
            os.makedirs(sync_dir)
            logger.info(f"Created Anytype sync directory: {sync_dir}")
        except Exception as e:
            logger.error(f"Failed to create Anytype sync directory: {e}")
            return False
    
    # Check if the directory is writable
    if not os.access(sync_dir, os.W_OK):
        logger.error(f"Anytype sync directory is not writable: {sync_dir}")
        return False
    
    return True

def get_default_export_path(user_id: str, data_type: str) -> str:
    """
    Get the default export path for a given user and data type
    
    Args:
        user_id: The user's ID
        data_type: Type of data (e.g., 'tickets', 'jobs')
        
    Returns:
        Path to the export file
    """
    sync_dir = os.environ.get('ANYTYPE_SYNC_DIR', DEFAULT_SYNC_DIR)
    
    # Create user directory if it doesn't exist
    user_dir = os.path.join(sync_dir, f"user_{user_id}")
    os.makedirs(user_dir, exist_ok=True)
    
    # Create timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    return os.path.join(user_dir, f"{data_type}_export_{timestamp}.json")

def get_latest_import_path(user_id: str, data_type: str) -> Optional[str]:
    """
    Get the path to the latest import file for a given user and data type
    
    Args:
        user_id: The user's ID
        data_type: Type of data (e.g., 'tickets', 'jobs')
        
    Returns:
        Path to the import file, or None if not found
    """
    sync_dir = os.environ.get('ANYTYPE_SYNC_DIR', DEFAULT_SYNC_DIR)
    user_dir = os.path.join(sync_dir, f"user_{user_id}")
    
    if not os.path.exists(user_dir):
        return None
    
    # Find import files matching the pattern
    import_files = [
        f for f in os.listdir(user_dir)
        if f.startswith(f"{data_type}_import_") and f.endswith(".json")
    ]
    
    if not import_files:
        return None
    
    # Sort by timestamp to get the latest
    latest_file = sorted(import_files)[-1]
    return os.path.join(user_dir, latest_file)

def update_sync_status(db_session: Session, user_id: str, data_type: str, 
                      is_export: bool, count: int, is_success: bool = True, error_message: Optional[str] = None, 
                      sync_file: Optional[str] = None) -> None:
    """
    Update the Anytype sync status for a user
    
    Args:
        db_session: SQLAlchemy database session
        user_id: The user's ID
        data_type: Type of data (e.g., 'tickets', 'jobs')
        is_export: Whether this was an export (True) or import (False)
        count: Number of items exported/imported
        is_success: Whether the sync was successful
        error_message: Optional error message if sync failed
        sync_file: Optional path to the sync file
    """
    from app.models import AnytypeSyncStatus, User
    
    try:
        # Get the user
        user = db_session.query(User).filter_by(replit_id=user_id).first()
        if not user:
            logger.error(f"User not found for sync status update: {user_id}")
            return
        
        # Get or create sync status
        sync_status = db_session.query(AnytypeSyncStatus).filter_by(
            user_id=user.id, data_type=data_type
        ).first()
        
        if not sync_status:
            sync_status = AnytypeSyncStatus(
                user_id=user.id,
                data_type=data_type
            )
            db_session.add(sync_status)
        
        # Update fields
        if is_export:
            sync_status.last_export_time = datetime.utcnow()
            sync_status.export_count += count
        else:
            sync_status.last_import_time = datetime.utcnow()
            sync_status.import_count += count
        
        sync_status.last_sync_status = "success" if is_success else "error"
        sync_status.error_message = error_message
        sync_status.sync_file = sync_file
        
        db_session.commit()
        logger.info(f"Updated Anytype sync status for user {user_id}, data_type {data_type}")
    
    except Exception as e:
        logger.error(f"Failed to update Anytype sync status: {e}")
        db_session.rollback()

def get_support_tickets_for_export(db_session: Session, user_id: str, 
                                  status: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve customer support ticket data from database for export to Anytype
    
    Args:
        db_session: SQLAlchemy database session
        user_id: The user's ID
        status: Optional status to filter by (e.g., 'new', 'resolved')
        
    Returns:
        List of support tickets in Anytype-compatible format
    """
    from app.models import User, SupportTicket, TicketMessage
    
    try:
        # Get user
        user = db_session.query(User).filter_by(replit_id=user_id).first()
        if not user:
            logger.error(f"User not found for ticket export: {user_id}")
            return []
        
        # Query tickets
        query = db_session.query(SupportTicket).filter_by(user_id=user.id)
        if status:
            query = query.filter_by(status=status)
        
        tickets = query.order_by(SupportTicket.created_at.desc()).all()
        
        # Format tickets for Anytype
        anytype_tickets = []
        for ticket in tickets:
            # Get messages for this ticket
            messages = db_session.query(TicketMessage).filter_by(ticket_id=ticket.id).order_by(TicketMessage.created_at.asc()).all()
            
            # Format the ticket
            ticket_data = {
                "id": ticket.id,
                "type": "ticket",
                "subject": ticket.subject,
                "description": ticket.description,
                "status": ticket.status,
                "priority": ticket.priority,
                "service_type": ticket.service_type,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
                "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
                "anytype_sync_id": ticket.anytype_sync_id,
                "messages": [
                    {
                        "id": msg.id,
                        "sender_type": msg.sender_type,
                        "message_text": msg.message_text,
                        "message_type": msg.message_type,
                        "created_at": msg.created_at.isoformat() if msg.created_at else None,
                        "is_internal": msg.is_internal
                    }
                    for msg in messages
                ]
            }
            anytype_tickets.append(ticket_data)
        
        return anytype_tickets
    
    except Exception as e:
        logger.error(f"Failed to get tickets for export: {e}")
        return []

def export_support_tickets_to_json(db_session: Session, user_id: str, 
                                  output_path: Optional[str] = None) -> str:
    """
    Export customer support ticket data to a JSON file for Anytype import
    
    Args:
        db_session: SQLAlchemy database session
        user_id: The user's ID
        output_path: Optional custom path for the export file
        
    Returns:
        Path to the exported JSON file
    """
    # Check sync directory
    if not check_sync_directory():
        raise RuntimeError("Anytype sync directory is not available")
    
    # Get default export path if not provided
    if not output_path:
        output_path = get_default_export_path(user_id, "tickets")
    
    try:
        # Get tickets for export
        tickets = get_support_tickets_for_export(db_session, user_id)
        
        # Write to JSON file
        with open(output_path, 'w') as f:
            json.dump({
                "tickets": tickets,
                "exported_at": datetime.utcnow().isoformat(),
                "user_id": user_id
            }, f, indent=2)
        
        # Update sync status
        update_sync_status(db_session, user_id, "tickets", True, len(tickets), True, None, output_path)
        
        logger.info(f"Exported {len(tickets)} tickets to {output_path}")
        return output_path
    
    except Exception as e:
        logger.error(f"Failed to export tickets to JSON: {e}")
        # Update sync status with error
        update_sync_status(db_session, user_id, "tickets", True, 0, False, str(e))
        raise

def import_support_tickets_from_json(db_session: Session, user_id: str, 
                                    input_path: Optional[str] = None) -> Tuple[int, int, int]:
    """
    Import customer support ticket data from a JSON file exported from Anytype
    
    Args:
        db_session: SQLAlchemy database session
        user_id: The user's ID
        input_path: Optional custom path for the import file
        
    Returns:
        Tuple of (created_count, updated_count, error_count)
    """
    from app.models import User, SupportTicket, TicketMessage
    
    # Get latest import file if not provided
    if not input_path:
        input_path = get_latest_import_path(user_id, "tickets")
        if not input_path:
            logger.error(f"No import file found for user {user_id}")
            update_sync_status(db_session, user_id, "tickets", False, 0, False, "No import file found")
            return (0, 0, 0)
    
    try:
        # Get user
        user = db_session.query(User).filter_by(replit_id=user_id).first()
        if not user:
            logger.error(f"User not found for ticket import: {user_id}")
            update_sync_status(db_session, user_id, "tickets", False, 0, False, "User not found")
            return (0, 0, 0)
        
        # Read JSON file
        with open(input_path, 'r') as f:
            import_data = json.load(f)
        
        tickets = import_data.get("tickets", [])
        created_count = 0
        updated_count = 0
        error_count = 0
        
        for ticket_data in tickets:
            try:
                # Check if ticket exists by ID or Anytype sync ID
                ticket_id = ticket_data.get("id")
                anytype_sync_id = ticket_data.get("anytype_sync_id")
                
                ticket = None
                if ticket_id:
                    ticket = db_session.query(SupportTicket).filter_by(id=ticket_id, user_id=user.id).first()
                
                if not ticket and anytype_sync_id:
                    ticket = db_session.query(SupportTicket).filter_by(anytype_sync_id=anytype_sync_id, user_id=user.id).first()
                
                # Update existing ticket
                if ticket:
                    # Update ticket fields
                    ticket.subject = ticket_data.get("subject", ticket.subject)
                    ticket.description = ticket_data.get("description", ticket.description)
                    ticket.status = ticket_data.get("status", ticket.status)
                    ticket.priority = ticket_data.get("priority", ticket.priority)
                    ticket.service_type = ticket_data.get("service_type", ticket.service_type)
                    ticket.anytype_sync_id = anytype_sync_id or ticket.anytype_sync_id
                    ticket.updated_at = datetime.utcnow()
                    
                    # Update messages if provided
                    if "messages" in ticket_data:
                        for msg_data in ticket_data.get("messages", []):
                            msg_id = msg_data.get("id")
                            msg = db_session.query(TicketMessage).filter_by(id=msg_id, ticket_id=ticket.id).first()
                            
                            if msg:
                                # Update existing message
                                msg.message_text = msg_data.get("message_text", msg.message_text)
                                msg.is_internal = msg_data.get("is_internal", msg.is_internal)
                            else:
                                # Create new message
                                new_msg = TicketMessage(
                                    ticket_id=ticket.id,
                                    sender_type=msg_data.get("sender_type", "user"),
                                    sender_id=user.id if msg_data.get("sender_type") == "user" else None,
                                    message_text=msg_data.get("message_text", ""),
                                    message_type=msg_data.get("message_type", "text"),
                                    is_internal=msg_data.get("is_internal", False)
                                )
                                db_session.add(new_msg)
                    
                    updated_count += 1
                
                # Create new ticket
                else:
                    new_ticket = SupportTicket(
                        user_id=user.id,
                        subject=ticket_data.get("subject", "Imported Ticket"),
                        description=ticket_data.get("description"),
                        status=ticket_data.get("status", "new"),
                        priority=ticket_data.get("priority", "medium"),
                        service_type=ticket_data.get("service_type"),
                        anytype_sync_id=anytype_sync_id
                    )
                    db_session.add(new_ticket)
                    db_session.flush()  # Flush to get the new ticket ID
                    
                    # Add messages if provided
                    for msg_data in ticket_data.get("messages", []):
                        new_msg = TicketMessage(
                            ticket_id=new_ticket.id,
                            sender_type=msg_data.get("sender_type", "user"),
                            sender_id=user.id if msg_data.get("sender_type") == "user" else None,
                            message_text=msg_data.get("message_text", ""),
                            message_type=msg_data.get("message_type", "text"),
                            is_internal=msg_data.get("is_internal", False)
                        )
                        db_session.add(new_msg)
                    
                    created_count += 1
            
            except Exception as e:
                logger.error(f"Error importing ticket: {e}")
                error_count += 1
        
        # Commit changes
        db_session.commit()
        
        # Update sync status
        total_count = created_count + updated_count
        update_sync_status(db_session, user_id, "tickets", False, total_count, True, None, input_path)
        
        logger.info(f"Imported tickets from {input_path}: {created_count} created, {updated_count} updated, {error_count} errors")
        return (created_count, updated_count, error_count)
    
    except Exception as e:
        logger.error(f"Failed to import tickets from JSON: {e}")
        db_session.rollback()
        # Update sync status with error
        update_sync_status(db_session, user_id, "tickets", False, 0, False, str(e), input_path)
        return (0, 0, 1)

def get_job_applications_for_export(db_session: Session, user_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve job application data from database for export to Anytype
    
    Args:
        db_session: SQLAlchemy database session
        user_id: The user's ID
        
    Returns:
        List of job applications in Anytype-compatible format
    """
    from app.models import User, JobApplication
    
    try:
        # Get user
        user = db_session.query(User).filter_by(replit_id=user_id).first()
        if not user:
            logger.error(f"User not found for job export: {user_id}")
            return []
        
        # Query job applications
        jobs = db_session.query(JobApplication).filter_by(user_id=user.id).order_by(JobApplication.application_date.desc()).all()
        
        # Format job applications for Anytype
        anytype_jobs = []
        for job in jobs:
            job_data = {
                "id": job.id,
                "type": "job_application",
                "position": job.position,
                "company": job.company,
                "status": job.status,
                "notes": job.notes,
                "application_date": job.application_date.isoformat() if job.application_date else None,
                "interview_date": job.interview_date.isoformat() if job.interview_date else None,
                "anytype_sync_id": job.anytype_sync_id
            }
            anytype_jobs.append(job_data)
        
        return anytype_jobs
    
    except Exception as e:
        logger.error(f"Failed to get jobs for export: {e}")
        return []

def export_job_applications_to_json(db_session: Session, user_id: str, 
                                   output_path: Optional[str] = None) -> str:
    """
    Export job applications to a JSON file for Anytype import
    
    Args:
        db_session: SQLAlchemy database session
        user_id: The user's ID
        output_path: Optional custom path for the export file
        
    Returns:
        Path to the exported JSON file
    """
    # Check sync directory
    if not check_sync_directory():
        raise RuntimeError("Anytype sync directory is not available")
    
    # Get default export path if not provided
    if not output_path:
        output_path = get_default_export_path(user_id, "jobs")
    
    try:
        # Get job applications for export
        jobs = get_job_applications_for_export(db_session, user_id)
        
        # Write to JSON file
        with open(output_path, 'w') as f:
            json.dump({
                "job_applications": jobs,
                "exported_at": datetime.utcnow().isoformat(),
                "user_id": user_id
            }, f, indent=2)
        
        # Update sync status
        update_sync_status(db_session, user_id, "jobs", True, len(jobs), True, None, output_path)
        
        logger.info(f"Exported {len(jobs)} job applications to {output_path}")
        return output_path
    
    except Exception as e:
        logger.error(f"Failed to export job applications to JSON: {e}")
        # Update sync status with error
        update_sync_status(db_session, user_id, "jobs", True, 0, False, str(e))
        raise

def import_job_applications_from_json(db_session: Session, user_id: str, 
                                     input_path: Optional[str] = None) -> Tuple[int, int, int]:
    """
    Import job applications from a JSON file exported from Anytype
    
    Args:
        db_session: SQLAlchemy database session
        user_id: The user's ID
        input_path: Optional custom path for the import file
        
    Returns:
        Tuple of (created_count, updated_count, error_count)
    """
    from app.models import User, JobApplication
    
    # Get latest import file if not provided
    if not input_path:
        input_path = get_latest_import_path(user_id, "jobs")
        if not input_path:
            logger.error(f"No import file found for user {user_id}")
            update_sync_status(db_session, user_id, "jobs", False, 0, False, "No import file found")
            return (0, 0, 0)
    
    try:
        # Get user
        user = db_session.query(User).filter_by(replit_id=user_id).first()
        if not user:
            logger.error(f"User not found for job import: {user_id}")
            update_sync_status(db_session, user_id, "jobs", False, 0, False, "User not found")
            return (0, 0, 0)
        
        # Read JSON file
        with open(input_path, 'r') as f:
            import_data = json.load(f)
        
        jobs = import_data.get("job_applications", [])
        created_count = 0
        updated_count = 0
        error_count = 0
        
        for job_data in jobs:
            try:
                # Check if job exists by ID or Anytype sync ID
                job_id = job_data.get("id")
                anytype_sync_id = job_data.get("anytype_sync_id")
                
                job = None
                if job_id:
                    job = db_session.query(JobApplication).filter_by(id=job_id, user_id=user.id).first()
                
                if not job and anytype_sync_id:
                    job = db_session.query(JobApplication).filter_by(anytype_sync_id=anytype_sync_id, user_id=user.id).first()
                
                # Update existing job application
                if job:
                    # Update job fields
                    job.position = job_data.get("position", job.position)
                    job.company = job_data.get("company", job.company)
                    job.status = job_data.get("status", job.status)
                    job.notes = job_data.get("notes", job.notes)
                    
                    # Parse dates if provided
                    if "interview_date" in job_data and job_data["interview_date"]:
                        try:
                            job.interview_date = datetime.fromisoformat(job_data["interview_date"])
                        except ValueError:
                            logger.warning(f"Invalid interview date format: {job_data['interview_date']}")
                    
                    job.anytype_sync_id = anytype_sync_id or job.anytype_sync_id
                    updated_count += 1
                
                # Create new job application
                else:
                    new_job = JobApplication(
                        user_id=user.id,
                        position=job_data.get("position", "Imported Job"),
                        company=job_data.get("company"),
                        status=job_data.get("status", "applied"),
                        notes=job_data.get("notes"),
                        anytype_sync_id=anytype_sync_id
                    )
                    
                    # Parse dates if provided
                    if "interview_date" in job_data and job_data["interview_date"]:
                        try:
                            new_job.interview_date = datetime.fromisoformat(job_data["interview_date"])
                        except ValueError:
                            logger.warning(f"Invalid interview date format: {job_data['interview_date']}")
                    
                    db_session.add(new_job)
                    created_count += 1
            
            except Exception as e:
                logger.error(f"Error importing job application: {e}")
                error_count += 1
        
        # Commit changes
        db_session.commit()
        
        # Update sync status
        total_count = created_count + updated_count
        update_sync_status(db_session, user_id, "jobs", False, total_count, True, None, input_path)
        
        logger.info(f"Imported job applications from {input_path}: {created_count} created, {updated_count} updated, {error_count} errors")
        return (created_count, updated_count, error_count)
    
    except Exception as e:
        logger.error(f"Failed to import job applications from JSON: {e}")
        db_session.rollback()
        # Update sync status with error
        update_sync_status(db_session, user_id, "jobs", False, 0, False, str(e), input_path)
        return (0, 0, 1)

def export_single_ticket_to_json(db_session: Session, ticket_id: int, user_id: str) -> Optional[str]:
    """
    Export a single support ticket to a JSON file for Anytype import
    
    Args:
        db_session: SQLAlchemy database session
        ticket_id: ID of the ticket to export
        user_id: The user's ID
        
    Returns:
        Path to the exported JSON file, or None if export failed
    """
    from app.models import User, SupportTicket
    
    try:
        # Get user
        user = db_session.query(User).filter_by(replit_id=user_id).first()
        if not user:
            logger.error(f"User not found for ticket export: {user_id}")
            return None
        
        # Get ticket
        ticket = db_session.query(SupportTicket).filter_by(id=ticket_id, user_id=user.id).first()
        if not ticket:
            logger.error(f"Ticket not found or access denied: {ticket_id}")
            return None
        
        # Create export data
        tickets = get_support_tickets_for_export(db_session, user_id, None)
        ticket_data = next((t for t in tickets if t["id"] == ticket_id), None)
        
        if not ticket_data:
            logger.error(f"Failed to format ticket for export: {ticket_id}")
            return None
        
        # Get export path
        output_path = get_default_export_path(user_id, f"ticket_{ticket_id}")
        
        # Write to JSON file
        with open(output_path, 'w') as f:
            json.dump({
                "tickets": [ticket_data],
                "exported_at": datetime.utcnow().isoformat(),
                "user_id": user_id
            }, f, indent=2)
        
        logger.info(f"Exported ticket {ticket_id} to {output_path}")
        return output_path
    
    except Exception as e:
        logger.error(f"Failed to export ticket to JSON: {e}")
        return None

def export_single_job_to_json(db_session: Session, job_id: int, user_id: str) -> Optional[str]:
    """
    Export a single job application to a JSON file for Anytype import
    
    Args:
        db_session: SQLAlchemy database session
        job_id: ID of the job application to export
        user_id: The user's ID
        
    Returns:
        Path to the exported JSON file, or None if export failed
    """
    from app.models import User, JobApplication
    
    try:
        # Get user
        user = db_session.query(User).filter_by(replit_id=user_id).first()
        if not user:
            logger.error(f"User not found for job export: {user_id}")
            return None
        
        # Get job application
        job = db_session.query(JobApplication).filter_by(id=job_id, user_id=user.id).first()
        if not job:
            logger.error(f"Job application not found or access denied: {job_id}")
            return None
        
        # Create export data
        jobs = get_job_applications_for_export(db_session, user_id)
        job_data = next((j for j in jobs if j["id"] == job_id), None)
        
        if not job_data:
            logger.error(f"Failed to format job application for export: {job_id}")
            return None
        
        # Get export path
        output_path = get_default_export_path(user_id, f"job_{job_id}")
        
        # Write to JSON file
        with open(output_path, 'w') as f:
            json.dump({
                "job_applications": [job_data],
                "exported_at": datetime.utcnow().isoformat(),
                "user_id": user_id
            }, f, indent=2)
        
        logger.info(f"Exported job application {job_id} to {output_path}")
        return output_path
    
    except Exception as e:
        logger.error(f"Failed to export job application to JSON: {e}")
        return None

def get_sync_status(db_session: Session, user_id: str) -> Dict[str, Any]:
    """
    Get Anytype synchronization status for a user
    
    Args:
        db_session: SQLAlchemy database session
        user_id: The user's ID
        
    Returns:
        Dictionary with sync status information
    """
    from app.models import User, AnytypeSyncStatus
    
    try:
        # Get user
        user = db_session.query(User).filter_by(replit_id=user_id).first()
        if not user:
            logger.error(f"User not found for sync status: {user_id}")
            return {"error": "User not found"}
        
        # Get sync status records
        statuses = db_session.query(AnytypeSyncStatus).filter_by(user_id=user.id).all()
        
        result = {
            "sync_directory": os.environ.get('ANYTYPE_SYNC_DIR', DEFAULT_SYNC_DIR),
            "directory_available": check_sync_directory(),
            "user_id": user_id,
            "data_types": {}
        }
        
        # Format status by data type
        for status in statuses:
            result["data_types"][status.data_type] = {
                "last_export_time": status.last_export_time.isoformat() if status.last_export_time else None,
                "last_import_time": status.last_import_time.isoformat() if status.last_import_time else None,
                "export_count": status.export_count,
                "import_count": status.import_count,
                "last_sync_status": status.last_sync_status,
                "error_message": status.error_message,
                "sync_file": status.sync_file
            }
        
        # Add placeholder for missing data types
        for data_type in ["tickets", "jobs"]:
            if data_type not in result["data_types"]:
                result["data_types"][data_type] = {
                    "last_export_time": None,
                    "last_import_time": None,
                    "export_count": 0,
                    "import_count": 0,
                    "last_sync_status": "none",
                    "error_message": None,
                    "sync_file": None
                }
        
        return result
    
    except Exception as e:
        logger.error(f"Failed to get sync status: {e}")
        return {"error": str(e)}