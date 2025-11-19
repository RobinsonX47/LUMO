"""
Debug script to check if the app is set up correctly
"""

from app import create_app
from extensions import db
from models import User
import os

def check_setup():
    print("🔍 Checking LUMO Setup...\n")
    
    # Check if instance folder exists
    if os.path.exists("instance"):
        print("✅ Instance folder exists")
    else:
        print("❌ Instance folder missing")
        
    # Check if database exists
    if os.path.exists("instance/lumo.db"):
        print("✅ Database file exists")
    else:
        print("❌ Database file missing")
    
    # Try to create app
    try:
        app = create_app()
        print("✅ App created successfully")
        
        with app.app_context():
            # Check tables
            try:
                user_count = User.query.count()
                print(f"✅ Database connected - {user_count} users found")
            except Exception as e:
                print(f"❌ Database error: {e}")
                
    except Exception as e:
        print(f"❌ App creation failed: {e}")
    
    print("\n" + "="*50)
    print("If you see errors above, try:")
    print("1. Delete instance/lumo.db")
    print("2. Run: python app.py")
    print("3. Run: python seed_data.py")
    print("="*50)

if __name__ == "__main__":
    check_setup()