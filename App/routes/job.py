from flask import Blueprint, request, jsonify, render_template, current_app, g
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.models import db, User, Job, Application, Enterprise, Interview
from app.services.gemini_service import analyze_job_match
from app.services.scoring_service import calculate_job_match_score
from app.utils.recommender import recommend_jobs_for_user
from app.utils.file_parser import extract_skills_from_cv
import os
from datetime import datetime, timezone
from werkzeug.utils import secure_filename
import uuid

job_bp = Blueprint('job', __name__, url_prefix='/jobs')
appJsonStr = 'application/json'

@job_bp.route('/', methods=['GET'])
def list_jobs():
    """List all active job postings with optional filtering"""
    # Handle query parameters for filtering
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # Filter parameters
    location = request.args.get('location')
    role_type = request.args.get('role_type')
    keyword = request.args.get('keyword')
    experience_level = request.args.get('experience_level')
    enterprise_id = request.args.get('enterprise_id', type=int)
    
    # Start with base query
    query = Job.query.filter_by(active=True)
    
    # Apply filters if provided
    if location:
        query = query.filter(Job.location.ilike(f'%{location}%'))
    if role_type:
        query = query.filter_by(job_type=role_type)
    if keyword:
        query = query.filter(
            (Job.title.ilike(f'%{keyword}%')) | 
            (Job.description.ilike(f'%{keyword}%')) |
            (Job.skills_required.ilike(f'%{keyword}%'))
        )
    if experience_level:
        query = query.filter_by(experience_level=experience_level)
    if enterprise_id:
        query = query.filter_by(enterprise_id=enterprise_id)
    
    # Order by most recent
    query = query.order_by(Job.created_at.desc())
    
    # Paginate results
    jobs_pagination = query.paginate(page=page, per_page=per_page)
    jobs = jobs_pagination.items
    
    # For API requests
    if request.headers.get('Accept') == appJsonStr:
        return jsonify({
            'jobs': [job.to_dict() for job in jobs],
            'total': jobs_pagination.total,
            'pages': jobs_pagination.pages,
            'current_page': page
        })
    
    # For web requests
    return render_template(
        'jobs/list.html',
        jobs=jobs,
        pagination=jobs_pagination
    )

@job_bp.route('/<int:job_id>', methods=['GET'])
def view_job(job_id):
    """View a specific job posting"""
    job = Job.query.get_or_404(job_id)
    
    # Check if job is still active
    if not job.active:
        return render_template('jobs/closed.html', job=job), 404
    
    # Get the associated enterprise
    enterprise = Enterprise.query.get(job.enterprise_id)
    
    # Check if user is logged in and has a match score
    user_match_score = None
    already_applied = False
    user_id = None
    
    try:
        user_id = get_jwt_identity()
        if user_id:
            # Check if user already applied
            application = Application.query.filter_by(
                user_id=user_id,
                job_id=job_id
            ).first()
            already_applied = application is not None
            
            # Get match score if user has CV
            user = User.query.get(user_id)
            if user and user.cv_path:
                user_skills = extract_skills_from_cv(user.cv_path)
                user_match_score = calculate_job_match_score(user_skills, job.skills_required)
    except Exception:
        # Not logged in or token issues, continue as guest
        pass
    
    # For API requests
    if request.headers.get('Accept') == appJsonStr:
        response = job.to_dict()
        response['enterprise'] = enterprise.to_dict() if enterprise else None
        response['user_match_score'] = user_match_score
        response['already_applied'] = already_applied
        return jsonify(response)
    
    # For web requests
    return render_template(
        'jobs/view.html',
        job=job,
        enterprise=enterprise,
        user_match_score=user_match_score,
        already_applied=already_applied
    )

@job_bp.route('/create', methods=['GET', 'POST'])
@jwt_required()
def create_job():
    """Create a new job posting (enterprise only)"""
    # Verify user is an enterprise
    claims = get_jwt()
    if claims.get('role') != 'enterprise':
        return jsonify({'error': 'Only enterprises can create job postings'}), 403
    
    enterprise_id = get_jwt_identity()
    enterprise = Enterprise.query.get(enterprise_id)
    
    if not enterprise:
        return jsonify({'error': 'Enterprise account not found'}), 404
    
    if request.method == 'POST':
        data = request.form or request.get_json()
        
        # Create new job with provided data
        new_job = Job(
            title=data.get('title'),
            description=data.get('description'),
            location=data.get('location'),
            job_type=data.get('job_type'),
            experience_level=data.get('experience_level'),
            salary_range=data.get('salary_range'),
            skills_required=data.get('skills_required'),
            enterprise_id=enterprise_id,
            active=True,
            application_deadline=datetime.strptime(data.get('application_deadline'), '%Y-%m-%d') if data.get('application_deadline') else None,
            interview_process=data.get('interview_process'),
            contact_email=data.get('contact_email') or enterprise.email
        )
        
        db.session.add(new_job)
        db.session.commit()
        
        # For API requests
        if request.headers.get('Accept') == appJsonStr:
            return jsonify({
                'message': 'Job created successfully',
                'job_id': new_job.id,
                'job': new_job.to_dict()
            }), 201
        
        # For web requests
        return render_template(
            'jobs/created.html',
            job=new_job
        )
    
    # GET request - show job creation form
    return render_template('jobs/create.html')

@job_bp.route('/<int:job_id>/update', methods=['GET', 'PUT', 'POST'])
@jwt_required()
def update_job(job_id):
    """Update an existing job posting (enterprise only)"""
    # Verify user is an enterprise
    claims = get_jwt()
    if claims.get('role') != 'enterprise':
        return jsonify({'error': 'Only enterprises can update job postings'}), 403
    
    enterprise_id = get_jwt_identity()
    job = Job.query.get_or_404(job_id)
    
    # Verify job belongs to this enterprise
    if job.enterprise_id != enterprise_id:
        return jsonify({'error': 'You do not have permission to edit this job'}), 403
    
    if request.method == 'GET':
        return render_template('jobs/update.html', job=job)
    
    data = request.form or request.get_json()
    
    # Update job fields
    job.title = data['title'] if data['title'] else job.title
    job.description = data['description'] if data['description'] else job.description
    job.location = data['location'] if data['location'] else job.location
    job.job_type = data['job_type'] if data['job_type'] else job.job_type
    job.experience_level = data['experience_level'] if data['experience_level'] else job.experience_level
    job.salary_range = data['salary_range'] if data['salary_range'] else job.salary_range
    job.skills_required = data['skills_required'] if data['skills_required'] else job.skills_required
    job.active = data['active'] if data['active'] else job.active
    job.application_deadline = datetime.strptime(data['application_deadline'], '%Y-%m-%d') if data['application_deadline'] else job.application_deadline
    job.interview_process = data['interview_process'] if data['interview_process'] else job.interview_process
    job.contact_email = data['contact_email'] if data['contact_email'] else job.contact_email
    
    job.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    
    # For API requests
    if request.headers.get('Accept') == appJsonStr:
        return jsonify({
            'message': 'Job updated successfully',
            'job': job.to_dict()
        })
    
    # For web requests - POST
    if request.method == 'POST':
        return render_template('jobs/updated.html', job=job)

@job_bp.route('/<int:job_id>/delete', methods=['DELETE', 'POST'])
@jwt_required()
def delete_job(job_id):
    """Delete a job posting (enterprise only)"""
    # Verify user is an enterprise
    claims = get_jwt()
    if claims.get('role') != 'enterprise':
        return jsonify({'error': 'Only enterprises can delete job postings'}), 403
    
    enterprise_id = get_jwt_identity()
    job = Job.query.get_or_404(job_id)
    
    # Verify job belongs to this enterprise
    if job.enterprise_id != enterprise_id:
        return jsonify({'error': 'You do not have permission to delete this job'}), 403
    
    # Soft delete - mark as inactive instead of removing from database
    job.active = False
    job.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    
    # For API requests
    if request.headers.get('Accept') == appJsonStr or request.method == 'DELETE':
        return jsonify({'message': 'Job deleted successfully'})
    
    # For web requests
    return render_template('jobs/deleted.html')

@job_bp.route('/<int:job_id>/apply', methods=['GET', 'POST'])
@jwt_required()
def apply_job(job_id):
    """Apply for a job (user only)"""
    user_id = get_jwt_identity()
    claims = get_jwt()
    
    # Verify user is not an enterprise
    if claims.get('role') == 'enterprise':
        return jsonify({'error': 'Enterprises cannot apply for jobs'}), 403
    
    job = Job.query.get_or_404(job_id)
    user = User.query.get_or_404(user_id)
    
    # Check if job is still active
    if not job.active:
        return jsonify({'error': 'This job posting is no longer active'}), 400
    
    # Check if already applied
    existing_application = Application.query.filter_by(
        user_id=user_id,
        job_id=job_id
    ).first()
    
    if existing_application:
        return jsonify({'error': 'You have already applied for this job'}), 400
    
    if request.method == 'POST':
        data = request.form or {}
        files = request.files or {}
        
        # Process CV upload if provided
        cv_path = user.cv_path  # Default to user's existing CV
        if 'cv' in files and files['cv']:
            cv_file = files['cv']
            filename = secure_filename(f"{uuid.uuid4()}_{cv_file.filename}")
            cv_upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'cvs', filename)
            os.makedirs(os.path.dirname(cv_upload_path), exist_ok=True)
            cv_file.save(cv_upload_path)
            cv_path = cv_upload_path
        
        # Create application record
        application = Application(
            user_id=user_id,
            job_id=job_id,
            cv_path=cv_path,
            cover_letter=data.get('cover_letter', ''),
            status='pending',
            applied_at=datetime.now(timezone.utc)
        )
        
        db.session.add(application)
        db.session.commit()
        
        # For API requests
        if request.headers.get('Accept') == appJsonStr:
            return jsonify({
                'message': 'Application submitted successfully', 
                'application_id': application.id
            }), 201
        
        # For web requests
        return render_template(
            'jobs/applied.html',
            job=job,
            application=application
        )
    
    # GET request - show application form
    return render_template(
        'jobs/apply.html',
        job=job,
        user=user
    )

@job_bp.route('/recommended')
@jwt_required()
def recommended_jobs():
    """Get jobs recommended for the user based on their profile"""
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    
    # Get user skills from CV if available
    user_skills = []
    if user.cv_path and os.path.exists(user.cv_path):
        user_skills = extract_skills_from_cv(user.cv_path)
    
    # Get recommended jobs
    recommended = recommend_jobs_for_user(user_id, user_skills)
    
    # For API requests
    if request.headers.get('Accept') == appJsonStr:
        return jsonify({
            'recommended_jobs': [job.to_dict() for job in recommended]
        })
    
    # For web requests
    return render_template(
        'jobs/recommended.html',
        jobs=recommended,
        user=user
    )

@job_bp.route('/<int:job_id>/match-analysis', methods=['GET'])
@jwt_required()
def job_match_analysis(job_id):
    """Get detailed analysis of job match for the user"""
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    job = Job.query.get_or_404(job_id)
    
    # Check if user has CV
    if not user.cv_path:
        return jsonify({'error': 'Please upload your CV first to get a match analysis'}), 400
    
    # Extract skills from CV
    user_skills = extract_skills_from_cv(user.cv_path)
    
    # Use Gemini to analyze the match
    analysis = analyze_job_match(
        user_skills=user_skills,
        job_title=job.title,
        job_description=job.description,
        required_skills=job.skills_required
    )
    
    # Calculate match score
    match_score = calculate_job_match_score(user_skills, job.skills_required)
    
    response = {
        'match_score': match_score,
        'analysis': analysis,
        'matched_skills': analysis.get('matched_skills', []),
        'missing_skills': analysis.get('missing_skills', []),
        'recommendations': analysis.get('recommendations', [])
    }
    
    # For API requests
    if request.headers.get('Accept') == appJsonStr:
        return jsonify(response)
    
    # For web requests
    return render_template(
        'jobs/match_analysis.html',
        job=job,
        user=user,
        match_score=match_score,
        analysis=analysis
    )

@job_bp.route('/applications', methods=['GET'])
@jwt_required()
def user_applications():
    """View all job applications for a user"""
    user_id = get_jwt_identity()
    
    # Get all applications for this user
    applications = Application.query.filter_by(user_id=user_id).order_by(Application.applied_at.desc()).all()
    
    # Prepare data with job details
    application_data = []
    for app in applications:
        job = Job.query.get(app.job_id)
        enterprise = Enterprise.query.get(job.enterprise_id) if job else None
        
        application_data.append({
            'application': app,
            'job': job,
            'enterprise': enterprise
        })
    
    # For API requests
    if request.headers.get('Accept') == appJsonStr:
        return jsonify({
            'applications': [{
                'application': app['application'].to_dict(),
                'job': app['job'].to_dict() if app['job'] else None,
                'enterprise': app['enterprise'].to_dict() if app['enterprise'] else None
            } for app in application_data]
        })
    
    # For web requests
    return render_template(
        'jobs/applications.html',
        applications=application_data
    )

@job_bp.route('/manage-applications', methods=['GET'])
@jwt_required()
def manage_applications():
    """View applications for enterprise jobs (enterprise only)"""
    # Verify user is an enterprise
    claims = get_jwt()
    if claims.get('role') != 'enterprise':
        return jsonify({'error': 'Only enterprises can view job applications'}), 403
    
    enterprise_id = get_jwt_identity()
    
    # Get jobs posted by this enterprise
    jobs = Job.query.filter_by(enterprise_id=enterprise_id).all()
    job_ids = [job.id for job in jobs]
    
    # Get applications for these jobs
    applications = Application.query.filter(Application.job_id.in_(job_ids)).order_by(Application.applied_at.desc()).all()
    
    # Group applications by job
    grouped_applications = {}
    for app in applications:
        job = Job.query.get(app.job_id)
        user = User.query.get(app.user_id)
        
        if app.job_id not in grouped_applications:
            grouped_applications[app.job_id] = {
                'job': job,
                'applications': []
            }
        
        grouped_applications[app.job_id]['applications'].append({
            'application': app,
            'user': user
        })
    
    # For API requests
    if request.headers.get('Accept') == appJsonStr:
        return jsonify({
            'jobs_with_applications': [{
                'job': group['job'].to_dict(),
                'applications': [{
                    'application': app['application'].to_dict(),
                    'user': app['user'].to_dict()
                } for app in group['applications']]
            } for job_id, group in grouped_applications.items()]
        })
    
    # For web requests
    return render_template(
        'jobs/manage_applications.html',
        jobs_with_applications=grouped_applications
    )

@job_bp.route('/applications/<int:application_id>/update-status', methods=['PUT', 'POST'])
@jwt_required()
def update_application_status(application_id):
    """Update the status of a job application (enterprise only)"""
    # Verify user is an enterprise
    claims = get_jwt()
    if claims.get('role') != 'enterprise':
        return jsonify({'error': 'Only enterprises can update application status'}), 403
    
    enterprise_id = get_jwt_identity()
    application = Application.query.get_or_404(application_id)
    job = Job.query.get(application.job_id)
    
    # Verify job belongs to this enterprise
    if not job or job.enterprise_id != enterprise_id:
        return jsonify({'error': 'You do not have permission to update this application'}), 403
    
    data = request.form or request.get_json()
    new_status = data.get('status')
    
    if not new_status:
        return jsonify({'error': 'New status not provided'}), 400
    
    # Valid status values
    valid_statuses = ['pending', 'reviewed', 'shortlisted', 'interview', 'rejected', 'hired']
    if new_status not in valid_statuses:
        return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
    
    # Update application status
    application.status = new_status
    application.status_updated_at = datetime.now(timezone.utc)
    db.session.commit()
    
    # For API requests 
    if request.headers.get('Accept') == appJsonStr or request.method == 'PUT':
        return jsonify({
            'message': 'Application status updated successfully',
            'application': application.to_dict()
        })
    
    # For web requests
    return jsonify({'success': True, 'message': 'Status updated successfully'})