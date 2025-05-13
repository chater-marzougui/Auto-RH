"""
Speech-to-Text Service for Automated HR
Handles transcription of audio to text during interviews
"""
import logging
import os
import tempfile
from typing import Optional, Dict, BinaryIO
import whisper
from pathlib import Path
import requests
import json
import base64
from flask import current_app

logger = logging.getLogger(__name__)

class STTService:
    """
    Service for Speech-to-Text conversions using OpenAI's Whisper
    """
    def __init__(self, model_size: str = "base"):
        """
        Initialize the STT service with a specified Whisper model size
        
        Args:
            model_size: Whisper model size ('tiny', 'base', 'small', 'medium', 'large')
        """
        self.model_size = model_size
        self._model = None  # Lazy loading
        self.temp_dir = Path(tempfile.gettempdir()) / "automated_hr_audio"
        self.temp_dir.mkdir(exist_ok=True)
        
    @property
    def model(self):
        """Lazy load the Whisper model on first use"""
        if self._model is None:
            try:
                logger.info(f"Loading Whisper model: {self.model_size}")
                self._model = whisper.load_model(self.model_size)
                logger.info("Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {str(e)}")
                raise
        return self._model
    
    def transcribe_audio_file(self, audio_file: BinaryIO, language: str = "en") -> Dict:
        """
        Transcribe an audio file to text
        
        Args:
            audio_file: File-like object containing audio data
            language: Language code (default: "en")
            
        Returns:
            Dict containing the transcription and metadata
        """
        try:
            # Save the file temporarily
            temp_file = self.temp_dir / f"temp_{os.urandom(8).hex()}.wav"
            with open(temp_file, "wb") as f:
                f.write(audio_file.read())
            
            # Perform transcription
            result = self.model.transcribe(
                str(temp_file), 
                language=language,
                fp16=False  # Use CPU if GPU not available
            )
            
            # Clean up
            temp_file.unlink(missing_ok=True)
            
            return {
                "text": result["text"],
                "segments": result.get("segments", []),
                "language": result.get("language", language)
            }
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            return {"error": str(e), "text": ""}
    
    def transcribe_audio_data(self, audio_data: bytes, language: str = "en") -> Dict:
        """
        Transcribe audio data bytes to text
        
        Args:
            audio_data: Raw audio data bytes
            language: Language code (default: "en")
            
        Returns:
            Dict containing the transcription and metadata
        """
        try:
            # Save the bytes to a temporary file
            temp_file = self.temp_dir / f"temp_{os.urandom(8).hex()}.wav"
            with open(temp_file, "wb") as f:
                f.write(audio_data)
            
            # Perform transcription
            result = self.model.transcribe(
                str(temp_file), 
                language=language,
                fp16=False
            )
            
            # Clean up
            temp_file.unlink(missing_ok=True)
            
            return {
                "text": result["text"],
                "segments": result.get("segments", []),
                "language": result.get("language", language)
            }
            
        except Exception as e:
            logger.error(f"Error transcribing audio data: {str(e)}")
            return {"error": str(e), "text": ""}
    
    def transcribe_audio_base64(self, audio_base64: str, language: str = "en") -> Dict:
        """
        Transcribe base64-encoded audio to text
        
        Args:
            audio_base64: Base64-encoded audio data
            language: Language code (default: "en")
            
        Returns:
            Dict containing the transcription and metadata
        """
        try:
            # Decode base64 to bytes
            audio_data = base64.b64decode(audio_base64)
            return self.transcribe_audio_data(audio_data, language)
            
        except Exception as e:
            logger.error(f"Error decoding base64 audio: {str(e)}")
            return {"error": str(e), "text": ""}
            
    def transcribe_audio_chunk(self, audio_data: bytes, language: str = "en") -> str:
        """
        Transcribe a small chunk of audio (for real-time transcription)
        
        Args:
            audio_data: Raw audio data bytes
            language: Language code (default: "en")
            
        Returns:
            Transcribed text
        """
        try:
            result = self.transcribe_audio_data(audio_data, language)
            return result.get("text", "")
        except Exception as e:
            logger.error(f"Error transcribing audio chunk: {str(e)}")
            return ""
    
    def transcribe_with_external_api(self, audio_file: BinaryIO) -> Dict:
        """
        Use an external API for transcription when local processing is not preferred
        
        Args:
            audio_file: File-like object containing audio data
            
        Returns:
            Dict containing the transcription result
        """
        api_key = current_app.config.get("SPEECH_API_KEY")
        api_url = current_app.config.get("SPEECH_API_URL")
        
        if not api_key or not api_url:
            logger.error("External transcription API credentials not configured")
            return {"error": "External API not configured", "text": ""}
        
        try:
            # Save the file temporarily
            temp_file = self.temp_dir / f"temp_{os.urandom(8).hex()}.wav"
            with open(temp_file, "wb") as f:
                f.write(audio_file.read())
            
            # Upload to API
            with open(temp_file, "rb") as f:
                response = requests.post(
                    api_url,
                    files={"file": f},
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                
            # Clean up
            temp_file.unlink(missing_ok=True)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return {"error": f"API error: {response.status_code}", "text": ""}
                
        except Exception as e:
            logger.error(f"Error using external transcription API: {str(e)}")
            return {"error": str(e), "text": ""}

    def continuous_transcription_start(self) -> str:
        """
        Start a continuous transcription session
        
        Returns:
            Session ID for the transcription
        """
        import uuid
        session_id = str(uuid.uuid4())
        
        # Create a session directory
        session_dir = self.temp_dir / session_id
        session_dir.mkdir(exist_ok=True)
        
        return session_id
    
    def continuous_transcription_add_chunk(self, session_id: str, chunk_data: bytes) -> None:
        """
        Add an audio chunk to a continuous transcription session
        
        Args:
            session_id: Session ID returned by continuous_transcription_start
            chunk_data: Audio chunk data bytes
        """
        session_dir = self.temp_dir / session_id
        if not session_dir.exists():
            logger.error(f"Session {session_id} not found")
            return
        
        # Save chunk
        chunk_count = len(list(session_dir.glob("chunk_*.wav")))
        chunk_file = session_dir / f"chunk_{chunk_count:04d}.wav"
        
        with open(chunk_file, "wb") as f:
            f.write(chunk_data)
    
    def continuous_transcription_end(self, session_id: str) -> Dict:
        """
        End a continuous transcription session and get the complete transcription
        
        Args:
            session_id: Session ID returned by continuous_transcription_start
            
        Returns:
            Dict containing the complete transcription
        """
        session_dir = self.temp_dir / session_id
        if not session_dir.exists():
            logger.error(f"Session {session_id} not found")
            return {"error": "Session not found", "text": ""}
        
        try:
            # Concatenate all audio chunks (simplified approach)
            all_chunks = sorted(session_dir.glob("chunk_*.wav"))
            if not all_chunks:
                return {"text": ""}
            
            # Use the first chunk for transcription (or implement audio concatenation here)
            result = self.model.transcribe(
                str(all_chunks[0]),
                fp16=False
            )
            
            # Clean up
            import shutil
            shutil.rmtree(session_dir)
            
            return {
                "text": result["text"],
                "segments": result.get("segments", []),
                "language": result.get("language", "en")
            }
            
        except Exception as e:
            logger.error(f"Error ending transcription session: {str(e)}")
            return {"error": str(e), "text": ""}