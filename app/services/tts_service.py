"""
Text-to-Speech Service - Handles conversion of text to spoken audio

This module provides functionality for:
- Converting text to speech using pyttsx3 library
- Managing audio files for interviews
- Supporting different voices and languages
"""
import os
import json
import time
import tempfile
import hashlib
from typing import Dict, Optional, Tuple, BinaryIO
import pyttsx3
import io
from pathlib import Path
import wave

class TTSService:
    """Service for Text-to-Speech conversion using pyttsx3 library."""
    
    def __init__(self, provider="pyttsx3"):
        """Initialize the TTS service.
        
        Args:
            provider: The TTS engine provider (always "pyttsx3" for this implementation)
        """
        self.provider = provider
        
        # Initialize the TTS engine
        self._engine = None  # Lazy initialization
        
        # Default voice settings
        self.default_voice_id = None  # Will be set during initialization
        
        # Set up cache directory for audio files
        self.cache_dir = os.path.join(tempfile.gettempdir(), 'tts_cache')
        os.makedirs(self.cache_dir, exist_ok=True)
    
    @property
    def engine(self):
        """Lazy load the TTS engine on first use"""
        if self._engine is None:
            try:
                self._engine = pyttsx3.init()
                # Set a default voice if available
                voices = self._engine.getProperty('voices')
                if voices:
                    self.default_voice_id = voices[0].id
                    self._engine.setProperty('voice', self.default_voice_id)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize pyttsx3 engine: {str(e)}")
        return self._engine
    
    def text_to_speech(self, text: str, voice_id: str = None, 
                      language: str = "en", 
                      output_format: str = "mp3") -> Tuple[bytes, str]:
        """Convert text to speech using pyttsx3.
        
        Args:
            text: The text to convert to speech
            voice_id: Optional voice ID or name
            language: Language code (default: "en")
            output_format: Output format (mp3 or wav)
            
        Returns:
            Tuple of (audio_bytes, content_type)
        """
        # Use default voice if not specified
        voice_id = voice_id or self.default_voice_id
        
        # Create a hash of the input parameters for caching
        text_hash = hashlib.md5(text.encode()).hexdigest()
        cache_key = f"{voice_id}_{language}_{text_hash}"
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.{output_format}")
        
        # Check if we have this in cache
        if os.path.exists(cache_file):
            with open(cache_file, 'rb') as f:
                content_type = 'audio/wav' if output_format.lower() == 'wav' else 'audio/mpeg'
                return f.read(), content_type
        
        # Set voice if specified
        if voice_id:
            self.engine.setProperty('voice', voice_id)
        
        # Set rate and volume
        self.engine.setProperty('rate', 150)    # Speed of speech
        self.engine.setProperty('volume', 0.9)  # Volume (0.0 to 1.0)
        
        # Generate speech to a temporary WAV file
        temp_wav_file = os.path.join(self.cache_dir, f"temp_{text_hash}.wav")
        
        # Use the engine to save to a file
        self.engine.save_to_file(text, temp_wav_file)
        self.engine.runAndWait()
        
        # Read the file bytes
        with open(temp_wav_file, 'rb') as f:
            audio_data = f.read()
        
        # Convert to requested format if not WAV
        if output_format.lower() != 'wav':
            try:
                audio_data = self._convert_wav_to_mp3(audio_data)
                content_type = 'audio/mpeg'
            except ImportError:
                # If conversion fails, fall back to WAV
                output_format = 'wav'
                content_type = 'audio/wav'
        else:
            content_type = 'audio/wav'
        
        # Save to cache
        with open(cache_file, 'wb') as f:
            f.write(audio_data)
        
        # Clean up temp file
        if os.path.exists(temp_wav_file):
            os.remove(temp_wav_file)
        
        return audio_data, content_type
    
    def _convert_wav_to_mp3(self, wav_data: bytes) -> bytes:
        """Convert WAV data to MP3 format.
        
        Args:
            wav_data: WAV audio data
            
        Returns:
            MP3 audio data
        """
        try:
            from pydub import AudioSegment
            
            # Create a temporary WAV file
            temp_wav = os.path.join(self.cache_dir, f"temp_convert_{os.urandom(4).hex()}.wav")
            temp_mp3 = os.path.join(self.cache_dir, f"temp_convert_{os.urandom(4).hex()}.mp3")
            
            with open(temp_wav, 'wb') as f:
                f.write(wav_data)
            
            # Convert WAV to MP3
            audio = AudioSegment.from_wav(temp_wav)
            audio.export(temp_mp3, format="mp3")
            
            # Read the MP3 data
            with open(temp_mp3, 'rb') as f:
                mp3_data = f.read()
            
            # Clean up temp files
            os.remove(temp_wav)
            os.remove(temp_mp3)
            
            return mp3_data
        except ImportError:
            raise ImportError("pydub library required for MP3 conversion. Install with: pip install pydub")
    
    def get_available_voices(self) -> Dict:
        """Get available voices from the TTS engine.
        
        Returns:
            Dictionary with available voices
        """
        voices = self.engine.getProperty('voices')
        
        formatted_voices = []
        for voice in voices:
            # Extract language from the voice ID (format varies by platform)
            language = "en"  # Default
            if 'language' in dir(voice):
                language = voice.language
            elif '_' in voice.id:
                language = voice.id.split('_')[0]
            
            # Determine gender (not always available)
            gender = "UNKNOWN"
            if 'gender' in dir(voice):
                gender = voice.gender
            
            formatted_voices.append({
                "voice_id": voice.id,
                "name": voice.name,
                "language": language,
                "gender": gender
            })
        
        return {"voices": formatted_voices}
    
    def stream_audio_response(self, text: str, voice_id: str = None):
        """Create a streaming response for audio playback.
        
        Args:
            text: The text to convert to speech
            voice_id: Optional voice ID or name
            
        Returns:
            Audio data and content type for streaming
        """
        return self.text_to_speech(text, voice_id)
    
    def save_audio_file(self, text: str, filepath: str, 
                       voice_id: str = None) -> str:
        """Save TTS output to a file.
        
        Args:
            text: The text to convert to speech
            filepath: Path where the file should be saved
            voice_id: Optional voice ID or name
            
        Returns:
            Path to the saved file
        """
        # Determine output format from file extension
        output_format = Path(filepath).suffix[1:].lower()
        if output_format not in ('wav', 'mp3'):
            output_format = 'wav'  # Default to WAV
        
        audio_data, _ = self.text_to_speech(text, voice_id, output_format=output_format)
        
        with open(filepath, 'wb') as f:
            f.write(audio_data)
            
        return filepath
    
    def clear_cache(self, max_age_hours: int = 24) -> int:
        """Clear old cached TTS files.
        
        Args:
            max_age_hours: Maximum age of files to keep (in hours)
            
        Returns:
            Number of files deleted
        """
        now = time.time()
        max_age_seconds = max_age_hours * 3600
        deleted_count = 0
        
        for filename in os.listdir(self.cache_dir):
            filepath = os.path.join(self.cache_dir, filename)
            
            if os.path.isfile(filepath):
                file_age = now - os.path.getmtime(filepath)
                
                if file_age > max_age_seconds:
                    os.remove(filepath)
                    deleted_count += 1
                    
        return deleted_count
    
    def say(self, text: str, voice_id: str = None):
        """Directly speak the text without saving to file.
        
        Args:
            text: The text to speak
            voice_id: Optional voice ID
        """
        # Set voice if specified
        if voice_id:
            self.engine.setProperty('voice', voice_id)
            
        # Speak the text
        self.engine.say(text)
        self.engine.runAndWait()
    
    def adjust_voice_properties(self, rate: int = None, volume: float = None, 
                               voice_id: str = None):
        """Adjust voice properties.
        
        Args:
            rate: Speech rate (words per minute)
            volume: Volume (0.0 to 1.0)
            voice_id: Voice ID
        """
        if rate is not None:
            self.engine.setProperty('rate', rate)
            
        if volume is not None:
            self.engine.setProperty('volume', max(0.0, min(1.0, volume)))
            
        if voice_id is not None:
            self.engine.setProperty('voice', voice_id)