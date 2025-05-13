from flask import Blueprint, render_template, request, jsonify, current_app, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import User, Interview, Application, CareerRoadmap, Enterprise, Job
from app.services.scoring_service import get_user_assessment_summary
from sqlalchemy import func
from datetime import datetime, timedelta

dashboard = Blueprint('dashboard', __name__)
db = current_app.extensions['db']

# User Dashboard Routes
@dashboard.route('/user/dashboard', methods=['GET'])
@jwt_required()
def user_dashboard():
    """Render the main user dashboard page"""
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    
    if user.role != 'user':
        abort(403, "Access denied: Enterprise accounts should use the enterprise dashboard")
    
    # Get recent interviews (last 5)
    interviews = Interview.query.filter_by(user_id=user_id).order_by(Interview.created_at.desc()).limit(5).all()
    
    # Get active job applications
    applications = Application.query.filter_by(user_id=user_id).order_by(Application.created_at.desc()).limit(5).all()
    
    # Get career roadmap if exists
    roadmap = CareerRoadmap.query.filter_by(user_id=user_id).first()
    
    return render_template('dashboard/user_dashboard.html', 
                           user=user,
                           interviews=interviews,
                           applications=applications,
                           roadmap=roadmap)

@dashboard.route('/user/assessments', methods=['GET'])
@jwt_required()
def user_assessments():
    """Get all user interview assessments"""
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    
    # Get all interviews with pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    interviews = Interview.query.filter_by(user_id=user_id).order_by(
        Interview.created_at.desc()).paginate(page=page, per_page=per_page)
    
    return render_template('dashboard/user_assessments.html', 
                           user=user,
                           interviews=interviews)

@dashboard.route('/user/assessment/<int:interview_id>', methods=['GET'])
@jwt_required()
def view_assessment(interview_id):
    """View detailed assessment for a specific interview"""
    user_id = get_jwt_identity()
    
    interview = Interview.query.filter_by(id=interview_id, user_id=user_id).first_or_404()
    
    # Get interview questions and answers
    questions = interview.questions.all()
    
    # Get assessment summary 
    summary = get_user_assessment_summary(interview_id)
    
    return render_template('dashboard/assessment_detail.html',
                           interview=interview,
                           questions=questions,
                           summary=summary)

@dashboard.route('/user/cv-score', methods=['GET'])
@jwt_required()
def user_cv_score():
    """Get user's CV score and improvement suggestions"""
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    
    # Logic for retrieving CV score would be implemented here
    # This could involve accessing a stored score or calculating it on demand
    
    # For now, we'll return a mock response
    cv_feedback = {
        'score': 75,  # Example score
        'strengths': [
            'Good technical skills section',
            'Clear project descriptions',
            'Relevant education background'
        ],
        'weaknesses': [
            'Missing quantifiable achievements',
            'Unclear career objective',
            'Formatting inconsistencies'
        ],
        'improvement_suggestions': [
            'Add metrics to your achievements (e.g., "Increased sales by 20%")',
            'Create a clear and concise professional summary',
            'Standardize the formatting throughout your CV'
        ]
    }
    
    return render_template('dashboard/cv_score.html', 
                           user=user,
                           cv_feedback=cv_feedback)

@dashboard.route('/user/stats', methods=['GET'])
@jwt_required()
def user_statistics():
    """Get user statistics and analytics"""
    user_id = get_jwt_identity()
    
    # Get overall interview performance
    interviews = Interview.query.filter_by(user_id=user_id).all()
    
    # Calculate average scores
    if interviews:
        avg_score = sum(interview.score for interview in interviews if interview.score) / len(interviews)
        best_score = max(interview.score for interview in interviews if interview.score)
    else:
        avg_score = 0
        best_score = 0
    
    # Get application success rate
    applications = Application.query.filter_by(user_id=user_id).all()
    successful_apps = sum(1 for app in applications if app.status == 'accepted')
    app_success_rate = (successful_apps / len(applications)) * 100 if applications else 0
    
    # Get monthly interview count (last 6 months)
    now = datetime.now()
    six_months_ago = now - timedelta(days=180)
    
    monthly_interviews = db.session.query(
        func.date_trunc('month', Interview.created_at).label('month'), 
        func.count(Interview.id).label('count')
    ).filter(
        Interview.user_id == user_id,
        Interview.created_at >= six_months_ago
    ).group_by('month').order_by('month').all()
    
    # Format data for charts 
    months = [item[0].strftime('%b %Y') for item in monthly_interviews]
    interview_counts = [item[1] for item in monthly_interviews]
    
    stats = {
        'avg_score': round(avg_score, 1),
        'best_score': best_score,
        'total_interviews': len(interviews),
        'total_applications': len(applications),
        'app_success_rate': round(app_success_rate, 1),
        'months': months,
        'interview_counts': interview_counts
    }
    
    return render_template('dashboard/user_statistics.html', stats=stats)

# Enterprise Dashboard Routes
@dashboard.route('/enterprise/dashboard', methods=['GET'])
@jwt_required()
def enterprise_dashboard():
    """Render the main enterprise dashboard page"""
    user_id = get_jwt_identity()
    enterprise = Enterprise.query.get_or_404(user_id)
    
    # Get active job postings
    active_jobs = Job.query.filter_by(enterprise_id=enterprise.id, status='active').all()
    
    # Get recent applications
    recent_applications = db.session.query(Application, Job).join(
        Job, Application.job_id == Job.id
    ).filter(
        Job.enterprise_id == enterprise.id
    ).order_by(
        Application.created_at.desc()
    ).limit(10).all()
    
    # Get upcoming interviews
    upcoming_interviews = db.session.query(Interview, User, Job).join(
        User, Interview.user_id == User.id
    ).join(
        Job, Interview.job_id == Job.id
    ).filter(
        Job.enterprise_id == enterprise.id,
        Interview.status == 'scheduled'
    ).order_by(
        Interview.scheduled_at.asc()
    ).limit(5).all()
    
    # Get interview statistics
    total_interviews = Interview.query.join(
        Job, Interview.job_id == Job.id
    ).filter(
        Job.enterprise_id == enterprise.id
    ).count()
    
    avg_score = db.session.query(func.avg(Interview.score)).join(
        Job, Interview.job_id == Job.id
    ).filter(
        Job.enterprise_id == enterprise.id
    ).scalar() or 0
    
    return render_template('dashboard/enterprise_dashboard.html',
                          enterprise=enterprise,
                          active_jobs=active_jobs,
                          recent_applications=recent_applications,
                          upcoming_interviews=upcoming_interviews,
                          total_interviews=total_interviews,
                          avg_score=round(avg_score, 1))

@dashboard.route('/enterprise/interviews', methods=['GET'])
@jwt_required()
def enterprise_interviews():
    """Get all interviews for enterprise job postings"""
    user_id = get_jwt_identity()
    enterprise = Enterprise.query.get_or_404(user_id)
    
    # Filter parameters
    job_id = request.args.get('job_id', type=int)
    status = request.args.get('status')
    sort_by = request.args.get('sort_by', 'date')  # 'date', 'score'
    sort_order = request.args.get('sort_order', 'desc')  # 'asc', 'desc'
    
    # Build query
    query = db.session.query(Interview, User, Job).join(
        User, Interview.user_id == User.id
    ).join(
        Job, Interview.job_id == Job.id
    ).filter(
        Job.enterprise_id == enterprise.id
    )
    
    # Apply filters
    if job_id:
        query = query.filter(Job.id == job_id)
    
    if status:
        query = query.filter(Interview.status == status)
    
    # Apply sorting
    if sort_by == 'score':
        if sort_order == 'asc':
            query = query.order_by(Interview.score.asc())
        else:
            query = query.order_by(Interview.score.desc())
    else:  # Default to date sorting
        if sort_order == 'asc':
            query = query.order_by(Interview.created_at.asc())
        else:
            query = query.order_by(Interview.created_at.desc())
    
    # Paginate results
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    pagination = query.paginate(page=page, per_page=per_page)
    
    # Get all jobs for filter dropdown
    jobs = Job.query.filter_by(enterprise_id=enterprise.id).all()
    
    return render_template('dashboard/enterprise_interviews.html',
                          enterprise=enterprise,
                          pagination=pagination,
                          jobs=jobs,
                          current_filters={
                              'job_id': job_id,
                              'status': status,
                              'sort_by': sort_by,
                              'sort_order': sort_order
                          })

@dashboard.route('/enterprise/statistics', methods=['GET'])
@jwt_required()
def enterprise_statistics():
    """Get enterprise statistics and analytics"""
    user_id = get_jwt_identity()
    enterprise = Enterprise.query.get_or_404(user_id)
    
    # Time range filter
    period = request.args.get('period', 'all')
    
    if period == 'month':
        start_date = datetime.now() - timedelta(days=30)
    elif period == 'quarter':
        start_date = datetime.now() - timedelta(days=90)
    elif period == 'year':
        start_date = datetime.now() - timedelta(days=365)
    else:
        start_date = None
    
    # Base queries with time filter if applicable
    job_query = Job.query.filter_by(enterprise_id=enterprise.id)
    if start_date:
        job_query = job_query.filter(Job.created_at >= start_date)
    
    application_query = db.session.query(Application).join(
        Job, Application.job_id == Job.id
    ).filter(
        Job.enterprise_id == enterprise.id
    )
    if start_date:
        application_query = application_query.filter(Application.created_at >= start_date)
    
    interview_query = db.session.query(Interview).join(
        Job, Interview.job_id == Job.id
    ).filter(
        Job.enterprise_id == enterprise.id
    )
    if start_date:
        interview_query = interview_query.filter(Interview.created_at >= start_date)
    
    # Calculate statistics
    total_jobs = job_query.count()
    total_applications = application_query.count()
    total_interviews = interview_query.count()
    
    # Applications per job
    applications_per_job = total_applications / total_jobs if total_jobs > 0 else 0
    
    # Interview conversion rate
    interview_conversion = (total_interviews / total_applications * 100) if total_applications > 0 else 0
    
    # Average score
    avg_score = db.session.query(func.avg(Interview.score)).select_from(
        Interview
    ).join(
        Job, Interview.job_id == Job.id
    ).filter(
        Job.enterprise_id == enterprise.id
    )
    if start_date:
        avg_score = avg_score.filter(Interview.created_at >= start_date)
    avg_score = avg_score.scalar() or 0
    
    # Top performing candidates (highest scores)
    top_candidates = db.session.query(
        User.id, User.name, Interview.score, Job.title
    ).join(
        Interview, User.id == Interview.user_id
    ).join(
        Job, Interview.job_id == Job.id
    ).filter(
        Job.enterprise_id == enterprise.id
    ).order_by(
        Interview.score.desc()
    ).limit(5).all()
    
    # Application trend over time (last 6 months)
    now = datetime.now()
    six_months_ago = now - timedelta(days=180)
    
    application_trend = db.session.query(
        func.date_trunc('month', Application.created_at).label('month'), 
        func.count(Application.id).label('count')
    ).join(
        Job, Application.job_id == Job.id
    ).filter(
        Job.enterprise_id == enterprise.id,
        Application.created_at >= six_months_ago
    ).group_by('month').order_by('month').all()
    
    # Format data for charts
    trend_months = [item[0].strftime('%b %Y') for item in application_trend]
    application_counts = [item[1] for item in application_trend]
    
    stats = {
        'total_jobs': total_jobs,
        'total_applications': total_applications,
        'total_interviews': total_interviews,
        'applications_per_job': round(applications_per_job, 1),
        'interview_conversion': round(interview_conversion, 1),
        'avg_score': round(avg_score, 1),
        'top_candidates': top_candidates,
        'trend_months': trend_months,
        'application_counts': application_counts
    }
    
    return render_template('dashboard/enterprise_statistics.html',
                           enterprise=enterprise,
                           stats=stats,
                           period=period)

@dashboard.route('/enterprise/top-candidates', methods=['GET'])
@jwt_required()
def top_candidates():
    """Get top candidates across all job postings"""
    user_id = get_jwt_identity()
    enterprise = Enterprise.query.get_or_404(user_id)
    
    # Filter by job if specified
    job_id = request.args.get('job_id', type=int)
    
    # Get top candidates query
    query = db.session.query(
        User, Interview, Job
    ).join(
        Interview, User.id == Interview.user_id
    ).join(
        Job, Interview.job_id == Job.id
    ).filter(
        Job.enterprise_id == enterprise.id,
        Interview.score.isnot(None)  # Ensure there is a score
    )
    
    if job_id:
        query = query.filter(Job.id == job_id)
    
    query = query.order_by(Interview.score.desc())
    
    # Paginate results
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    pagination = query.paginate(page=page, per_page=per_page)
    
    # Get all jobs for filter
    jobs = Job.query.filter_by(enterprise_id=enterprise.id).all()
    
    return render_template('dashboard/top_candidates.html',
                          enterprise=enterprise,
                          pagination=pagination,
                          jobs=jobs,
                          current_job_id=job_id)

# API endpoints for dashboard data
@dashboard.route('/api/user/interview-progress', methods=['GET'])
@jwt_required()
def api_user_interview_progress():
    """API endpoint to get user interview progress over time"""
    user_id = get_jwt_identity()
    
    # Get interviews from the last 6 months
    six_months_ago = datetime.now() - timedelta(days=180)
    
    interviews = Interview.query.filter(
        Interview.user_id == user_id,
        Interview.created_at >= six_months_ago
    ).order_by(Interview.created_at.asc()).all()
    
    # Format data for chart
    data = [{
        'date': interview.created_at.strftime('%Y-%m-%d'),
        'score': interview.score,
        'job_title': interview.job.title if interview.job else 'General Assessment'
    } for interview in interviews if interview.score is not None]
    
    return jsonify(data)

@dashboard.route('/api/enterprise/job-performance', methods=['GET'])
@jwt_required()
def api_job_performance():
    """API endpoint to get performance metrics by job"""
    user_id = get_jwt_identity()
    enterprise = Enterprise.query.get_or_404(user_id)
    
    # Get all jobs and their associated metrics
    jobs = Job.query.filter_by(enterprise_id=enterprise.id).all()
    
    results = []
    for job in jobs:
        # Count applications
        application_count = Application.query.filter_by(job_id=job.id).count()
        
        # Count interviews
        interview_count = Interview.query.filter_by(job_id=job.id).count()
        
        # Get average score
        avg_score = db.session.query(func.avg(Interview.score)).filter(
            Interview.job_id == job.id,
            Interview.score.isnot(None)
        ).scalar() or 0
        
        results.append({
            'job_id': job.id,
            'job_title': job.title,
            'applications': application_count,
            'interviews': interview_count,
            'avg_score': round(float(avg_score), 1),
            'conversion_rate': round((interview_count / application_count * 100), 1) if application_count > 0 else 0
        })
    
    return jsonify(results)