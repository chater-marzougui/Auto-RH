from flask import Blueprint, request, jsonify, render_template, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import Enterprise, Job, Interview, User, Application, db
from app.utils.decorators import enterprise_required
from datetime import datetime, timezone
import json
from werkzeug.security import generate_password_hash
from sqlalchemy import func

enterprise_bp = Blueprint('enterprise', __name__)
enterpriseNotFoundErrStr = "Enterprise not found"

@enterprise_bp.route('/profile', methods=['GET', 'PUT'])
@jwt_required()
@enterprise_required
def enterprise_profile():
    identity = get_jwt_identity()
    enterprise = Enterprise.query.get(identity['id'])
    
    if not enterprise:
        return jsonify({'error': enterpriseNotFoundErrStr}), 404
    
    if request.method == 'GET':
        return render_template('enterprise/profile.html', enterprise=enterprise)
    
    # PUT request to update profile
    data = request.get_json()
    
    # Update allowed fields
    if 'name' in data:
        enterprise.name = data['name']
    
    if 'industry' in data:
        enterprise.industry = data['industry']
    
    if 'description' in data:
        enterprise.description = data['description']
    
    if 'location' in data:
        enterprise.location = data['location']
    
    if 'website' in data:
        enterprise.website = data['website']
    
    if 'company_size' in data:
        enterprise.company_size = data['company_size']
    
    if 'founded_year' in data:
        enterprise.founded_year = data['founded_year']
    
    enterprise.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    
    return jsonify({'message': 'Profile updated successfully'}), 200

@enterprise_bp.route('/settings', methods=['GET', 'PUT'])
@jwt_required()
@enterprise_required
def enterprise_settings():
    identity = get_jwt_identity()
    enterprise = Enterprise.query.get(identity['id'])
    
    if not enterprise:
        return jsonify({'error': enterpriseNotFoundErrStr}), 404
    
    if request.method == 'GET':
        return render_template('enterprise/settings.html', enterprise=enterprise)
    
    # PUT request to update settings
    data = request.get_json()
    
    # Update notification preferences
    if 'notification_preferences' in data:
        enterprise.notification_preferences = data['notification_preferences']
    
    # Update interview settings
    if 'interview_settings' in data:
        enterprise.interview_settings = data['interview_settings']
    
    # Update custom AI behavior settings
    if 'ai_behavior_settings' in data:
        enterprise.ai_behavior_settings = data['ai_behavior_settings']
    
    enterprise.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    
    return jsonify({'message': 'Settings updated successfully'}), 200

@enterprise_bp.route('/team', methods=['GET'])
@jwt_required()
@enterprise_required
def list_team_members():
    identity = get_jwt_identity()
    enterprise = Enterprise.query.get(identity['id'])
    
    if not enterprise:
        return jsonify({'error': enterpriseNotFoundErrStr}), 404
    
    # Assuming we have a TeamMember model linked to Enterprise
    team_members = enterprise.team_members
    
    return render_template('enterprise/team.html', team_members=team_members)

@enterprise_bp.route('/team/add', methods=['POST'])
@jwt_required()
@enterprise_required
def add_team_member():
    identity = get_jwt_identity()
    enterprise = Enterprise.query.get(identity['id'])
    
    if not enterprise:
        return jsonify({'error': enterpriseNotFoundErrStr}), 404
    
    data = request.get_json()
    
    # Validate required fields
    if not all(field in data for field in ['email', 'name', 'role']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check if the team member already exists
    existing_member = TeamMember.query.filter_by(
        enterprise_id=enterprise.id,
        email=data['email']
    ).first()
    
    if existing_member:
        return jsonify({'error': 'Team member already exists'}), 409
    
    # Create a temporary password for the team member
    temp_password = generate_password_hash(str(datetime.now(timezone.utc)))
    
    # Create new team member
    new_member = TeamMember(
        enterprise_id=enterprise.id,
        email=data['email'],
        name=data['name'],
        role=data['role'],
        password=temp_password,  # Will be reset on first login
        created_at=datetime.now(timezone.utc)
    )
    
    db.session.add(new_member)
    db.session.commit()
    
    # TODO: Send invitation email to the team member
    
    return jsonify({'message': 'Team member added successfully'}), 201

@enterprise_bp.route('/team/<int:member_id>', methods=['PUT', 'DELETE'])
@jwt_required()
@enterprise_required
def manage_team_member(member_id):
    identity = get_jwt_identity()
    enterprise = Enterprise.query.get(identity['id'])
    
    if not enterprise:
        return jsonify({'error': enterpriseNotFoundErrStr}), 404
    
    # Find the team member
    team_member = TeamMember.query.filter_by(
        id=member_id,
        enterprise_id=enterprise.id
    ).first()
    
    if not team_member:
        return jsonify({'error': 'Team member not found'}), 404
    
    if request.method == 'PUT':
        data = request.get_json()
        
        # Update allowed fields
        if 'name' in data:
            team_member.name = data['name']
        
        if 'role' in data:
            team_member.role = data['role']
        
        if 'permissions' in data:
            team_member.permissions = data['permissions']
        
        team_member.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        return jsonify({'message': 'Team member updated successfully'}), 200
    
    # DELETE request
    db.session.delete(team_member)
    db.session.commit()
    
    return jsonify({'message': 'Team member removed successfully'}), 200

@enterprise_bp.route('/analytics', methods=['GET'])
@jwt_required()
@enterprise_required
def enterprise_analytics():
    identity = get_jwt_identity()
    enterprise = Enterprise.query.get(identity['id'])
    
    if not enterprise:
        return jsonify({'error': enterpriseNotFoundErrStr}), 404
    
    # Get analytics data
    # Jobs count
    jobs_count = Job.query.filter_by(enterprise_id=enterprise.id).count()
    
    # Applications count
    applications_count = db.session.query(func.count(Application.id)).\
        join(Job).filter(Job.enterprise_id == enterprise.id).scalar()
    
    # Interviews count
    interviews_count = db.session.query(func.count(Interview.id)).\
        join(Job).filter(Job.enterprise_id == enterprise.id).scalar()
    
    # Top performing candidates
    top_candidates = db.session.query(
        User.id, User.name, User.email, Interview.score
    ).join(
        Interview, User.id == Interview.user_id
    ).join(
        Job, Interview.job_id == Job.id
    ).filter(
        Job.enterprise_id == enterprise.id
    ).order_by(
        Interview.score.desc()
    ).limit(10).all()
    
    # Most applied to jobs
    most_applied_jobs = db.session.query(
        Job.id, Job.title, func.count(Application.id).label('application_count')
    ).join(
        Application, Job.id == Application.job_id
    ).filter(
        Job.enterprise_id == enterprise.id
    ).group_by(
        Job.id
    ).order_by(
        func.count(Application.id).desc()
    ).limit(5).all()
    
    analytics_data = {
        'jobs_count': jobs_count,
        'applications_count': applications_count,
        'interviews_count': interviews_count,
        'top_candidates': [
            {
                'id': candidate.id,
                'name': candidate.name,
                'email': candidate.email,
                'score': candidate.score
            } for candidate in top_candidates
        ],
        'most_applied_jobs': [
            {
                'id': job.id,
                'title': job.title,
                'application_count': job.application_count
            } for job in most_applied_jobs
        ]
    }
    
    return render_template('enterprise/analytics.html', analytics=analytics_data)

@enterprise_bp.route('/subscription', methods=['GET'])
@jwt_required()
@enterprise_required
def subscription_status():
    identity = get_jwt_identity()
    enterprise = Enterprise.query.get(identity['id'])
    
    if not enterprise:
        return jsonify({'error': enterpriseNotFoundErrStr}), 404
    
    # Get subscription details
    subscription = {
        'plan': enterprise.subscription_plan,
        'status': enterprise.subscription_status,
        'next_billing_date': enterprise.next_billing_date,
        'features': {
            'max_jobs': enterprise.max_jobs_allowed,
            'max_interviews': enterprise.max_interviews_allowed,
            'additional_features': enterprise.subscription_features
        }
    }
    
    return render_template('enterprise/subscription.html', subscription=subscription)

@enterprise_bp.route('/subscription/upgrade', methods=['POST'])
@jwt_required()
@enterprise_required
def upgrade_subscription():
    identity = get_jwt_identity()
    enterprise = Enterprise.query.get(identity['id'])
    
    if not enterprise:
        return jsonify({'error': enterpriseNotFoundErrStr}), 404
    
    data = request.get_json()
    
    if 'plan' not in data:
        return jsonify({'error': 'Plan selection is required'}), 400
    
    plan = data['plan']
    
    # Update subscription details based on the plan
    if plan == 'basic':
        enterprise.subscription_plan = 'basic'
        enterprise.max_jobs_allowed = 5
        enterprise.max_interviews_allowed = 20
        enterprise.subscription_features = json.dumps(['Basic analytics', 'Standard AI interviews'])
    elif plan == 'pro':
        enterprise.subscription_plan = 'pro'
        enterprise.max_jobs_allowed = 20
        enterprise.max_interviews_allowed = 100
        enterprise.subscription_features = json.dumps(['Advanced analytics', 'Custom AI behavior', 'Priority support'])
    elif plan == 'enterprise':
        enterprise.subscription_plan = 'enterprise'
        enterprise.max_jobs_allowed = 100
        enterprise.max_interviews_allowed = 500
        enterprise.subscription_features = json.dumps(['Full analytics suite', 'Custom AI behavior', '24/7 support', 'API access', 'White labeling'])
    else:
        return jsonify({'error': 'Invalid plan selection'}), 400
    
    enterprise.subscription_status = 'active'
    enterprise.next_billing_date = datetime.now(timezone.utc).replace(day=1).replace(month=datetime.now(timezone.utc).month + 1 if datetime.now(timezone.utc).month < 12 else 1)
    enterprise.updated_at = datetime.now(timezone.utc)
    
    db.session.commit()
    
    return jsonify({'message': 'Subscription upgraded successfully'}), 200

@enterprise_bp.route('/candidates', methods=['GET'])
@jwt_required()
@enterprise_required
def view_candidates():
    identity = get_jwt_identity()
    enterprise = Enterprise.query.get(identity['id'])
    
    if not enterprise:
        return jsonify({'error': enterpriseNotFoundErrStr}), 404
    
    # Get filters from query parameters
    job_id = request.args.get('job_id', type=int)
    min_score = request.args.get('min_score', type=float)
    skills = request.args.get('skills')
    
    # Base query for applications to jobs owned by this enterprise
    query = db.session.query(
        User, Application, Job, Interview
    ).join(
        Application, User.id == Application.user_id
    ).join(
        Job, Application.job_id == Job.id
    ).outerjoin(
        Interview, (Application.user_id == Interview.user_id) & (Application.job_id == Interview.job_id)
    ).filter(
        Job.enterprise_id == enterprise.id
    )
    
    # Apply filters
    if job_id:
        query = query.filter(Job.id == job_id)
    
    if min_score:
        query = query.filter(Interview.score >= min_score)
    
    if skills:
        skill_list = skills.split(',')
        # This assumes a skills JSON field in User or related Skills table
        for skill in skill_list:
            query = query.filter(User.skills.contains(skill.strip()))
    
    candidates = query.all()
    
    # Format candidates for display
    formatted_candidates = []
    for user, application, job, interview in candidates:
        candidate_data = {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'job_title': job.title,
            'application_date': application.created_at,
            'status': application.status,
            'interview_score': interview.score if interview else None,
            'interview_date': interview.created_at if interview else None
        }
        formatted_candidates.append(candidate_data)
    
    # Get all jobs for filter dropdown
    jobs = Job.query.filter_by(enterprise_id=enterprise.id).all()
    
    return render_template('enterprise/candidates.html', 
                           candidates=formatted_candidates, 
                           jobs=jobs)