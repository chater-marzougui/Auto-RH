from flask import Blueprint, request, jsonify, render_template, current_app, g
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import User, CareerRoadmap, db
import app.services.gemini_service as gemini_service
from app.utils.file_parser import parse_cv
import os
from dotenv import load_dotenv

load_dotenv()

gemini_service = gemini_service.GeminiService(api_key=os.getenv('GEMINI_API_KEY'))

career_bp = Blueprint('career', __name__, url_prefix='/career')
userNotFoundErrStr = "User not found"

@career_bp.route('/roadmap', methods=['GET', 'POST'])
@jwt_required()
def career_roadmap():
    """Generate or retrieve a career roadmap for the user"""
    user_id = get_jwt_identity()
    
    if request.method == 'POST':
        # Create a new roadmap
        data = request.form or request.get_json()
        
        # Get user's CV skills (from latest uploaded CV)
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': userNotFoundErrStr}), 404
            
        # Extract skills from CV if user has uploaded one
        cv_data = None
        if user.cv_path and os.path.exists(user.cv_path):
            cv_data = parse_cv(user.cv_path)
        
        # Get additional inputs for roadmap generation
        current_role = data.get('current_role', '')
        target_role = data.get('target_role', '')
        personality_traits = data.get('personality_traits', [])
        
        # Use Gemini to generate career roadmap
        roadmap_data = gemini_service.generate_career_roadmap(
            cv_data=cv_data,
            career_interests=[target_role],
            personality_traits=personality_traits,
        )
        
        # Store the roadmap in the database
        roadmap = CareerRoadmap(
            user_id=user_id,
            goals=roadmap_data.get('goals'),
            recommended_skills=roadmap_data.get('recommended_skills'),
            timeline=roadmap_data.get('timeline'),
            current_role=current_role,
            target_role=target_role
        )
        
        db.session.add(roadmap)
        db.session.commit()
        
        return jsonify({
            'message': 'Career roadmap created successfully',
            'roadmap_id': roadmap.id,
            'roadmap': roadmap_data
        }), 201
    
    else:  # GET request
        # Retrieve the most recent roadmap for the user
        roadmap = CareerRoadmap.query.filter_by(user_id=user_id).order_by(CareerRoadmap.created_at.desc()).first()
        
        if not roadmap:
            return jsonify({'message': 'No career roadmap found. Please create one.'}), 404
            
        return jsonify({
            'roadmap_id': roadmap.id,
            'goals': roadmap.goals,
            'recommended_skills': roadmap.recommended_skills,
            'timeline': roadmap.timeline,
            'current_role': roadmap.current_role,
            'target_role': roadmap.target_role,
            'created_at': roadmap.created_at
        })

@career_bp.route('/roadmap/<int:roadmap_id>', methods=['GET', 'PUT', 'DELETE'])
@jwt_required()
def manage_roadmap(roadmap_id):
    """Manage a specific career roadmap"""
    user_id = get_jwt_identity()
    roadmap = CareerRoadmap.query.filter_by(id=roadmap_id, user_id=user_id).first()
    
    if not roadmap:
        return jsonify({'error': 'Roadmap not found or access denied'}), 404
    
    if request.method == 'GET':
        return jsonify({
            'roadmap_id': roadmap.id,
            'goals': roadmap.goals,
            'recommended_skills': roadmap.recommended_skills,
            'timeline': roadmap.timeline,
            'current_role': roadmap.current_role,
            'target_role': roadmap.target_role,
            'created_at': roadmap.created_at
        })
        
    elif request.method == 'DELETE':
        db.session.delete(roadmap)
        db.session.commit()
        return jsonify({'message': 'Roadmap deleted successfully'})
    
    data = request.form or request.get_json()
    
    # Update roadmap fields
    roadmap.goals = data['goals'] if 'goals' in data else roadmap.goals
    roadmap.target_role = data['target_role'] if 'target_role' in data else roadmap.target_role
    
    
    # Re-generate roadmap if significant changes
    if 'regenerate' in data and data['regenerate']:
        user = User.query.get(user_id)
        cv_data = None
        if user.cv_path and os.path.exists(user.cv_path):
            cv_data = parse_cv(user.cv_path)
            
        roadmap_data = gemini_service.generate_career_advice(
            cv_data=cv_data,
            career_interests=[roadmap.target_role],
            personality_traits=data.get('personality_traits', [])
        )
        
        roadmap.recommended_skills = roadmap_data.get('recommended_skills')
        roadmap.timeline = roadmap_data.get('timeline')
    
    db.session.commit()
    return jsonify({'message': 'Roadmap updated successfully'})

@career_bp.route('/advice', methods=['POST'])
@jwt_required()
def get_career_advice():
    """Get career advice based on uploaded CV and preferences"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': userNotFoundErrStr}), 404
    
    data = request.form or request.get_json()
    
    # Extract skills from CV if user has uploaded one
    cv_data = []
    if user.cv_path and os.path.exists(user.cv_path):
        cv_data = parse_cv(user.cv_path)
    
    # Get career preferences
    preferences = data.get('preferences', {})
    personality_traits = data.get('personality_traits', [])
    
    prefs_list = [f"'Preference': {k}, 'value': {v} " for k, v in preferences.items()]
    
    # Use Gemini to generate career advice
    advice = gemini_service.generate_career_advice(
        cv_data=cv_data,
        career_interests=prefs_list,
        personality_traits=personality_traits
    )
    
    return jsonify({
        'advice': advice,
        'suitable_roles': advice.get('suitable_roles', []),
        'skills_to_develop': advice.get('skills_to_develop', []),
        'recommended_actions': advice.get('recommended_actions', [])
    })

@career_bp.route('/courses', methods=['GET'])
@jwt_required()
def recommended_courses():
    """Get recommended courses based on user's career roadmap"""
    user_id = get_jwt_identity()
    
    # Get user's latest roadmap
    roadmap = CareerRoadmap.query.filter_by(user_id=user_id).order_by(CareerRoadmap.created_at.desc()).first()
    
    if not roadmap:
        return jsonify({'error': 'No career roadmap found. Please create one first.'}), 404

    return jsonify({
        'recommended_courses': ["Advanced Ajax System", "DFS, BFS, and Fifferent Sorting Algorythms", "Best Practices in Python", "Advanced Data Structures and Algorithms"],
    })

@career_bp.route('/progress', methods=['POST'])
@jwt_required()
def update_progress():
    """Update user's progress on roadmap activities"""
    user_id = get_jwt_identity()
    data = request.form or request.get_json()
    
    roadmap_id = data.get('roadmap_id')
    roadmap = CareerRoadmap.query.filter_by(id=roadmap_id, user_id=user_id).first()
    
    if not roadmap:
        return jsonify({'error': 'Roadmap not found or access denied'}), 404
    
    # Update progress data
    progress_data = data.get('progress', {})
    if not roadmap.progress:
        roadmap.progress = {}
    
    # Merge new progress with existing progress
    roadmap.progress.update(progress_data)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Progress updated successfully',
        'current_progress': roadmap.progress
    })

@career_bp.route('/view', methods=['GET'])
@jwt_required()
def view_career_page():
    """Render the career development page"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': userNotFoundErrStr}), 404
    
    # Get the user's latest roadmap
    roadmap = CareerRoadmap.query.filter_by(user_id=user_id).order_by(CareerRoadmap.created_at.desc()).first()
    
    # Return the career development page with user data
    return render_template(
        'career/dashboard.html',
        user=user,
        roadmap=roadmap
    )