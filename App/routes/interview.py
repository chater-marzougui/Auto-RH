import base64
from flask import Blueprint, request, jsonify, render_template, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import Interview, User, Enterprise, Job, Application, InterviewQuestion, db
from app.services.gemini_service import GeminiService
from app.services.scoring_service import ScoringService
from app.services.tts_service import TTSService
from app.services.stt_service import STTService
from app.utils.decorators import enterprise_required, user_required
from datetime import datetime, timezone
import json
import uuid
from werkzeug.utils import secure_filename
import os

interview_bp = Blueprint('interview', __name__)
gemini_service = GeminiService()
scoring_service = ScoringService()
tts_service = TTSService()
stt_service = STTService()
errorHtmlPage = 'error.html'
userNotFoundErrStr = "User not found"
enterpriseNotFoundStr = "Enterprise not found"

# General interview routes
@interview_bp.route('/interviews', methods=['GET'])
@jwt_required()
def list_interviews():
    identity = get_jwt_identity()
    
    if identity['type'] == 'user':
        # Get user's interviews
        user = User.query.get(identity['id'])
        if not user:
            return jsonify({'error': userNotFoundErrStr}), 404
        
        interviews = Interview.query.filter_by(user_id=user.id).all()
        
        interview_list = [{
            'id': interview.id,
            'job_title': interview.job.title if interview.job else 'General Assessment',
            'date': interview.created_at,
            'score': interview.score,
            'status': interview.status
        } for interview in interviews]
        
        return render_template('user/interviews.html', interviews=interview_list)
    
    elif identity['type'] == 'enterprise':
        # Get enterprise's interviews
        enterprise = Enterprise.query.get(identity['id'])
        if not enterprise:
            return jsonify({'error': enterpriseNotFoundStr}), 404
        
        # Get jobs owned by the enterprise
        job_ids = [job.id for job in Job.query.filter_by(enterprise_id=enterprise.id).all()]
        
        # Get interviews associated with those jobs
        interviews = Interview.query.filter(Interview.job_id.in_(job_ids)).all()
        
        interview_list = [{
            'id': interview.id,
            'job_title': interview.job.title,
            'candidate_name': interview.user.name,
            'date': interview.created_at,
            'score': interview.score,
            'status': interview.status
        } for interview in interviews]
        
        return render_template('enterprise/interviews.html', interviews=interview_list)
    
    return jsonify({'error': 'Invalid user type'}), 400

@interview_bp.route('/interview/<int:interview_id>', methods=['GET'])
@jwt_required()
def get_interview_details(interview_id):
    identity = get_jwt_identity()
    interview = Interview.query.get(interview_id)
    
    if not interview:
        return jsonify({'error': 'Interview not found'}), 404
    
    # Check permissions
    if identity['type'] == 'user' and interview.user_id != identity['id']:
        return jsonify({'error': 'Not authorized to view this interview'}), 403
    
    if identity['type'] == 'enterprise':
        # Check if enterprise owns the job associated with the interview
        enterprise = Enterprise.query.get(identity['id'])
        job = Job.query.get(interview.job_id)
        
        if not job or job.enterprise_id != enterprise.id:
            return jsonify({'error': 'Not authorized to view this interview'}), 403
    
    # Get interview questions and answers
    questions = InterviewQuestion.query.filter_by(interview_id=interview.id).order_by(InterviewQuestion.created_at).all()
    
    # Format interview data
    interview_data = {
        'id': interview.id,
        'user': {
            'id': interview.user.id,
            'name': interview.user.name,
            'email': interview.user.email
        },
        'job': {
            'id': interview.job.id,
            'title': interview.job.title,
            'description': interview.job.description
        } if interview.job else None,
        'date': interview.created_at,
        'score': interview.score,
        'status': interview.status,
        'summary': interview.summary,
        'transcript': interview.transcript,
        'questions': [{
            'id': q.id,
            'question': q.question,
            'answer': q.answer,
            'score': q.score,
            'feedback': q.feedback
        } for q in questions]
    }
    
    # Return different templates based on user type
    if identity['type'] == 'user':
        return render_template('user/interview_details.html', interview=interview_data)
    else:
        return render_template('enterprise/interview_details.html', interview=interview_data)

# User general assessment interviews
@interview_bp.route('/assessment/start', methods=['POST'])
@jwt_required()
@user_required
def start_general_assessment():
    """Start a general AI assessment interview without a specific job"""
    identity = get_jwt_identity()
    user = User.query.get(identity['id'])
    
    if not user:
        return jsonify({'error': userNotFoundErrStr}), 404
    
    data = request.get_json()
    
    # Check if user has uploaded a CV
    if not user.cv_path:
        return jsonify({'error': 'Please upload your CV before starting an assessment'}), 400
    
    # Extract job interest and other parameters
    job_interest = data.get('job_interest', '')
    additional_info = data.get('additional_info', '')
    
    # Create a new interview record
    new_interview = Interview(
        user_id=user.id,
        job_id=None,  # General assessment, not tied to a specific job
        status='in_progress',
        created_at=datetime.now(timezone.utc),
        interview_type='general_assessment',
        additional_data=json.dumps({
            'job_interest': job_interest,
            'additional_info': additional_info
        })
    )
    
    db.session.add(new_interview)
    db.session.commit()
    
    # Generate initial question based on CV and job interest
    initial_question = gemini_service.generate_initial_question(
        cv_path=user.cv_path,
        job_interest=job_interest,
        additional_info=additional_info
    )
    
    # Store the first question
    question = InterviewQuestion(
        interview_id=new_interview.id,
        question=initial_question,
        created_at=datetime.now(timezone.utc)
    )
    
    db.session.add(question)
    db.session.commit()
    
    # Generate audio for the question (if needed)
    audio_url = None
    if current_app.config.get('ENABLE_TTS', False):
        audio_filename = f"question_{question.id}.mp3"
        audio_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'audio', audio_filename)
        tts_service.generate_audio(initial_question, audio_path)
        audio_url = f"/audio/{audio_filename}"
    
    return jsonify({
        'interview_id': new_interview.id,
        'question_id': question.id,
        'question': initial_question,
        'audio_url': audio_url
    }), 201

@interview_bp.route('/assessment/answer/<int:question_id>', methods=['POST'])
@jwt_required()
@user_required
def submit_answer(question_id):
    """Submit an answer to a question in an ongoing interview"""
    identity = get_jwt_identity()
    user = User.query.get(identity['id'])
    
    if not user:
        return jsonify({'error': userNotFoundErrStr}), 404
    
    # Get the question
    question = InterviewQuestion.query.get(question_id)
    
    if not question:
        return jsonify({'error': 'Question not found'}), 404
    
    # Check if the question belongs to the user's interview
    interview = Interview.query.get(question.interview_id)
    
    if not interview or interview.user_id != user.id:
        return jsonify({'error': 'Not authorized to answer this question'}), 403
    
    data = request.get_json()
    answer_text = data.get('answer', '')
    
    # If audio was sent, transcribe it
    if 'audio' in data:
        audio_data = data['audio']
        # Assuming audio is sent as base64
        audio_filename = f"answer_{question.id}.webm"
        audio_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'audio', audio_filename)
        
        # Save audio file
        with open(audio_path, 'wb') as f:
            f.write(base64.b64decode(audio_data))
        
        # Transcribe audio
        answer_text = stt_service.transcribe_audio(audio_path)
    
    # Update the question with the answer
    question.answer = answer_text
    question.answered_at = datetime.now(timezone.utc)
    
    # Score the answer
    score, feedback = scoring_service.score_answer(
        question=question.question,
        answer=answer_text,
        cv_path=user.cv_path,
        job_interest=json.loads(interview.additional_data).get('job_interest', '')
    )
    
    question.score = score
    question.feedback = feedback
    
    db.session.commit()
    
    # Check if we should continue the interview or finish it
    questions_count = InterviewQuestion.query.filter_by(interview_id=interview.id).count()
    
    if questions_count >= 10:  # Limit to 10 questions per interview
        # Generate next steps
        return finish_interview(interview.id)
    
    # Generate the next question
    next_question_text = gemini_service.generate_follow_up_question(
        cv_path=user.cv_path,
        job_interest=json.loads(interview.additional_data).get('job_interest', ''),
        previous_questions=[q.question for q in InterviewQuestion.query.filter_by(interview_id=interview.id).all()],
        previous_answers=[q.answer for q in InterviewQuestion.query.filter_by(interview_id=interview.id).all() if q.answer],
        current_question=question.question,
        current_answer=answer_text
    )
    
    # Store the next question
    next_question = InterviewQuestion(
        interview_id=interview.id,
        question=next_question_text,
        created_at=datetime.now(timezone.utc)
    )
    
    db.session.add(next_question)
    db.session.commit()
    
    # Generate audio for the question (if needed)
    audio_url = None
    if current_app.config.get('ENABLE_TTS', False):
        audio_filename = f"question_{next_question.id}.mp3"
        audio_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'audio', audio_filename)
        tts_service.generate_audio(next_question_text, audio_path)
        audio_url = f"/audio/{audio_filename}"
    
    return jsonify({
        'question_id': next_question.id,
        'question': next_question_text,
        'audio_url': audio_url,
        'previous_feedback': feedback,
        'previous_score': score
    }), 200

@interview_bp.route('/assessment/finish/<int:interview_id>', methods=['POST'])
@jwt_required()
@user_required
def finish_interview(interview_id):
    """Finish an interview and generate the final assessment"""
    identity = get_jwt_identity()
    user = User.query.get(identity['id'])
    
    if not user:
        return jsonify({'error': userNotFoundErrStr}), 404
    
    # Get the interview
    interview = Interview.query.get(interview_id)
    
    if not interview or interview.user_id != user.id:
        return jsonify({'error': 'Not authorized to finish this interview'}), 403
    
    # Check if there are any questions
    questions = InterviewQuestion.query.filter_by(interview_id=interview.id).all()
    
    if not questions:
        return jsonify({'error': 'No questions found for this interview'}), 400
    
    # Generate transcript
    transcript = "\n\n".join([
        f"Q: {q.question}\nA: {q.answer if q.answer else 'Not answered'}"
        for q in questions
    ])
    
    # Generate summary and overall score
    job_interest = json.loads(interview.additional_data).get('job_interest', '')
    
    summary, overall_score = gemini_service.generate_interview_summary(
        cv_path=user.cv_path,
        job_interest=job_interest,
        questions=[q.question for q in questions],
        answers=[q.answer if q.answer else '' for q in questions],
        scores=[q.score for q in questions if q.score]
    )
    
    # Update the interview record
    interview.status = 'completed'
    interview.ended_at = datetime.now(timezone.utc)
    interview.transcript = transcript
    interview.summary = summary
    interview.score = overall_score
    
    db.session.commit()
    
    return jsonify({
        'interview_id': interview.id,
        'status': 'completed',
        'summary': summary,
        'score': overall_score,
        'redirect_url': f"/dashboard/interview/{interview.id}"
    }), 200

# Enterprise job-specific interview routes
@interview_bp.route('/job/<int:job_id>/interview/setup', methods=['GET', 'POST'])
@jwt_required()
@enterprise_required
def setup_job_interview(job_id):
    """Setup interview configuration for a specific job"""
    identity = get_jwt_identity()
    enterprise = Enterprise.query.get(identity['id'])
    
    if not enterprise:
        return jsonify({'error': enterpriseNotFoundStr}), 404
    
    # Check if job exists and belongs to this enterprise
    job = Job.query.get(job_id)
    
    if not job or job.enterprise_id != enterprise.id:
        return jsonify({'error': 'Job not found or not authorized'}), 404
    
    if request.method == 'GET':
        # Get current interview settings for this job
        interview_settings = job.interview_settings if job.interview_settings else {}
        return render_template('enterprise/setup_interview.html', job=job, settings=interview_settings)
    
    # POST request to update interview settings
    data = request.get_json()
    
    # Update job interview settings
    interview_settings = {
        'must_ask_questions': data.get('must_ask_questions', []),
        'personality_traits': data.get('personality_traits', []),
        'technical_focus': data.get('technical_focus', []),
        'time_limit': data.get('time_limit', 30),  # Default 30 minutes
        'difficulty_level': data.get('difficulty_level', 'medium'),
        'ai_behavior': data.get('ai_behavior', 'professional'),
        'feedback_detail': data.get('feedback_detail', 'detailed')
    }
    
    job.interview_settings = interview_settings
    job.updated_at = datetime.now(timezone.utc)
    
    db.session.commit()
    
    return jsonify({'message': 'Interview settings updated successfully'}), 200

@interview_bp.route('/job/<int:job_id>/interview/invite', methods=['POST'])
@jwt_required()
@enterprise_required
def invite_candidate(job_id):
    """Send interview invitation to a candidate"""
    identity = get_jwt_identity()
    enterprise = Enterprise.query.get(identity['id'])
    
    if not enterprise:
        return jsonify({'error': enterpriseNotFoundStr}), 404
    
    # Check if job exists and belongs to this enterprise
    job = Job.query.get(job_id)
    
    if not job or job.enterprise_id != enterprise.id:
        return jsonify({'error': 'Job not found or not authorized'}), 404
    
    data = request.get_json()
    
    if 'candidate_email' not in data:
        return jsonify({'error': 'Candidate email is required'}), 400
    
    # Check if user exists
    candidate = User.query.filter_by(email=data['candidate_email']).first()
    
    if not candidate:
        # Create a new user with a temporary account
        candidate = User(
            email=data['candidate_email'],
            name=data.get('candidate_name', 'Candidate'),
            password_hash=str(uuid.uuid4()),  # Random password, will be reset on first login
            created_at=datetime.now(timezone.utc),
            is_active=False,
            is_temp_account=True
        )
        db.session.add(candidate)
        db.session.commit()
    
    # Check if candidate has already applied to this job
    application = Application.query.filter_by(
        user_id=candidate.id,
        job_id=job.id
    ).first()
    
    if not application:
        # Create an application record
        application = Application(
            user_id=candidate.id,
            job_id=job.id,
            status='invited',
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(application)
    else:
        application.status = 'invited'
        application.updated_at = datetime.now(timezone.utc)
    
    # Generate interview token
    interview_token = str(uuid.uuid4())
    
    # Schedule the interview
    scheduled_time = data.get('scheduled_time')
    expiry_time = data.get('expiry_time')
    
    application.interview_token = interview_token
    application.interview_scheduled_at = scheduled_time
    application.interview_token_expiry = expiry_time
    
    db.session.commit()
    
    # TODO: Send email invitation to the candidate
    invitation_url = f"{request.host_url}interview/job/{job.id}/token/{interview_token}"
    
    # For now, just return the URL
    return jsonify({
        'message': 'Interview invitation sent successfully',
        'invitation_url': invitation_url,
        'candidate_id': candidate.id,
        'application_id': application.id
    }), 200

@interview_bp.route('/job/<int:job_id>/token/<token>', methods=['GET'])
def join_job_interview(job_id, token):
    """Access job interview with a token"""
    # Verify the token
    application = Application.query.filter_by(
        job_id=job_id,
        interview_token=token
    ).first()
    
    if not application:
        return render_template(errorHtmlPage, message='Invalid interview token'), 404
    
    # Check if token is expired
    if application.interview_token_expiry and application.interview_token_expiry < datetime.now(timezone.utc):
        return render_template(errorHtmlPage, message='Interview token has expired'), 400
    
    # Check if user has already completed an interview for this job
    existing_interview = Interview.query.filter_by(
        user_id=application.user_id,
        job_id=job_id,
        status='completed'
    ).first()
    
    if existing_interview:
        return render_template(errorHtmlPage, message='You have already completed an interview for this job'), 400
    
    # Get job and user details
    job = Job.query.get(job_id)
    user = User.query.get(application.user_id)
    
    if not job or not user:
        return render_template(errorHtmlPage, message='Job or user not found'), 404
    
    # Prepare for interview
    return render_template('interview/job_interview.html', 
                          job=job, 
                          user=user, 
                          application=application,
                          token=token)

@interview_bp.route('/job/<int:job_id>/token/<token>/start', methods=['POST'])
def start_job_interview(job_id, token):
    """Start the actual job interview with a token"""
    # Verify the token
    application = Application.query.filter_by(
        job_id=job_id,
        interview_token=token
    ).first()
    
    if not application:
        return jsonify({'error': 'Invalid interview token'}), 404
    
    # Check if token is expired
    if application.interview_token_expiry and application.interview_token_expiry < datetime.now(timezone.utc):
        return jsonify({'error': 'Interview token has expired'}), 400
    
    # Get job and user details
    job = Job.query.get(job_id)
    user = User.query.get(application.user_id)
    
    if not job or not user:
        return jsonify({'error': 'Job or user not found'}), 404
    
    # Create a new interview record
    new_interview = Interview(
        user_id=user.id,
        job_id=job.id,
        status='in_progress',
        created_at=datetime.now(timezone.utc),
        interview_type='job_specific'
    )
    
    db.session.add(new_interview)
    db.session.commit()
    
    # Update application status
    application.status = 'interviewing'
    application.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    
    # Generate initial question based on job description and interview settings
    interview_settings = job.interview_settings if job.interview_settings else {}
    must_ask_questions = interview_settings.get('must_ask_questions', [])
    
    # If there are must-ask questions, use the first one
    if must_ask_questions:
        initial_question_text = must_ask_questions[0]
    else:
        # Generate a question using AI
        initial_question_text = gemini_service.generate_job_interview_question(
            job_description=job.description,
            job_requirements=job.requirements,
            interview_settings=interview_settings,
            is_first_question=True
        )
    
    # Store the first question
    question = InterviewQuestion(
        interview_id=new_interview.id,
        question=initial_question_text,
        created_at=datetime.now(timezone.utc),
        is_must_ask=len(must_ask_questions) > 0
    )
    
    db.session.add(question)
    db.session.commit()
    
    # Generate audio for the question (if needed)
    audio_url = None
    if current_app.config.get('ENABLE_TTS', False):
        audio_filename = f"question_{question.id}.mp3"
        audio_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'audio', audio_filename)
        tts_service.generate_audio(initial_question_text, audio_path)
        audio_url = f"/audio/{audio_filename}"
    
    return jsonify({
        'interview_id': new_interview.id,
        'question_id': question.id,
        'question': initial_question_text,
        'audio_url': audio_url,
        'remaining_time': interview_settings.get('time_limit', 30) * 60  # Convert minutes to seconds
    }), 201

# Endpoint similar to general assessment answer but specifically for job interviews
@interview_bp.route('/job/interview/answer/<int:question_id>', methods=['POST'])
def submit_job_interview_answer(question_id):
    """Submit an answer to a question in a job interview"""
    # Get the question
    question = InterviewQuestion.query.get(question_id)
    
    if not question:
        return jsonify({'error': 'Question not found'}), 404
    
    # Get the interview
    interview = Interview.query.get(question.interview_id)
    
    if not interview or interview.interview_type != 'job_specific':
        return jsonify({'error': 'Invalid interview type'}), 400
    
    # Get the job
    job = Job.query.get(interview.job_id)
    
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    data = request.get_json()
    answer_text = data.get('answer', '')
    
    # If audio was sent, transcribe it
    if 'audio' in data:
        audio_data = data['audio']
        # Assuming audio is sent as base64
        audio_filename = f"answer_{question.id}.webm"
        audio_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'audio', audio_filename)
        
        # Save audio file
        with open(audio_path, 'wb') as f:
            f.write(base64.b64decode(audio_data))
        
        # Transcribe audio
        answer_text = stt_service.transcribe_audio(audio_path)
    
    # Update the question with the answer
    question.answer = answer_text
    question.answered_at = datetime.now(timezone.utc)
    
    # Score the answer
    interview_settings = job.interview_settings if job.interview_settings else {}
    score, feedback = scoring_service.score_job_interview_answer(
        question=question.question,
        answer=answer_text,
        job_description=job.description,
        job_requirements=job.requirements,
        interview_settings=interview_settings
    )
    
    question.score = score
    question.feedback = feedback
    
    db.session.commit()
    
    # Check if we should continue the interview or finish it
    questions_count = InterviewQuestion.query.filter_by(interview_id=interview.id).count()
    must_ask_questions = interview_settings.get('must_ask_questions', [])
    answered_must_ask = InterviewQuestion.query.filter_by(
        interview_id=interview.id,
        is_must_ask=True,
        answer=None  # Not null
    ).count()
    
    # Check if we've reached the maximum number of questions or all must-ask questions are answered
    if questions_count >= 15 or (len(must_ask_questions) > 0 and answered_must_ask == len(must_ask_questions)):
        # Finish the interview
        return finish_job_interview(interview.id)
    
    # Generate the next question
    
    # If there are remaining must-ask questions, use the next one
    remaining_must_ask = [q for q in must_ask_questions if q not in [
        question.question for question in InterviewQuestion.query.filter_by(
            interview_id=interview.id, 
            is_must_ask=True
        ).all()
    ]]
    
    if remaining_must_ask:
        next_question_text = remaining_must_ask[0]
        is_must_ask = True
    else:
        # Generate a follow-up question using AI
        previous_questions = [q.question for q in InterviewQuestion.query.filter_by(interview_id=interview.id).all()]
        previous_answers = [q.answer for q in InterviewQuestion.query.filter_by(interview_id=interview.id).all() if q.answer]
        
        next_question_text = gemini_service.generate_job_interview_follow_up(
            job_description=job.description,
            job_requirements=job.requirements,
            interview_settings=interview_settings,
            previous_questions=previous_questions,
            previous_answers=previous_answers,
            current_question=question.question,
            current_answer=answer_text
        )
        is_must_ask = False
    
    # Store the next question
    next_question = InterviewQuestion(
        interview_id=interview.id,
        question=next_question_text,
        created_at=datetime.now(timezone.utc),
        is_must_ask=is_must_ask
    )
    
    db.session.add(next_question)
    db.session.commit()
    
    # Generate audio for the question (if needed)
    audio_url = None
    if current_app.config.get('ENABLE_TTS', False):
        audio_filename = f"question_{next_question.id}.mp3"
        audio_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'audio', audio_filename)
        tts_service.generate_audio(next_question_text, audio_path)
        audio_url = f"/audio/{audio_filename}"
    
    return jsonify({
        'question_id': next_question.id,
        'question': next_question_text,
        'audio_url': audio_url,
        'previous_feedback': feedback,
        'previous_score': score
    }), 200

@interview_bp.route('/job/interview/finish/<int:interview_id>', methods=['POST'])
def finish_job_interview(interview_id):
    """Finish a job interview and generate the final assessment"""
    # Get the interview
    interview = Interview.query.get(interview_id)
    
    if not interview or interview.interview_type != 'job_specific':
        return jsonify({'error': 'Invalid interview'}), 404
    
    # Get the job
    job = Job.query.get(interview.job_id)
    
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    # Get all questions and answers
    questions = InterviewQuestion.query.filter_by(interview_id=interview.id).all()
    
    if not questions:
        return jsonify({'error': 'No questions found for this interview'}), 400
    
    # Generate transcript
    transcript = "\n\n".join([
        f"Q: {q.question}\nA: {q.answer if q.answer else 'Not answered'}"
        for q in questions
    ])
    
    # Generate summary and overall score
    interview_settings = job.interview_settings if job.interview_settings else {}
    
    summary, overall_score = gemini_service.evaluate_job_interview(
        job_description=job.description,
        job_requirements=job.requirements,
        interview_settings=interview_settings,
        questions=[q.question for q in questions],
        answers=[q.answer if q.answer else '' for q in questions],
        scores=[q.score for q in questions if q.score]
    )
    
    # Update the interview record
    interview.status = 'completed'
    interview.ended_at = datetime.now(timezone.utc)
    interview.transcript = transcript
    interview.summary = summary
    interview.score = overall_score
    
    # Update application status
    application = Application.query.filter_by(
        user_id=interview.user_id,
        job_id=interview.job_id
    ).first()
    
    if application:
        application.status = 'interviewed'
        application.updated_at = datetime.now(timezone.utc)
    
    db.session.commit()
    
    return jsonify({
        'interview_id': interview.id,
        'status': 'completed',
        'summary': summary,
        'score': overall_score,
        'redirect_url': f"/job/{job.id}/application/thank-you"
    }), 200