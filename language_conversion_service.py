"""
Language Conversion Service for the ASL Customer Support System.

This module provides services for converting between different forms of communication:
- Voice to Text (Speech Recognition)
- Text to Sign Language
- Sign Language to Text
- Text to Voice (Text-to-Speech)
"""

import logging
import os
import json
import base64
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check for API keys
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not set. Voice-to-text functionality may be limited.")

# Import necessary libraries for voice processing
# Initialize OpenAI client if API key is available
client = None
OPENAI_MODEL = "gpt-4o"  # the newest OpenAI model as of May 13, 2024
if OPENAI_API_KEY:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
    except ImportError:
        logger.error("OpenAI library not installed. Voice processing will not work.")


class LanguageConversionService:
    """Service for converting between different language modalities."""
    
    def __init__(self):
        """Initialize the language conversion service."""
        self.openai_client = client
        self.sign_gestures_map = self._load_sign_gestures_map()
    
    def _load_sign_gestures_map(self) -> Dict[str, Any]:
        """
        Load the mapping between words/phrases and sign language gestures.
        
        Returns:
            Dictionary mapping words to sign gestures
        """
        # This is a placeholder for a more sophisticated mapping system
        # In a real implementation, this would load from a database or API
        basic_gestures = {
            "hello": {"gesture_id": "g_hello", "animation": "hello.mp4"},
            "thank you": {"gesture_id": "g_thankyou", "animation": "thankyou.mp4"},
            "help": {"gesture_id": "g_help", "animation": "help.mp4"},
            "yes": {"gesture_id": "g_yes", "animation": "yes.mp4"},
            "no": {"gesture_id": "g_no", "animation": "no.mp4"},
            "please": {"gesture_id": "g_please", "animation": "please.mp4"},
            "how are you": {"gesture_id": "g_howareyou", "animation": "howareyou.mp4"},
            "good": {"gesture_id": "g_good", "animation": "good.mp4"},
            "bad": {"gesture_id": "g_bad", "animation": "bad.mp4"},
            "name": {"gesture_id": "g_name", "animation": "name.mp4"},
            "what": {"gesture_id": "g_what", "animation": "what.mp4"},
            "who": {"gesture_id": "g_who", "animation": "who.mp4"},
            "when": {"gesture_id": "g_when", "animation": "when.mp4"},
            "where": {"gesture_id": "g_where", "animation": "where.mp4"},
            "why": {"gesture_id": "g_why", "animation": "why.mp4"},
            "how": {"gesture_id": "g_how", "animation": "how.mp4"},
        }
        return basic_gestures
    
    async def voice_to_text(self, audio_file_data: bytes) -> Dict[str, Any]:
        """
        Convert voice/audio to text using OpenAI's Whisper API.
        
        Args:
            audio_file_data: Raw audio data as bytes
            
        Returns:
            Dictionary containing the transcription and metadata
        """
        if not self.openai_client:
            logger.warning("OpenAI client not available. Cannot process voice to text.")
            return {
                "success": False,
                "error": "OpenAI API key not configured",
                "text": "",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        temp_file_path = None
        try:
            # Create a temporary file for the audio data
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_file.write(audio_file_data)
                temp_file_path = temp_file.name
            
            with open(temp_file_path, "rb") as audio_file:
                # Transcribe audio using OpenAI's Whisper API
                response = self.openai_client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file
                )
                
                # Return the transcription
                return {
                    "success": True,
                    "text": response.text,
                    "model": "whisper-1",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error in voice to text conversion: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "timestamp": datetime.utcnow().isoformat()
            }
        finally:
            # Clean up the temporary file
            if temp_file_path:
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.error(f"Failed to remove temporary file: {str(e)}")
                    pass
    
    async def text_to_sign_sequence(self, text: str) -> Dict[str, Any]:
        """
        Convert text to a sequence of sign language gestures.
        
        Args:
            text: Input text to convert
            
        Returns:
            Dictionary containing sign gesture IDs and metadata
        """
        try:
            # Normalize text: lowercase, remove extra spaces
            normalized_text = text.lower().strip()
            
            # Tokenize the text into words and phrases
            # This is a simplified approach; a more sophisticated NLP-based
            # approach would be needed for a production system
            words = normalized_text.split()
            
            # Match words and phrases to sign gestures
            gestures = []
            i = 0
            while i < len(words):
                # Try matching multi-word phrases first (up to 3 words)
                matched = False
                for phrase_length in range(min(3, len(words) - i), 0, -1):
                    phrase = " ".join(words[i:i+phrase_length])
                    if phrase in self.sign_gestures_map:
                        gestures.append({
                            "text": phrase,
                            "gesture_id": self.sign_gestures_map[phrase]["gesture_id"],
                            "animation": self.sign_gestures_map[phrase]["animation"]
                        })
                        i += phrase_length
                        matched = True
                        break
                
                # If no phrase matched, add the word as-is (fingerspelling would be used)
                if not matched:
                    gestures.append({
                        "text": words[i],
                        "gesture_id": f"spell_{words[i]}",
                        "animation": "fingerspell.mp4",  # Generic animation
                        "fingerspell": True
                    })
                    i += 1
            
            return {
                "success": True,
                "original_text": text,
                "gestures": gestures,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in text to sign conversion: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "original_text": text,
                "gestures": [],
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def analyze_sign_video(self, video_data: bytes) -> Dict[str, Any]:
        """
        Analyze a sign language video and convert to text.
        
        Args:
            video_data: Raw video data as bytes
            
        Returns:
            Dictionary containing recognized text and metadata
        """
        # This would typically use a machine learning model trained on sign language
        # For this implementation, we'll return a placeholder response
        # In a real system, this would call a specialized ASL recognition model
        
        return {
            "success": False,
            "error": "Sign language video analysis not implemented yet",
            "text": "",
            "confidence": 0.0,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def text_to_voice(self, text: str) -> Dict[str, Any]:
        """
        Convert text to speech using OpenAI's TTS API.
        
        Args:
            text: Text to convert to speech
            
        Returns:
            Dictionary containing audio data and metadata
        """
        if not self.openai_client:
            logger.warning("OpenAI client not available. Cannot process text to voice.")
            return {
                "success": False,
                "error": "OpenAI API key not configured",
                "audio": None,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        try:
            # Use OpenAI's TTS API
            response = self.openai_client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text
            )
            
            # Get audio bytes
            audio_bytes = response.read()
            
            # Convert to base64 for web transmission
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            return {
                "success": True,
                "text": text,
                "audio_base64": audio_base64,
                "mime_type": "audio/mp3",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in text to voice conversion: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "text": text,
                "audio_base64": None,
                "timestamp": datetime.utcnow().isoformat()
            }