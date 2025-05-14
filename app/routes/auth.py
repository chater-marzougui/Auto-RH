from flask import Blueprint, request, jsonify, current_app, render_template, url_for, redirect
from flask_jwt_extended import (create_access_token, create_refresh_token, 
                               jwt_required, get_jwt_identity, get_jwt)
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User, Enterprise, db
from datetime import datetime, timedelta, timezone
import uuid
import os
from itsdangerous import URLSafeTimedSerializer

auth_bp = Blueprint('auth', __name__)

# Helper function to send verification email
def send_verification_email(user_email, token):
    # In a real application, you would use a proper email service
    # For now, we just print the token for testing purposes
    verification_url = url_for('auth.verify_email', token=token, _external=True)
    print(f"Verification URL for {user_email}: {verification_url}")

# Function to generate email verification token
def generate_verification_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=current_app.config['SECURITY_PASSWORD_SALT'])

# Function to confirm verification token
def confirm_verification_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt=current_app.config['SECURITY_PASSWORD_SALT'],
            max_age=expiration
        )
        return email
    except Exception as e:
        return False, e

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('auth/register.html')
    
    data = request.form if request.form else request.get_json()
    
    # Check if required fields are present
    required_fields = ['email', 'password', 'name', 'account_type']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check if user already exists
    existing_user = User.query.filter_by(email=data['email']).first()
    existing_enterprise = Enterprise.query.filter_by(email=data['email']).first()
    
    if existing_user or existing_enterprise:
        return jsonify({'error': 'Email already registered'}), 409
    
    # Create user or enterprise based on account type
    if data['account_type'] == 'user':
        password_hash = generate_password_hash(data['password'])
        new_user = User(
            email=data['email'],
            password=password_hash,
            name=data['name'],
            created_at=datetime.now(timezone.utc),
            is_active=False  # User starts as inactive until email verification
        )
        db.session.add(new_user)
        db.session.commit()
        
        # Generate verification token and send email
        token = generate_verification_token(data['email'])
        send_verification_email(data['email'], token)
        
        return jsonify({'message': 'User registered successfully. Please verify your email.'}), 201
    
    elif data['account_type'] == 'enterprise':
        password_hash = generate_password_hash(data['password'])
        new_enterprise = Enterprise(
            email=data['email'],
            password=password_hash,
            name=data['name'],
            created_at=datetime.now(timezone.utc),
            is_active=False  # Enterprise starts as inactive until email verification
        )
        db.session.add(new_enterprise)
        db.session.commit()
        
        # Generate verification token and send email
        token = generate_verification_token(data['email'])
        send_verification_email(data['email'], token)
        
        return jsonify({'message': 'Enterprise registered successfully. Please verify your email.'}), 201
    
    else:
        return jsonify({'error': 'Invalid account type'}), 400

@auth_bp.route('/verify-email/<token>', methods=['GET'])
def verify_email(token):
    email = confirm_verification_token(token)
    if not email:
        return jsonify({'error': 'Invalid or expired verification token'}), 400
    
    # Check if it's a user or enterprise
    user = User.query.filter_by(email=email).first()
    if user:
        user.is_active = True
        db.session.commit()
        return redirect(url_for('auth.login'))
    
    enterprise = Enterprise.query.filter_by(email=email).first()
    if enterprise:
        enterprise.is_active = True
        db.session.commit()
        return redirect(url_for('auth.login'))
    
    return jsonify({'error': 'Account not found'}), 404

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('auth/login.html')
    
    data = request.form if request.form else request.get_json()
    
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({'error': 'Missing email or password'}), 400
    
    # Check if it's a user
    user = User.query.filter_by(email=data['email']).first()
    if user and check_password_hash(user.password, data['password']):
        if not user.is_active:
            return jsonify({'error': 'Please verify your email before logging in'}), 401
        
        access_token = create_access_token(
            identity={'id': user.id, 'type': 'user'},
            expires_delta=timedelta(hours=1)
        )
        refresh_token = create_refresh_token(
            identity={'id': user.id, 'type': 'user'},
            expires_delta=timedelta(days=30)
        )
        
        # Update last login time
        user.last_login = datetime.now(timezone.utc)
        db.session.commit()
        
        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user_type': 'user',
            'user_id': user.id
        }), 200
    
    # Check if it's an enterprise
    enterprise = Enterprise.query.filter_by(email=data['email']).first()
    if enterprise and check_password_hash(enterprise.password, data['password']):
        if not enterprise.is_active:
            return jsonify({'error': 'Please verify your email before logging in'}), 401
        
        access_token = create_access_token(
            identity={'id': enterprise.id, 'type': 'enterprise'},
            expires_delta=timedelta(hours=1)
        )
        refresh_token = create_refresh_token(
            identity={'id': enterprise.id, 'type': 'enterprise'},
            expires_delta=timedelta(days=30)
        )
        
        # Update last login time
        enterprise.last_login = datetime.now(timezone.utc)
        db.session.commit()
        
        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user_type': 'enterprise',
            'user_id': enterprise.id
        }), 200
    
    return jsonify({'error': 'Invalid email or password'}), 401

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    access_token = create_access_token(
        identity=identity,
        expires_delta=timedelta(hours=1)
    )
    return jsonify({'access_token': access_token}), 200

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        return render_template('auth/forgot_password.html')
    
    data = request.form if request.form else request.get_json()
    
    if not data or 'email' not in data:
        return jsonify({'error': 'Email is required'}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    enterprise = Enterprise.query.filter_by(email=data['email']).first()
    
    # Even if user not found, return success to prevent email enumeration
    if not user and not enterprise:
        return jsonify({'message': 'If your email exists in our system, you will receive a password reset link'}), 200
    
    # Generate a password reset token
    token = str(uuid.uuid4())
    expiry = datetime.now(timezone.utc) + timedelta(hours=24)
    
    if user:
        user.reset_token = token
        user.reset_token_expiry = expiry
    else:
        enterprise.reset_token = token
        enterprise.reset_token_expiry = expiry
    
    db.session.commit()
    
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    print(f"Password reset URL for {data['email']}: {reset_url}")
    
    return jsonify({'message': 'If your email exists in our system, you will receive a password reset link'}), 200

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'GET':
        return render_template('auth/reset_password.html', token=token)
    
    data = request.form if request.form else request.get_json()
    
    if not data or 'password' not in data:
        return jsonify({'error': 'New password is required'}), 400
    
    # Check user reset token
    user = User.query.filter_by(reset_token=token).first()
    from datetime import timezone

    if user and user.reset_token_expiry > datetime.now(timezone.utc):
        user.password = generate_password_hash(data['password'])
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        return jsonify({'message': 'Password has been reset successfully'}), 200
    
    # Check enterprise reset token
    enterprise = Enterprise.query.filter_by(reset_token=token).first()
    if enterprise and enterprise.reset_token_expiry > datetime.now(timezone.utc):
        enterprise.password = generate_password_hash(data['password'])
        enterprise.reset_token = None
        enterprise.reset_token_expiry = None
        db.session.commit()
        return jsonify({'message': 'Password has been reset successfully'}), 200
    
    return jsonify({'error': 'Invalid or expired token'}), 400

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    identity = get_jwt_identity()
    data = request.get_json()
    
    if not data or 'current_password' not in data or 'new_password' not in data:
        return jsonify({'error': 'Current and new passwords are required'}), 400
    
    if identity['type'] == 'user':
        user = User.query.get(identity['id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if not check_password_hash(user.password, data['current_password']):
            return jsonify({'error': 'Current password is incorrect'}), 401
        
        user.password = generate_password_hash(data['new_password'])
        db.session.commit()
    
    elif identity['type'] == 'enterprise':
        enterprise = Enterprise.query.get(identity['id'])
        if not enterprise:
            return jsonify({'error': 'Enterprise not found'}), 404
        
        if not check_password_hash(enterprise.password, data['current_password']):
            return jsonify({'error': 'Current password is incorrect'}), 401
        
        enterprise.password = generate_password_hash(data['new_password'])
        db.session.commit()
    
    return jsonify({'message': 'Password changed successfully'}), 200