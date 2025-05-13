"""
Interview Socket for Automated HR
Handles real-time WebSocket communications for interviews
"""
import logging
from flask import request, session
from flask_socketio import Namespace, emit, join_room, leave_room
from flask_jwt_extended import decode_token, verify_jwt_in_request
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.models import Interview, User, Job, InterviewQuestion
from app.services.gemini_service import GeminiService
from app.services.tts_service import TTSService
from app.services.stt_service import STTService
from app.services.scoring_service import ScoringService

logger = logging.getLogger(__name__)

class InterviewSocketNamespace(Namespace):
    """Socket.IO namespace for handling interview communications"""
    
    def __init__(self, namespace="/interview"):
        super().__init__(namespace)
        self.gemini_service = GeminiService()
        self.tts_service = TTSService()
        self.stt_service = STTService()
        self.scoring_service = ScoringService()
        
        # Active interview sessions
        self.active_sessions = {}
        # Structure: {
        #   'session_id': {
        #     'user_id': 123,
        #     'interview_id': 456,
        #     'job_id': 789,
        #     'start_time': timestamp,
        #     'questions_asked': [],
        #     'transcript': [],
        #     'current_question': {},
        #     'audio_enabled': True
        #   }
        # }
    
    def on_connect(self):
        """Handle client connection"""
        try:
            # Authenticate the user
            token = request.args.get('token')
            if not token:
                emit('error', {'message': 'No authentication token provided'})
                return
            
            # Decode token
            try:
                decoded_token = decode_token(token)
                user_id = decoded_token['sub']['id']
                role = decoded_token['sub'].get('role', 'user')
            except Exception as e:
                logger.error(f"Token validation error: {str(e)}")
                emit('error', {'message': 'Invalid token'})
                return

            # Store user info in session
            session['user_id'] = user_id
            session['role'] = role
            
            logger.info(f"User {user_id} connected to interview socket")
            emit('connect_success', {'message': 'Connected to interview socket'})
            
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            emit('error', {'message': 'Connection error'})
    
    def on_disconnect(self):
        """Handle client disconnection"""
        try:
            user_id = session.get('user_id')
            if user_id:
                # Find and clean up any active sessions for this user
                for session_id, session_data in list(self.active_sessions.items()):
                    if session_data.get('user_id') == user_id:
                        self._end_interview_session(session_id)
                        
                logger.info(f"User {user_id} disconnected from interview socket")
            
        except Exception as e:
            logger.error(f"Disconnect error: {str(e)}")
    
    def on_join_interview(self, data):
        """
        Join an interview room
        
        Expected data:
        {
            'interview_id': 123,  # Optional for new interviews
            'job_id': 456,        # Required for new interviews
            'audio_enabled': True  # Whether to use TTS/STT
        }
        """
        try:
            user_id = session.get('user_id')
            if not user_id:
                emit('error', {'message': 'Authentication required'})
                return
            
            # Check if this is an existing or new interview
            interview_id = data.get('interview_id')
            job_id = data.get('job_id')
            
            if interview_id:
                # Existing interview
                interview = Interview.query.get(interview_id)
                if not interview:
                    emit('error', {'message': 'Interview not found'})
                    return
                
                # Security check - ensure user has access
                if interview.user_id != user_id and session.get('role') != 'enterprise':
                    emit('error', {'message': 'Access denied'})
                    return
                
                job_id = interview.job_id
                
            else:
                # New interview - create it
                if not job_id and session.get('role') != 'enterprise':
                    emit('error', {'message': 'Job ID required for new interviews'})
                    return
                
                # Create new interview record
                from app import db
                interview = Interview(
                    user_id=user_id,
                    job_id=job_id,
                    status='scheduled',
                    scheduled_time=datetime.now(timezone.utc)
                )
                db.session.add(interview)
                db.session.commit()
                interview_id = interview.id
            
            # Generate a session ID
            import uuid
            session_id = str(uuid.uuid4())
            
            # Join the socket room
            room_name = f"interview_{interview_id}"
            join_room(room_name)
            
            # Initialize session data
            self.active_sessions[session_id] = {
                'user_id': user_id,
                'interview_id': interview_id,
                'job_id': job_id,
                'room': room_name,
                'start_time': time.time(),
                'questions_asked': [],
                'transcript': [],
                'current_question': None,
                'audio_enabled': data.get('audio_enabled', False)
            }
            
            # Send join confirmation
            emit('interview_joined', {
                'session_id': session_id,
                'interview_id': interview_id,
                'job_id': job_id
            })
            
            logger.info(f"User {user_id} joined interview {interview_id}, session {session_id}")
            
        except Exception as e:
            logger.error(f"Join interview error: {str(e)}")
            emit('error', {'message': f'Failed to join interview: {str(e)}'})
    
    def on_start_interview(self, data):
        """
        Start the interview flow
        
        Expected data:
        {
            'session_id': 'uuid_string',
            'cv_data': 'Optional CV text or ID'
        }
        """
        try:
            # Validate session
            session_id = data.get('session_id')
            if not session_id or session_id not in self.active_sessions:
                emit('error', {'message': 'Invalid session'})
                return
            
            session_data = self.active_sessions[session_id]
            interview_id = session_data['interview_id']
            job_id = session_data['job_id']
            
            # Update interview status
            from app import db
            interview = Interview.query.get(interview_id)
            if interview.status != 'in_progress':
                interview.status = 'in_progress'
                interview.start_time = datetime.now(timezone.utc)
                db.session.commit()
            
            # Get job details if available
            job = None
            job_description = "General interview assessment"
            if job_id:
                job = Job.query.get(job_id)
                if job:
                    job_description = job.description
            
            # Get user CV if provided
            cv_data = data.get('cv_data', '')
            
            # Generate introduction and first question
            introduction = self._generate_introduction(job_description, cv_data)
            first_question = self._generate_question(session_id, is_first=True)
            
            # Send introduction
            emit('interview_started', {
                'introduction': introduction,
                'first_question': first_question
            }, room=session_data['room'])
            
            # If audio enabled, generate speech
            if session_data['audio_enabled']:
                try:
                    intro_audio = self.tts_service.generate_speech(introduction)
                    question_audio = self.tts_service.generate_speech(first_question['text'])
                    
                    emit('speech_data', {
                        'type': 'introduction',
                        'audio_data': intro_audio
                    }, room=session_data['room'])
                    
                    emit('speech_data', {
                        'type': 'question',
                        'question_id': first_question['id'],
                        'audio_data': question_audio
                    }, room=session_data['room'])
                    
                except Exception as e:
                    logger.error(f"TTS error: {str(e)}")
                    
            logger.info(f"Interview {interview_id} started")
            
        except Exception as e:
            logger.error(f"Start interview error: {str(e)}")
            emit('error', {'message': f'Failed to start interview: {str(e)}'})

    def on_submit_answer(self, data):
        """
        Handle submitted answers
        
        Expected data:
        {
            'session_id': 'uuid_string',
            'question_id': 123,
            'answer_text': 'User's answer',
            'audio_data': 'Optional base64 audio data' 
        }
        """
        try:
            # Validate session
            session_id = data.get('session_id')
            if not session_id or session_id not in self.active_sessions:
                emit('error', {'message': 'Invalid session'})
                return
            
            session_data = self.active_sessions[session_id]
            interview_id = session_data['interview_id']
            
            # Get answer data
            question_id = data.get('question_id')
            answer_text = data.get('answer_text', '')
            audio_data = data.get('audio_data')
            
            # Process audio if provided but no text
            if audio_data and not answer_text:
                try:
                    transcription = self.stt_service.transcribe_audio_base64(audio_data)
                    answer_text = transcription.get('text', '')
                except Exception as e:
                    logger.error(f"STT error: {str(e)}")
            
            # Save the answer
            if question_id:
                self._save_answer(interview_id, question_id, answer_text)
            
            # Add to transcript
            if session_data.get('current_question'):
                q_text = session_data['current_question'].get('text', '')
                session_data['transcript'].append({
                    'speaker': 'interviewer',
                    'text': q_text
                })
                
            session_data['transcript'].append({
                'speaker': 'candidate',
                'text': answer_text
            })
            
            # Generate next question
            next_question = self._generate_question(session_id, previous_answer=answer_text)
            
            # Check if interview should end
            if next_question.get('is_final', False):
                self._process_interview_end(session_id)
                return
            
            # Send next question
            emit('next_question', next_question, room=session_data['room'])
            
            # If audio enabled, generate speech
            if session_data['audio_enabled']:
                try:
                    question_audio = self.tts_service.generate_speech(next_question['text'])
                    
                    emit('speech_data', {
                        'type': 'question',
                        'question_id': next_question['id'],
                        'audio_data': question_audio
                    }, room=session_data['room'])
                    
                except Exception as e:
                    logger.error(f"TTS error: {str(e)}")
            
        except Exception as e:
            logger.error(f"Submit answer error: {str(e)}")
            emit('error', {'message': f'Failed to process answer: {str(e)}'})
    
    def on_end_interview(self, data):
        """
        End the interview session
        
        Expected data:
        {
            'session_id': 'uuid_string'
        }
        """
        try:
            session_id = data.get('session_id')
            if session_id and session_id in self.active_sessions:
                self._process_interview_end(session_id)
                
        except Exception as e:
            logger.error(f"End interview error: {str(e)}")
            emit('error', {'message': f'Failed to end interview: {str(e)}'})
    
    def _generate_introduction(self, job_description: str, cv_data: str = "") -> str:
        """Generate interview introduction based on job and CV"""
        try:
            prompt = f"""
            You are an AI interviewer. Generate a professional, friendly introduction for a job interview.
            
            JOB DESCRIPTION: {job_description}
            
            CV DATA: {cv_data}
            
            Create a brief, welcoming introduction that:
            1. Greets the candidate
            2. Explains this is an AI-conducted interview
            3. Sets expectations for the interview process
            4. Mentions that responses will be evaluated
            
            Keep it under 150 words, warm and professional.
            """
            
            introduction = self.gemini_service.generate_response(prompt)
            return introduction.strip()
            
        except Exception as e:
            logger.error(f"Introduction generation error: {str(e)}")
            return "Welcome to your interview. I'll be asking you several questions to assess your skills and experience. Let's get started."
    
    def _generate_question(self, session_id: str, is_first: bool = False, previous_answer: str = "") -> Dict:
        """Generate the next interview question"""
        try:
            session_data = self.active_sessions[session_id]
            interview_id = session_data['interview_id']
            job_id = session_data['job_id']
            
            # Get job details if available
            job = None
            job_description = "General interview assessment"
            job_title = "General Position"
            if job_id:
                job = Job.query.get(job_id)
                if job:
                    job_description = job.description
                    job_title = job.title
            
            # Get transcript so far
            transcript = ""
            for exchange in session_data.get('transcript', []):
                speaker = exchange.get('speaker', '')
                text = exchange.get('text', '')
                transcript += f"{speaker.capitalize()}: {text}\n"
            
            # Get previously asked questions
            questions_asked = session_data.get('questions_asked', [])
            questions_text = "\n".join([q.get('text', '') for q in questions_asked])
            
            # Check if we should end the interview (based on number of questions)
            if len(questions_asked) >= 10:  # Max 10 questions per interview
                return {
                    'id': None,
                    'text': "Thank you for your responses. That concludes our interview questions.",
                    'is_final': True
                }
            
            # Determine question type
            question_type = "general"
            if is_first:
                question_type = "introduction"
            elif len(questions_asked) == 9:  # Last question
                question_type = "conclusion"
            
            # Generate question
            prompt = f"""
            You are an AI interviewer for a {job_title} position. Generate the next interview question.
            
            JOB DESCRIPTION: {job_description}
            
            PREVIOUS QUESTIONS ASKED:
            {questions_text}
            
            INTERVIEW TRANSCRIPT SO FAR:
            {transcript}
            
            LAST ANSWER FROM CANDIDATE:
            {previous_answer}
            
            QUESTION TYPE: {question_type}
            
            Create a single, clear interview question that:
            1. Follows naturally from the conversation
            2. Is relevant to the job position
            3. Has not already been asked
            4. Is open-ended (not yes/no)
            5. Tests skills and experiences relevant to the job
            
            Return ONLY the question text without any explanations or additional text.
            """
            
            question_text = self.gemini_service.generate_response(prompt)
            question_text = question_text.strip()
            
            # Create question record
            from app import db
            question = InterviewQuestion(
                interview_id=interview_id,
                question=question_text
            )
            db.session.add(question)
            db.session.commit()
            
            # Add to questions asked
            question_data = {
                'id': question.id,
                'text': question_text,
                'timestamp': time.time()
            }
            session_data['questions_asked'].append(question_data)
            session_data['current_question'] = question_data
            
            return {
                'id': question.id,
                'text': question_text,
                'is_final': False
            }
            
        except Exception as e:
            logger.error(f"Question generation error: {str(e)}")
            return {
                'id': None,
                'text': "Could you tell me about your relevant experience for this position?",
                'is_final': False
            }
    
    def _save_answer(self, interview_id: int, question_id: int, answer_text: str) -> None:
        """Save an answer to the database"""
        try:
            from app import db
            question = InterviewQuestion.query.get(question_id)
            if question:
                question.answer = answer_text
                db.session.commit()
                
        except Exception as e:
            logger.error(f"Save answer error: {str(e)}")
    
    def _process_interview_end(self, session_id: str) -> None:
        """Process the end of an interview"""
        try:
            session_data = self.active_sessions[session_id]
            interview_id = session_data['interview_id']
            room = session_data['room']
            
            # Generate full transcript
            full_transcript = ""
            for exchange in session_data.get('transcript', []):
                speaker = exchange.get('speaker', '')
                text = exchange.get('text', '')
                full_transcript += f"{speaker.capitalize()}: {text}\n\n"
            
            # Update interview record
            from app import db
            interview = Interview.query.get(interview_id)
            if interview:
                interview.status = 'completed'
                interview.end_time = datetime.now(timezone.utc)
                interview.transcript = full_transcript
                db.session.commit()
            
            # Process scoring
            try:
                scoring_result = self.scoring_service.score_interview(interview_id)
                
                # Send results to client
                emit('interview_completed', {
                    'interview_id': interview_id,
                    'transcript': full_transcript,
                    'score': scoring_result.get('overall_score', 0),
                    'assessment': scoring_result.get('assessment_summary', ''),
                    'tips': scoring_result.get('improvement_tips', [])
                }, room=room)
                
            except Exception as e:
                logger.error(f"Scoring error: {str(e)}")
                emit('interview_completed', {
                    'interview_id': interview_id,
                    'transcript': full_transcript,
                    'message': 'Interview completed. Detailed assessment will be available soon.'
                }, room=room)
            
            # Clean up session
            self._end_interview_session(session_id)
            
        except Exception as e:
            logger.error(f"Process interview end error: {str(e)}")
    
    def _end_interview_session(self, session_id: str) -> None:
        """Clean up interview session"""
        try:
            if session_id in self.active_sessions:
                room = self.active_sessions[session_id].get('room')
                if room:
                    leave_room(room)
                del self.active_sessions[session_id]
                
        except Exception as e:
            logger.error(f"End session error: {str(e)}")