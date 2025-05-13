"""
This script initializes the database and creates the first migration.
Run this file to set up your database schema after creating your models.

Usage:
    python -m migrations.init_db
"""

import os
import sys

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from flask_migrate import init, migrate, upgrade

# Create app with development config
app = create_app('development')

with app.app_context():
    # Initialize migrations directory if it doesn't exist
    if not os.path.exists('migrations'):
        print("Initializing migrations directory...")
        init()
    
    # Create migration
    print("Creating migration for initial database schema...")
    migrate(message='Initial migration')
    
    # Apply migration
    print("Applying migration...")
    upgrade()
    
    print("Database initialized successfully!")