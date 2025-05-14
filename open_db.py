"""
Database initialization script for Automated HR system.
This script will:
1. Create all database tables
2. Add sample data for testing
"""

import os
import sys
import random
from datetime import datetime, timedelta
import json
from werkzeug.security import generate_password_hash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Database configuration
DATABASE_URI = os.environ.get('DATABASE_URI', 'postgresql://postgres:password@localhost:5432/automated_hr')

def init_db():
    """Initialize database and create tables"""
    from app import create_app
    from app.models import db, User, Enterprise, Job, Application, Interview, InterviewQuestion, CareerRoadmap, Notification, TeamMember
    
    app = create_app()
    
    with app.app_context():
        # Create all tables
        db.create_all()
        print("✅ Database tables created")

        # Check if data already exists
        if User.query.first() is not None:
            print("Data already exists in database. Skipping sample data creation.")
            return

        # Create sample data
        create_sample_data(db, User, Enterprise, Job, Application, Interview, InterviewQuestion, CareerRoadmap, Notification, TeamMember)
        print("✅ Sample data created")

def create_sample_data(db, User, Enterprise, Job, Application, Interview, InterviewQuestion, CareerRoadmap, Notification, TeamMember):
    """Create sample data for testing."""
    
    # Create sample users
    users = [
        User(
            name='John Doe',
            email='john@example.com',
            role='user',
            profile_data={
                'skills': ['Python', 'JavaScript', 'SQL', 'Data Analysis'],
                'experience': [
                    {'title': 'Software Developer', 'company': 'Tech Solutions', 'years': '2018-2020'},
                    {'title': 'Data Analyst', 'company': 'Data Corp', 'years': '2020-2023'}
                ],
                'education': [
                    {'degree': 'Bachelor of Science', 'field': 'Computer Science', 'school': 'State University', 'year': '2018'}
                ]
            }
        ),
        User(
            name='Jane Smith',
            email='jane@example.com',
            role='user',
            profile_data={
                'skills': ['UI/UX Design', 'Figma', 'HTML/CSS', 'User Research'],
                'experience': [
                    {'title': 'UI Designer', 'company': 'Creative Agency', 'years': '2019-2022'},
                    {'title': 'UX Researcher', 'company': 'User First', 'years': '2022-present'}
                ],
                'education': [
                    {'degree': 'Bachelor of Arts', 'field': 'Design', 'school': 'Art Institute', 'year': '2019'}
                ]
            }
        ),
        User(
            name='Michael Johnson',
            email='michael@example.com',
            role='user',
            profile_data={
                'skills': ['Java', 'Spring Boot', 'Microservices', 'AWS'],
                'experience': [
                    {'title': 'Backend Developer', 'company': 'Enterprise Solutions', 'years': '2017-2021'},
                    {'title': 'Senior Developer', 'company': 'Cloud Tech', 'years': '2021-present'}
                ],
                'education': [
                    {'degree': 'Master of Computer Science', 'field': 'Software Engineering', 'school': 'Tech University', 'year': '2017'}
                ]
            }
        ),
        User(
            name='Admin User',
            email='admin@example.com',
            role='admin',
            profile_data={}
        )
    ]
    
    for user in users:
        user.set_password('password123')
        db.session.add(user)
    
    db.session.commit()
    
    # Create sample enterprises
    enterprises = [
        Enterprise(
            name='Tech Innovations Inc.',
            email='hr@techinnovations.com',
            description='Leading technology company focused on AI and machine learning solutions.',
            industry='Technology',
            website='https://techinnovations.com',
            location='San Franciscom, CA',
            size='51-200',
            custom_settings={
                'interview_duration': 45,
                'default_questions': [
                    'Tell us about your experience with AI technologies.',
                    'How do you approach problem-solving in a team environment?',
                    'Describe a challenging project you worked on and how you overcame obstacles.'
                ]
            }
        ),
        Enterprise(
            name='Global Finance Group',
            email='careers@globalfinance.com',
            description='International financial services company offering banking and investment solutions.',
            industry='Finance',
            website='https://globalfinance.com',
            location='New York, NY',
            size='501+',
            custom_settings={
                'interview_duration': 60,
                'default_questions': [
                    'What experience do you have with financial analysis?',
                    'How do you stay updated with market trends?',
                    'Describe a time when you had to make a difficult financial decision.'
                ]
            }
        ),
        Enterprise(
            name='Creative Design Studio',
            email='jobs@creativedesign.com',
            description='Boutique design agency specializing in branding and user experience.',
            industry='Design',
            website='https://creativedesign.com',
            location='Austin, TX',
            size='11-50',
            custom_settings={
                'interview_duration': 30,
                'default_questions': [
                    'What is your design process?',
                    'How do you incorporate user feedback into your designs?',
                    'Show us examples of your most successful projects.'
                ]
            }
        )
    ]
    
    for enterprise in enterprises:
        enterprise.set_password('enterprise123')
        db.session.add(enterprise)
    
    db.session.commit()
    
    # Create sample team members
    team_members = [
        TeamMember(
            name='Sarah Williams',
            email='sarah@techinnovations.com',
            role='admin',
            enterprise_id=1
        ),
        TeamMember(
            name='David Chen',
            email='david@techinnovations.com',
            role='member',
            enterprise_id=1
        ),
        TeamMember(
            name='Emily Johnson',
            email='emily@globalfinance.com',
            role='admin',
            enterprise_id=2
        )
    ]
    
    for member in team_members:
        member.set_password('teammember123')
        db.session.add(member)
    
    db.session.commit()
    
    # Create sample jobs
    jobs = [
        Job(
            title='Senior Python Developer',
            description='We are looking for an experienced Python developer to join our AI team.',
            requirements='5+ years of Python experience, knowledge of machine learning frameworks, and experience with cloud platforms.',
            location='San Francisco, CA',
            salary_range='$120,000 - $150,000',
            job_type='Full-time',
            remote=True,
            expires_at=datetime.utcnow() + timedelta(days=30),
            status='active',
            enterprise_id=1,
            interview_settings={
                'technical_focus': 'Python, AI/ML, Cloud',
                'required_questions': [
                    'Describe your experience with Python in production environments.',
                    'What machine learning frameworks have you worked with?',
                    'How do you approach testing and validation of ML models?'
                ],
                'personality_traits': ['Analytical', 'Problem-solver', 'Team player']
            }
        ),
        Job(
            title='UX/UI Designer',
            description='Join our creative team to design intuitive user experiences for our products.',
            requirements='3+ years of UX/UI design experience, proficiency in Figma and Adobe Creative Suite, portfolio of previous work.',
            location='Austin, TX',
            salary_range='$80,000 - $110,000',
            job_type='Full-time',
            remote=True,
            expires_at=datetime.utcnow() + timedelta(days=45),
            status='active',
            enterprise_id=3,
            interview_settings={
                'technical_focus': 'UX Design, UI Design, User Research',
                'required_questions': [
                    'Walk us through your design process from concept to implementation.',
                    'How do you collaborate with developers to ensure your designs are implemented correctly?',
                    'Describe a time when user feedback significantly changed your initial design.'
                ],
                'personality_traits': ['Creative', 'Collaborative', 'Detail-oriented']
            }
        ),
        Job(
            title='Financial Analyst',
            description='Analyze financial data to provide insights and recommendations for our clients.',
            requirements='Bachelor\'s degree in Finance or related field, 2+ years of financial analysis experience, proficiency in Excel and financial modeling.',
            location='New York, NY',
            salary_range='$75,000 - $95,000',
            job_type='Full-time',
            remote=False,
            expires_at=datetime.utcnow() + timedelta(days=60),
            status='active',
            enterprise_id=2,
            interview_settings={
                'technical_focus': 'Financial Analysis, Excel, Data Visualization',
                'required_questions': [
                    'Explain your approach to financial modeling.',
                    'How do you communicate complex financial information to non-financial stakeholders?',
                    'Describe a time when your financial analysis led to a significant business decision.'
                ],
                'personality_traits': ['Analytical', 'Attention to detail', 'Clear communicator']
            }
        ),
        Job(
            title='Data Scientist',
            description='Use data to solve complex business problems and drive strategic decisions.',
            requirements='Master\'s degree in Statistics, Computer Science, or related field, experience with Python and R, knowledge of machine learning algorithms.',
            location='San Francisco, CA',
            salary_range='$110,000 - $140,000',
            job_type='Full-time',
            remote=True,
            expires_at=datetime.utcnow() + timedelta(days=30),
            status='active',
            enterprise_id=1,
            interview_settings={
                'technical_focus': 'Data Science, Python, Statistical Analysis',
                'required_questions': [
                    'Describe a data science project you completed from data collection to implementation.',
                    'What is your experience with feature engineering?',
                    'How do you validate the results of your models?'
                ],
                'personality_traits': ['Curious', 'Analytical', 'Problem-solver']
            }
        )
    ]
    
    for job in jobs:
        db.session.add(job)
    
    db.session.commit()
    
    # Create sample applications
    applications = [
        Application(
            user_id=1,
            job_id=4,
            cv_path='/uploads/john_doe_cv.pdf',
            cover_letter='I believe my experience in data analysis and Python programming makes me an excellent candidate for this position.',
            status='pending',
            application_data={
                'extracted_skills': ['Python', 'SQL', 'Data Analysis', 'Machine Learning'],
                'skill_match_score': 85
            }
        ),
        Application(
            user_id=2,
            job_id=2,
            cv_path='/uploads/jane_smith_cv.pdf',
            cover_letter='As a passionate UX/UI designer with 4 years of experience, I am excited about the opportunity to join your creative team.',
            status='interview_scheduled',
            application_data={
                'extracted_skills': ['UI Design', 'UX Research', 'Figma', 'Adobe XD'],
                'skill_match_score': 90
            }
        ),
        Application(
            user_id=3,
            job_id=1,
            cv_path='/uploads/michael_johnson_cv.pdf',
            cover_letter='With over 6 years of experience in software development including Python and cloud services, I am well-positioned to contribute to your AI team.',
            status='pending',
            application_data={
                'extracted_skills': ['Java', 'Spring Boot', 'AWS', 'Microservices'],
                'skill_match_score': 75
            }
        )
    ]
    
    for application in applications:
        db.session.add(application)
    
    db.session.commit()
    
    # Create sample interviews
    interviews = [
        Interview(
            user_id=1,
            job_id=4,
            scheduled_time=datetime.utcnow() + timedelta(days=5),
            transcript=None,  # Will be filled after the interview
            summary=None,  # Will be filled after the interview
            score=None,  # Will be filled after the interview
            detailed_scores=None,  # Will be filled after the interview
            feedback=None,  # Will be filled after the interview
            interview_type='job_specific',
            status='scheduled'
        ),
        Interview(
            user_id=2,
            job_id=2,
            scheduled_time=datetime.utcnow() + timedelta(days=3),
            transcript=None,
            summary=None,
            score=None,
            detailed_scores=None,
            feedback=None,
            interview_type='job_specific',
            status='scheduled'
        ),
        Interview(
            user_id=3,
            job_id=None,  # General assessment
            start_time=datetime.utcnow() - timedelta(days=2),
            end_time=datetime.utcnow() - timedelta(days=2) + timedelta(minutes=45),
            transcript="Q: Tell me about your experience with Java.\nA: I have been working with Java for over 6 years...",
            summary="Michael demonstrates strong experience with Java and enterprise development. He has good knowledge of microservices architecture and AWS cloud services.",
            score=82.5,
            detailed_scores={
                'technical_knowledge': 85,
                'communication': 80,
                'problem_solving': 78,
                'culture_fit': 90
            },
            feedback="Michael shows excellent technical knowledge and experience with enterprise Java development. He could improve on explaining complex concepts more clearly. Overall, he would be a strong addition to a backend development team.",
            interview_type='general',
            status='completed'
        )
    ]
    
    for interview in interviews:
        db.session.add(interview)
    
    db.session.commit()
    
    # Create sample interview questions for the completed interview
    questions = [
        InterviewQuestion(
            interview_id=3,
            question="Tell me about your experience with Java.",
            answer="I have been working with Java for over 6 years, primarily in enterprise environments. I've built microservices using Spring Boot and have experience with both monolithic and distributed architectures.",
            score=85,
            feedback="Good detailed answer showing deep experience with Java."
        ),
        InterviewQuestion(
            interview_id=3,
            question="How do you approach designing microservices?",
            answer="I start by identifying domain boundaries and defining clear interfaces between services. I ensure services are loosely coupled and highly cohesive. I also consider data ownership, scalability needs, and monitoring requirements from the beginning.",
            score=90,
            feedback="Excellent understanding of microservice architecture principles."
        ),
        InterviewQuestion(
            interview_id=3,
            question="Describe a challenging problem you solved recently.",
            answer="We had performance issues with our database queries in a high-traffic service. I implemented a caching solution and optimized our most expensive queries, which reduced response times by 70%.",
            score=82,
            feedback="Good practical example, but could have provided more details on the specific optimizations made."
        ),
        InterviewQuestion(
            interview_id=3,
            question="How do you handle conflicts in a team?",
            answer="I believe in addressing conflicts directly but respectfully. I try to understand all perspectives and find common ground. In my last role, we had disagreements about the architecture approach, so I organized a workshop to list pros and cons of each option, which helped us reach consensus.",
            score=80,
            feedback="Shows good conflict resolution skills and a collaborative approach."
        )
    ]
    
    for question in questions:
        db.session.add(question)
    
    db.session.commit()
    
    # Create sample career roadmaps
    roadmaps = [
        CareerRoadmap(
            user_id=1,
            title="Data Science Career Path",
            description="A roadmap to transition from data analysis to data science roles",
            goals={
                "short_term": "Gain practical experience with machine learning projects",
                "medium_term": "Secure a junior data scientist position",
                "long_term": "Become a senior data scientist specializing in NLP"
            },
            recommended_skills=[
                {"name": "Python", "priority": "high", "resources": ["Coursera Python for Data Science", "Real Python tutorials"]},
                {"name": "Machine Learning", "priority": "high", "resources": ["Andrew Ng's Machine Learning course", "Hands-On Machine Learning with Scikit-Learn"]},
                {"name": "SQL", "priority": "medium", "resources": ["SQL for Data Analysis", "PostgreSQL tutorials"]},
                {"name": "Natural Language Processing", "priority": "medium", "resources": ["NLP Specialization on Coursera", "NLTK documentation"]}
            ],
            recommended_roles=[
                {"title": "Junior Data Scientist", "timeline": "1-2 years"},
                {"title": "Data Scientist", "timeline": "2-4 years"},
                {"title": "Senior Data Scientist", "timeline": "4+ years"}
            ],
            recommended_courses=[
                {"name": "Machine Learning", "provider": "Coursera", "duration": "3 months"},
                {"name": "Deep Learning Specialization", "provider": "Coursera", "duration": "5 months"},
                {"name": "Data Science Certificate", "provider": "DataCamp", "duration": "6 months"}
            ],
            timeline={
                "2023": "Complete Python and ML fundamentals courses, build 2-3 portfolio projects",
                "2024": "Gain entry-level data science position, focus on applied ML skills",
                "2025": "Specialize in NLP, contribute to open source projects",
                "2026": "Move to mid-level data scientist role"
            }
        ),
        CareerRoadmap(
            user_id=2,
            title="UX/UI Design Leadership Path",
            description="A roadmap to advance from UX/UI designer to design leadership roles",
            goals={
                "short_term": "Build expertise in user research methodologies",
                "medium_term": "Lead design for major product features",
                "long_term": "Become a UX Director or Head of Design"
            },
            recommended_skills=[
                {"name": "User Research", "priority": "high", "resources": ["Just Enough Research by Erika Hall", "UX Research courses on LinkedIn Learning"]},
                {"name": "Design Systems", "priority": "high", "resources": ["Design Systems Handbook", "Figma Design System course"]},
                {"name": "Leadership", "priority": "medium", "resources": ["Design Leadership courses", "Manager books by Julie Zhuo"]},
                {"name": "Measuring Design Impact", "priority": "medium", "resources": ["Lean Analytics", "Google Analytics for Designers"]}
            ],
            recommended_roles=[
                {"title": "Senior UX/UI Designer", "timeline": "1-2 years"},
                {"title": "UX Lead", "timeline": "2-3 years"},
                {"title": "Design Manager", "timeline": "3-5 years"},
                {"title": "Director of UX", "timeline": "5+ years"}
            ],
            recommended_courses=[
                {"name": "Advanced User Research", "provider": "Nielsen Norman Group", "duration": "1 month"},
                {"name": "Design Leadership", "provider": "DesignOps Global Conference", "duration": "2 days"},
                {"name": "Strategic Design Thinking", "provider": "IDEO", "duration": "3 months"}
            ],
            timeline={
                "2023": "Develop expertise in user research and testing methodologies",
                "2024": "Take on project lead responsibilities, mentor junior designers",
                "2025": "Move into formal design leadership role managing small team",
                "2026": "Expand leadership scope, influence product strategy"
            }
        )
    ]
    
    for roadmap in roadmaps:
        db.session.add(roadmap)
    
    db.session.commit()
    
    # Create sample notifications
    notifications = [
        Notification(
            user_id=1,
            message="Your interview for Data Scientist position is scheduled for Friday at 2:00 PM.",
            read=False,
            notification_type="interview",
            related_id=1
        ),
        Notification(
            user_id=2,
            message="Your application for UX/UI Designer position has moved to the interview stage.",
            read=True,
            notification_type="application",
            related_id=2
        ),
        Notification(
            user_id=3,
            message="Your general assessment has been completed. View your results now!",
            read=False,
            notification_type="feedback",
            related_id=3
        ),
        Notification(
            user_id=1,
            message="We found a new job that matches your profile: AI Engineer at Tech Solutions Inc.",
            read=False,
            notification_type="job_match",
            related_id=None
        )
    ]
    
    for notification in notifications:
        db.session.add(notification)
    
    db.session.commit()
    
    print("Sample data created successfully!")


if __name__ == "__main__":
    # This can be run standalone
    init_db()