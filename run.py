import os
from app import create_app, socketio, db, celery
from app.models import User, Enterprise, Job, Application, Interview, InterviewQuestion, CareerRoadmap, Notification
from dotenv import load_dotenv

load_dotenv()

# Get configuration from environment or use default
app_config = os.getenv('FLASK_CONFIG', 'default')
print(f"Using configuration: {app_config}")
app = create_app(app_config)

# Context processor to make models available in shell context
@app.shell_context_processor
def make_shell_context():
    return {
        'db': db, 
        'User': User, 
        'Enterprise': Enterprise,
        'Job': Job,
        'Application': Application,
        'Interview': Interview,
        'InterviewQuestion': InterviewQuestion,
        'CareerRoadmap': CareerRoadmap,
        'Notification': Notification
    }

if __name__ == '__main__':
    # Use SocketIO to run the app instead of app.run()
    socketio.run(app, debug=app.config['DEBUG'], host='127.0.0.1', port=5000)