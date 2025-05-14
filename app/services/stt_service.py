"""
Speech-to-Text Service for Automated HR
Handles transcription of audio to text during interviews
Using SpeechRecognition library instead of external APIs
"""
import logging
import os
import tempfile
from typing import Optional, Dict, BinaryIO
import speech_recognition as sr
from pathlib import Path
import uuid
import base64
import wave
import io

logger = logging.getLogger(__name__)

class STTService:
    """
    Service for Speech-to-Text conversions using SpeechRecognition library
    """
    def __init__(self, engine: str = "google"):
        """
        Initialize the STT service with a specified recognition engine
        
        Args:
            engine: Recognition engine ('google', 'sphinx')
        """
        self.engine = engine
        self.recognizer = sr.Recognizer()
        self.temp_dir = Path(tempfile.gettempdir()) / "automated_hr_audio"
        self.temp_dir.mkdir(exist_ok=True)
        
    def transcribe_audio_file(self, audio_file: BinaryIO, language: str = "en-US") -> Dict:
        """
        Transcribe an audio file to text
        
        Args:
            audio_file: File-like object containing audio data
            language: Language code (default: "en-US")
            
        Returns:
            Dict containing the transcription and metadata
        """
        try:
            # Save the file temporarily
            temp_file = self.temp_dir / f"temp_{os.urandom(8).hex()}.wav"
            with open(temp_file, "wb") as f:
                f.write(audio_file.read())
            
            # Load audio file with SpeechRecognition
            with sr.AudioFile(str(temp_file)) as source:
                audio_data = self.recognizer.record(source)
            
            # Perform transcription using the selected engine
            text = self._recognize_audio(audio_data, language)
            
            # Clean up
            temp_file.unlink(missing_ok=True)
            
            return {
                "text": text,
                "language": language
            }
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            return {"error": str(e), "text": ""}
    
    def transcribe_audio_data(self, audio_data: bytes, language: str = "en-US") -> Dict:
        """
        Transcribe audio data bytes to text
        
        Args:
            audio_data: Raw audio data bytes
            language: Language code (default: "en-US")
            
        Returns:
            Dict containing the transcription and metadata
        """
        try:
            # Save the bytes to a temporary file
            temp_file = self.temp_dir / f"temp_{os.urandom(8).hex()}.wav"
            with open(temp_file, "wb") as f:
                f.write(audio_data)
            
            # Load audio file with SpeechRecognition
            with sr.AudioFile(str(temp_file)) as source:
                audio = self.recognizer.record(source)
            
            # Perform transcription
            text = self._recognize_audio(audio, language)
            
            # Clean up
            temp_file.unlink(missing_ok=True)
            
            return {
                "text": text,
                "language": language
            }
            
        except Exception as e:
            logger.error(f"Error transcribing audio data: {str(e)}")
            return {"error": str(e), "text": ""}
    
    def transcribe_audio_base64(self, audio_base64: str, language: str = "en-US") -> Dict:
        """
        Transcribe base64-encoded audio to text
        
        Args:
            audio_base64: Base64-encoded audio data
            language: Language code (default: "en-US")
            
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
            
    def transcribe_audio_chunk(self, audio_data: bytes, language: str = "en-US") -> str:
        """
        Transcribe a small chunk of audio (for real-time transcription)
        
        Args:
            audio_data: Raw audio data bytes
            language: Language code (default: "en-US")
            
        Returns:
            Transcribed text
        """
        try:
            result = self.transcribe_audio_data(audio_data, language)
            return result.get("text", "")
        except Exception as e:
            logger.error(f"Error transcribing audio chunk: {str(e)}")
            return ""
    
    def _recognize_audio(self, audio_data: sr.AudioData, language: str = "en-US") -> str:
        """
        Recognize speech in audio data using the selected engine
        
        Args:
            audio_data: AudioData object from SpeechRecognition
            language: Language code
            
        Returns:
            Transcribed text
        """
        try:
            if self.engine == "google":
                # Use Google's free web recognition (no API key needed)
                return self.recognizer.recognize_google(audio_data, language=language)
            elif self.engine == "sphinx":
                # Use CMU Sphinx (works offline)
                return self.recognizer.recognize_sphinx(audio_data, language=language)
        except sr.UnknownValueError:
            logger.warning("Speech could not be understood")
            return ""
        except sr.RequestError as e:
            logger.error(f"Recognition request failed: {e}")
            return ""
        except Exception as e:
            logger.error(f"Recognition error: {e}")
            return ""

    def continuous_transcription_start(self) -> str:
        """
        Start a continuous transcription session
        
        Returns:
            Session ID for the transcription
        """
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
            # Concatenate all audio chunks
            all_chunks = sorted(session_dir.glob("chunk_*.wav"))
            if not all_chunks:
                return {"text": ""}
            
            # For proper concatenation, we would need to merge WAV files correctly
            # This is a simplified approach for demonstration
            if len(all_chunks) == 1:
                # Only one chunk, no need to merge
                with sr.AudioFile(str(all_chunks[0])) as source:
                    audio_data = self.recognizer.record(source)
                text = self._recognize_audio(audio_data)
            else:
                # Process each chunk separately and combine the results
                # More sophisticated audio merging would be needed for production use
                combined_text = ""
                for chunk_file in all_chunks:
                    with sr.AudioFile(str(chunk_file)) as source:
                        audio_data = self.recognizer.record(source)
                    chunk_text = self._recognize_audio(audio_data)
                    if chunk_text:
                        combined_text += chunk_text + " "
                text = combined_text.strip()
            
            # Clean up
            import shutil
            shutil.rmtree(session_dir)
            
            return {
                "text": text,
                "language": "en-US"  # Default language
            }
            
        except Exception as e:
            logger.error(f"Error ending transcription session: {str(e)}")
            return {"error": str(e), "text": ""}
            
    def merge_wav_files(self, input_files, output_file):
        """
        Merge multiple WAV files into one
        
        Args:
            input_files: List of WAV file paths
            output_file: Output WAV file path
        """
        data = []
        sample_rate = None
        sample_width = None
        
        # Read all input files
        for file_path in input_files:
            with wave.open(str(file_path), 'rb') as wf:
                if sample_rate is None:
                    sample_rate = wf.getframerate()
                    sample_width = wf.getsampwidth()
                    channels = wf.getnchannels()
                elif sample_rate != wf.getframerate() or sample_width != wf.getsampwidth():
                    logger.warning(f"WAV file {file_path} has different format, skipping")
                    continue
                
                data.append(wf.readframes(wf.getnframes()))
        
        # Write merged file
        with wave.open(str(output_file), 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            for fragment in data:
                wf.writeframes(fragment)