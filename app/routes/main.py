from flask import Blueprint, render_template, redirect, url_for, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.models import User, Interview, Job, Enterprise, db

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Home page route"""
    # Get recent job postings for the homepage
    recent_jobs = Job.query.order_by(Job.created_at.desc()).limit(6).all()
    
    # Check if user is logged in
    logged_in = False
    user_role = None
    
    try:
        # Try to get JWT identity (will fail if not logged in)
        user_id = get_jwt_identity()
        if user_id:
            logged_in = True
            claims = get_jwt()
            user_role = claims.get('role', 'user')
    except Exception:
        # Not logged in, continue as guest
        pass
    
    return render_template(
        'main/index.html', 
        recent_jobs=recent_jobs,
        logged_in=logged_in,
        user_role=user_role
    )

@main_bp.route('/about')
def about():
    """About page route"""
    return render_template('main/about.html')

@main_bp.route('/how-it-works')
def how_it_works():
    """How it works page explaining platform features"""
    return render_template('main/how_it_works.html')

@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    """Contact form page"""
    if request.method == 'POST':
        # data = request.form """"
        # name = data.get('name')
        # email = data.get('email')
        # subject = data.get('subject')
        # message = data.get('message')
        
        # Here you would typically send the email or store in DB
        # For now, we'll just return a success message
        
        return render_template(
            'main/contact.html',
            success=True,
            message="Your message has been sent. We'll get back to you soon!"
        )
    
    return render_template('main/contact.html')

@main_bp.route('/pricing')
def pricing():
    """Pricing page for premium features"""
    return render_template('main/pricing.html')

@main_bp.route('/terms')
def terms():
    """Terms and conditions page"""
    return render_template('main/terms.html')

@main_bp.route('/privacy')
def privacy():
    """Privacy policy page"""
    return render_template('main/privacy.html')

@main_bp.route('/faq')
def faq():
    """Frequently asked questions page"""
    return render_template('main/faq.html')

@main_bp.route('/api/stats')
def api_stats():
    """Public API endpoint for platform statistics"""
    # Get basic platform stats
    stats = {
        'total_users': User.query.count(),
        'total_enterprises': Enterprise.query.count(),
        'total_jobs': Job.query.count(),
        'total_interviews': Interview.query.count()
    }
    
    return jsonify(stats)

@main_bp.route('/search')
def search():
    """Search functionality for the platform"""
    query = request.args.get('q', '')
    category = request.args.get('category', 'jobs')
    
    results = []
    
    if query:
        if category == 'jobs':
            # Search jobs
            job_results = Job.query.filter(
                (Job.title.ilike(f'%{query}%')) | 
                (Job.description.ilike(f'%{query}%'))
            ).limit(20).all()
            
            results = [{
                'id': job.id,
                'title': job.title,
                'company': job.enterprise.name if job.enterprise else 'Unknown',
                'location': job.location,
                'type': job.job_type,
                'url': url_for('job.view_job', job_id=job.id)
            } for job in job_results]
        
        elif category == 'enterprises':
            # Search enterprises
            enterprise_results = Enterprise.query.filter(
                Enterprise.name.ilike(f'%{query}%')
            ).limit(20).all()
            
            results = [{
                'id': ent.id,
                'name': ent.name,
                'industry': ent.industry,
                'url': url_for('enterprise.view_enterprise', enterprise_id=ent.id)
            } for ent in enterprise_results]
    
    # For AJAX requests, return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'results': results,
            'count': len(results)
        })
    
    # For normal requests, render template
    return render_template(
        'main/search.html',
        query=query,
        category=category,
        results=results
    )

@main_bp.route('/sitemap')
def sitemap():
    """Site map page"""
    return render_template('main/sitemap.html')

@main_bp.route('/dashboard-redirect')
@jwt_required()
def dashboard_redirect():
    """Redirect users to the appropriate dashboard based on role"""
    # user_id = get_jwt_identity() ""
    claims = get_jwt()
    role = claims.get('role', 'user')
    
    if role == 'enterprise':
        return redirect(url_for('enterprise.dashboard'))
    else:
        return redirect(url_for('dashboard.user_dashboard'))

@main_bp.errorhandler(404)
def page_not_found(e):
    """Custom 404 page"""
    return render_template('errors/404.html'), 404

@main_bp.errorhandler(500)
def server_error(e):
    """Custom 500 page"""
    return render_template('errors/500.html'), 500