"""
Text-to-Speech Service - Handles conversion of text to spoken audio

This module provides functionality for:
- Converting text to speech using ElevenLabs or Google Cloud TTS
- Managing audio files for interviews
- Supporting different voices and languages
"""
import os
import json
import time
import requests
import base64
from typing import Dict, Optional, Tuple, BinaryIO
from flask import current_app, Response
import tempfile


class TTSService:
    """Service for Text-to-Speech conversion using various providers."""
    
    def __init__(self, provider="elevenlabs"):
        """Initialize the TTS service.
        
        Args:
            provider: The TTS provider to use ('elevenlabs' or 'google')
        """
        self.provider = provider
        self.elevenlabs_api_key = os.environ.get('ELEVENLABS_API_KEY') or current_app.config.get('ELEVENLABS_API_KEY')
        self.google_api_key = os.environ.get('GOOGLE_API_KEY') or current_app.config.get('GOOGLE_API_KEY')
        
        # Default voice settings
        self.default_elevenlabs_voice = "Adam"  # Default ElevenLabs voice ID
        self.default_google_voice = "en-US-Standard-D"  # Default Google voice
        
        # ElevenLabs API endpoints
        self.elevenlabs_tts_url = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        self.elevenlabs_voices_url = "https://api.elevenlabs.io/v1/voices"
        
        # Google Cloud TTS API endpoint
        self.google_tts_url = "https://texttospeech.googleapis.com/v1/text:synthesize"
        
        # Set up cache directory for audio files
        self.cache_dir = os.path.join(tempfile.gettempdir(), 'tts_cache')
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def text_to_speech(self, text: str, voice_id: str = None, 
                      language: str = "en", 
                      output_format: str = "mp3") -> Tuple[bytes, str]:
        """Convert text to speech using the configured provider.
        
        Args:
            text: The text to convert to speech
            voice_id: Optional voice ID or name
            language: Language code (default: "en")
            output_format: Output format (mp3 or wav)
            
        Returns:
            Tuple of (audio_bytes, content_type)
        """
        if self.provider == "elevenlabs":
            return self._elevenlabs_tts(text, voice_id)
        else:  # Default to Google TTS
            return self._google_tts(text, voice_id, language, output_format)
    
    def _elevenlabs_tts(self, text: str, voice_id: str = None) -> Tuple[bytes, str]:
        """Use ElevenLabs for text-to-speech conversion.
        
        Args:
            text: The text to convert to speech
            voice_id: Optional ElevenLabs voice ID
            
        Returns:
            Tuple of (audio_bytes, content_type)
        """
        if not self.elevenlabs_api_key:
            raise ValueError("ElevenLabs API key not configured")
        
        # Use default voice if not specified
        voice_id = voice_id or self.default_elevenlabs_voice
        
        # Check cache first (simple hash-based caching)
        cache_key = f"{voice_id}_{hash(text)}"
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.mp3")
        
        if os.path.exists(cache_file):
            with open(cache_file, 'rb') as f:
                return f.read(), 'audio/mpeg'
        
        # Prepare the request
        url = self.elevenlabs_tts_url.format(voice_id=voice_id)
        headers = {
            "xi-api-key": self.elevenlabs_api_key,
            "Content-Type": "application/json"
        }
        
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        # Make the API request
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code != 200:
            current_app.logger.error(f"ElevenLabs API error: {response.status_code} - {response.text}")
            raise requests.exceptions.HTTPError(f"ElevenLabs API error: {response.status_code}")
        
        # Save to cache
        with open(cache_file, 'wb') as f:
            f.write(response.content)
        
        return response.content, 'audio/mpeg'
    
    def _google_tts(self, text: str, voice_name: str = None, 
                   language: str = "en-US", 
                   output_format: str = "mp3") -> Tuple[bytes, str]:
        """Use Google Cloud Text-to-Speech for conversion.
        
        Args:
            text: The text to convert to speech
            voice_name: Optional Google TTS voice name
            language: Language code (default: "en-US")
            output_format: Output format (mp3 or wav)
            
        Returns:
            Tuple of (audio_bytes, content_type)
        """
        if not self.google_api_key:
            raise ValueError("Google API key not configured")
        
        # Use default voice if not specified
        voice_name = voice_name or self.default_google_voice
        
        # Determine audio format
        if output_format.lower() == "mp3":
            audio_encoding = "MP3"
            content_type = "audio/mpeg"
        else:
            audio_encoding = "LINEAR16"
            content_type = "audio/wav"
        
        # Check cache first
        cache_key = f"google_{voice_name}_{language}_{hash(text)}"
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.{output_format}")
        
        if os.path.exists(cache_file):
            with open(cache_file, 'rb') as f:
                return f.read(), content_type
        
        # Prepare the request
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.google_api_key
        }
        
        data = {
            "input": {"text": text},
            "voice": {
                "languageCode": language,
                "name": voice_name
            },
            "audioConfig": {
                "audioEncoding": audio_encoding
            }
        }
        
        # Make the API request
        response = requests.post(self.google_tts_url, headers=headers, json=data)
        
        if response.status_code != 200:
            current_app.logger.error(f"Google TTS API error: {response.status_code} - {response.text}")
            raise requests.exceptions.HTTPError(f"Google TTS API error: {response.status_code}")
        
        # Decode the base64 audio content
        audio_content = base64.b64decode(response.json()["audioContent"])
        
        # Save to cache
        with open(cache_file, 'wb') as f:
            f.write(audio_content)
        
        return audio_content, content_type
    
    def get_available_voices(self) -> Dict:
        """Get available voices from the current provider.
        
        Returns:
            Dictionary with available voices
        """
        if self.provider == "elevenlabs":
            return self._get_elevenlabs_voices()
        else:
            return self._get_google_voices()
    
    def _get_elevenlabs_voices(self) -> Dict:
        """Get available voices from ElevenLabs.
        
        Returns:
            Dictionary with voice information
        """
        if not self.elevenlabs_api_key:
            return {"error": "ElevenLabs API key not configured"}
        
        headers = {
            "xi-api-key": self.elevenlabs_api_key
        }
        
        response = requests.get(self.elevenlabs_voices_url, headers=headers)
        
        if response.status_code != 200:
            return {"error": f"Failed to get voices: {response.status_code}"}
        
        # Format the voice data
        voices_data = response.json()
        formatted_voices = [{
            "voice_id": voice["voice_id"],
            "name": voice["name"],
            "preview_url": voice.get("preview_url", ""),
            "category": voice.get("category", "")
        } for voice in voices_data.get("voices", [])]
        
        return {"voices": formatted_voices}
    
    def _get_google_voices(self) -> Dict:
        """Get standard Google TTS voices.
        
        Returns:
            Dictionary with voice information
        """
        # This is a simplified version - in production, you should fetch from the API
        standard_voices = [
            {"name": "en-US-Standard-A", "language": "en-US", "gender": "FEMALE"},
            {"name": "en-US-Standard-B", "language": "en-US", "gender": "MALE"},
            {"name": "en-US-Standard-C", "language": "en-US", "gender": "FEMALE"},
            {"name": "en-US-Standard-D", "language": "en-US", "gender": "MALE"},
            {"name": "en-US-Standard-E", "language": "en-US", "gender": "FEMALE"},
            {"name": "en-US-Standard-F", "language": "en-US", "gender": "FEMALE"},
            {"name": "en-US-Standard-G", "language": "en-US", "gender": "MALE"},
            {"name": "en-US-Standard-H", "language": "en-US", "gender": "FEMALE"},
            {"name": "en-US-Standard-I", "language": "en-US", "gender": "MALE"},
            {"name": "en-US-Standard-J", "language": "en-US", "gender": "MALE"},
            {"name": "en-GB-Standard-A", "language": "en-GB", "gender": "FEMALE"},
            {"name": "en-GB-Standard-B", "language": "en-GB", "gender": "MALE"},
            {"name": "en-GB-Standard-C", "language": "en-GB", "gender": "FEMALE"},
            {"name": "en-GB-Standard-D", "language": "en-GB", "gender": "MALE"},
            {"name": "en-GB-Standard-F", "language": "en-GB", "gender": "FEMALE"},
        ]
        
        return {"voices": standard_voices}
    
    def stream_audio_response(self, text: str, voice_id: str = None) -> Response:
        """Create a streaming response for audio playback.
        
        Args:
            text: The text to convert to speech
            voice_id: Optional voice ID or name
            
        Returns:
            Flask Response object for streaming
        """
        audio_data, content_type = self.text_to_speech(text, voice_id)
        
        def generate():
            yield audio_data
            
        return Response(generate(), mimetype=content_type)
    
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
        audio_data, _ = self.text_to_speech(text, voice_id)
        
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