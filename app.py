from flask import Flask
from models import db, Role, User, Department, Doctor, Patient
from datetime import datetime, timedelta, date
from config import Config
import os

# Import Blueprints
from admin import admin_bp
from doctor import doctor_bp
from patient import patient_bp
from common import common_bp

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db.init_app(app)

# Make datetime available in templates
app.jinja_env.globals.update(datetime=datetime, timedelta=timedelta)

# Register Blueprints
app.register_blueprint(common_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(doctor_bp)
app.register_blueprint(patient_bp)

# --- Helper for Role Creation (Simulating datastore) ---
class UserDatastore:
    def find_or_create_role(self, name, description=None):
        role = Role.query.filter_by(name=name).first()
        if not role:
            role = Role(name=name, description=description)
            db.session.add(role)
            db.session.commit()
            print(f"   + Created Role: {name}")
        return role

user_datastore = UserDatastore()

def init_database():
    """Initialize database, create roles, and ensure Admin has ALL profiles"""
    with app.app_context():
        db.create_all()

        # 1. Create Roles programmatically
        print("⚡ Initializing Roles...")
        admin_role = user_datastore.find_or_create_role(name='admin', description='Administrator')
        doctor_role = user_datastore.find_or_create_role(name='doctor', description='Doctor')
        patient_role = user_datastore.find_or_create_role(name='patient', description='Patient')

        # 2. Create Departments FIRST
        if Department.query.count() == 0:
            departments = [
                Department(name='Cardiology', description='Heart and cardiovascular system', price=1500.0),
                Department(name='Neurology', description='Brain and nervous system', price=1200.0),
                Department(name='Orthopedics', description='Bones and muscles', price=800.0),
                Department(name='Pediatrics', description='Children healthcare', price=600.0),
                Department(name='Dermatology', description='Skin, hair, and nails', price=700.0),
                Department(name='General Medicine', description='General health issues', price=500.0)
            ]
            for dept in departments:
                db.session.add(dept)
            db.session.commit()

        # 3. Create or Update Admin User
        admin_user = User.query.filter_by(username='admin').first()
        
        if not admin_user:
            print("   + Creating Admin User...")
            admin_user = User(
                username='admin',
                email='admin@hospital.com',
                full_name='System Administrator',
                phone='0000000000'
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit() # Commit to get ID
        
        # --- SELF-HEALING: Ensure Admin has all roles and profiles ---
        
        # Ensure Roles
        if not admin_user.has_role('admin'): admin_user.roles.append(admin_role)
        if not admin_user.has_role('doctor'): admin_user.roles.append(doctor_role)
        if not admin_user.has_role('patient'): admin_user.roles.append(patient_role)
        
        db.session.commit()

        # Ensure Doctor Profile
        if not Doctor.query.filter_by(user_id=admin_user.id).first():
            print("   + Adding missing Doctor profile to Admin")
            first_dept = Department.query.first()
            admin_doctor = Doctor(
                user_id=admin_user.id,
                department_id=first_dept.id if first_dept else 1,
                qualification="Super User",
                experience_years=10
            )
            db.session.add(admin_doctor)

        # Ensure Patient Profile
        if not Patient.query.filter_by(user_id=admin_user.id).first():
            print("   + Adding missing Patient profile to Admin")
            admin_patient = Patient(
                user_id=admin_user.id,
                date_of_birth=date(1990, 1, 1),
                gender="Other",
                address="Server Room",
                blood_group="O+"
            )
            db.session.add(admin_patient)

        db.session.commit()
        print("✅ Database check complete.")

if __name__ == '__main__':
    if not os.path.exists('hospital.db'):
        init_database()
    else:
        # Run init anyway to check/fix roles
        init_database()
        
    app.run(debug=True, port=8000)