"""
Routes for handling user operations like profile management and CV uploads.
"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import os
import json

from app import db
from app.models import User
from app.utils.file_parser import save_uploaded_file, parse_cv, FileUploadError

user = Blueprint('user', __name__)
notFoundErrorStr = "User not found"

@user.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get the current user's profile"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({"error": notFoundErrorStr}), 404
    
    profile_data = user.profile_data or {}
    
    return jsonify({
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at.isoformat(),
        "profile_data": profile_data
    })

@user.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update the current user's profile"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({"error": notFoundErrorStr}), 404
    
    data = request.json
    
    # Update basic user info if provided
    if 'name' in data:
        user.name = data['name']
    
    # Update profile data
    profile_data = user.profile_data or {}
    
    # Allow updating specific profile fields
    updatable_fields = [
        'about', 'skills', 'experience', 'education', 
        'certifications', 'languages', 'location',
        'job_preferences', 'social_links'
    ]
    
    for field in updatable_fields:
        if field in data:
            profile_data[field] = data[field]
    
    user.profile_data = profile_data
    
    try:
        db.session.commit()
        return jsonify({"message": "Profile updated successfully", "profile_data": profile_data})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating profile: {str(e)}")
        return jsonify({"error": "Failed to update profile"}), 500

@user.route('/upload-cv', methods=['POST'])
@jwt_required()
def upload_cv():
    """Upload and parse a CV file"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({"error": notFoundErrorStr}), 404
    
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    try:
        # Save the file
        file_path, new_filename = save_uploaded_file(file, directory='cvs')
        
        # Parse the CV
        cv_data = parse_cv(file_path)
        
        # Update user profile with CV data
        profile_data = user.profile_data or {}
        
        # Store CV file path
        profile_data['cv_filename'] = new_filename
        profile_data['cv_path'] = file_path
        
        # Update profile with extracted data if not already set
        if 'skills' not in profile_data or not profile_data['skills']:
            profile_data['skills'] = cv_data['skills']
            
        if 'education' not in profile_data or not profile_data['education']:
            profile_data['education'] = cv_data['education']
            
        if 'experience' not in profile_data or not profile_data['experience']:
            profile_data['experience'] = cv_data['experience']
        
        # Update the user
        user.profile_data = profile_data
        db.session.commit()
        
        return jsonify({
            "message": "CV uploaded and parsed successfully",
            "cv_data": cv_data,
            "profile_data": profile_data
        })
        
    except FileUploadError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error uploading CV: {str(e)}")
        return jsonify({"error": "Failed to process CV"}), 500

@user.route('/cvs', methods=['GET'])
@jwt_required()
def get_user_cvs():
    """Get all CVs uploaded by the user"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({"error": notFoundErrorStr}), 404
    
    profile_data = user.profile_data or {}
    
    # Get CV details if available
    cv_info = None
    if 'cv_filename' in profile_data and 'cv_path' in profile_data:
        cv_info = {
            "filename": profile_data['cv_filename'],
            "uploaded_at": profile_data.get('cv_uploaded_at', None)
        }
    
    return jsonify({
        "cvs": [cv_info] if cv_info else []
    })