from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()
userIdStr = 'users.id'

class User(db.Model):
    """User model for job seekers."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user', nullable=False)  # 'user', 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    profile_data = db.Column(JSONB, nullable=True)  # Stores skills, experience, education, etc.
    
    # Relationships
    interviews = db.relationship('Interview', backref='user', lazy='dynamic')
    applications = db.relationship('Application', backref='user', lazy='dynamic')
    career_roadmaps = db.relationship('CareerRoadmap', backref='user', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.name}>'
    

class TeamMember(db.Model):
    """Team member model for enterprises."""
    __tablename__ = 'team_members'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='member', nullable=False)  # 'member', 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    enterprise_id = db.Column(db.Integer, db.ForeignKey('enterprises.id'), nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<TeamMember {self.name}>'


class Enterprise(db.Model):
    """Enterprise model for companies using the platform."""
    __tablename__ = 'enterprises'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text, nullable=True)
    industry = db.Column(db.String(100), nullable=True)
    website = db.Column(db.String(200), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    size = db.Column(db.String(50), nullable=True)  # e.g., "1-10", "11-50", "51-200", "201-500", "501+"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    custom_settings = db.Column(JSONB, nullable=True)  # Custom interview settings, preferences
    
    # Relationships
    jobs = db.relationship('Job', backref='enterprise', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<Enterprise {self.name}>'


class Job(db.Model):
    """Job postings created by enterprises."""
    __tablename__ = 'jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    requirements = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(100), nullable=True)
    salary_range = db.Column(db.String(100), nullable=True)
    job_type = db.Column(db.String(50), nullable=True)  # e.g., "Full-time", "Part-time", "Contract"
    remote = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='active')  # 'active', 'closed', 'draft', 'archived'
    enterprise_id = db.Column(db.Integer, db.ForeignKey('enterprises.id'), nullable=False)
    interview_settings = db.Column(JSONB, nullable=True)  # Required questions, personality traits, etc.
    
    # Relationships
    applications = db.relationship('Application', backref='job', lazy='dynamic')
    interviews = db.relationship('Interview', backref='job', lazy='dynamic')
    
    def __repr__(self):
        return f'<Job {self.title} by {self.enterprise.name}>'


class Application(db.Model):
    """Job applications submitted by users."""
    __tablename__ = 'applications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(userIdStr), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    cv_path = db.Column(db.String(255), nullable=True)  # Path to CV file
    cover_letter = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'rejected', 'interview_scheduled', 'accepted'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Additional data like extracted skills, etc.
    application_data = db.Column(JSONB, nullable=True)
    
    def __repr__(self):
        return f'<Application {self.id} by User {self.user_id} for Job {self.job_id}>'


class Interview(db.Model):
    """Interviews conducted on the platform."""
    __tablename__ = 'interviews'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(userIdStr), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=True)  # Can be NULL for general assessments
    scheduled_time = db.Column(db.DateTime, nullable=True)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    transcript = db.Column(db.Text, nullable=True)  # Full interview transcript
    summary = db.Column(db.Text, nullable=True)  # AI-generated summary
    score = db.Column(db.Float, nullable=True)  # Overall score
    detailed_scores = db.Column(JSONB, nullable=True)  # Breakdown of scores by category
    feedback = db.Column(db.Text, nullable=True)  # AI-generated feedback
    interview_type = db.Column(db.String(20), default='general')  # 'general', 'job_specific'
    status = db.Column(db.String(20), default='scheduled')  # 'scheduled', 'in_progress', 'completed', 'cancelled'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    questions = db.relationship('InterviewQuestion', backref='interview', lazy='dynamic')
    
    def __repr__(self):
        interview_type = f" for {self.job.title}" if self.job else ""
        return f'<Interview {self.id} by {self.user.name}{interview_type}>'


class InterviewQuestion(db.Model):
    """Individual questions and answers from interviews."""
    __tablename__ = 'interview_questions'
    
    id = db.Column(db.Integer, primary_key=True)
    interview_id = db.Column(db.Integer, db.ForeignKey('interviews.id'), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=True)
    score = db.Column(db.Float, nullable=True)  # Score for this specific question
    feedback = db.Column(db.Text, nullable=True)  # Feedback on this answer
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<InterviewQuestion {self.id} for Interview {self.interview_id}>'


class CareerRoadmap(db.Model):
    """Career roadmaps generated for users."""
    __tablename__ = 'career_roadmaps'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(userIdStr), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    goals = db.Column(JSONB, nullable=True)  # Career goals
    recommended_skills = db.Column(JSONB, nullable=True)  # Skills to develop
    recommended_roles = db.Column(JSONB, nullable=True)  # Suitable job roles
    recommended_courses = db.Column(JSONB, nullable=True)  # Courses to take
    timeline = db.Column(JSONB, nullable=True)  # Timeline for skill development
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<CareerRoadmap {self.id} for User {self.user_id}>'


class Notification(db.Model):
    """Notifications for users."""
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(userIdStr), nullable=False)
    message = db.Column(db.Text, nullable=False)
    read = db.Column(db.Boolean, default=False)
    notification_type = db.Column(db.String(50), nullable=False)  # 'interview', 'application', 'feedback', 'job_match'
    related_id = db.Column(db.Integer, nullable=True)  # ID of related resource (interview, application, etc.)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Notification {self.id} for User {self.user_id}>'