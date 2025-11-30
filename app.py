from flask import Flask
from models import db, Role, User, Department, Doctor, Patient
from datetime import datetime, timedelta, date
from config import Config
import os

from admin import admin_bp
from doctor import doctor_bp
from patient import patient_bp
from common import common_bp

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

app.jinja_env.globals.update(datetime=datetime, timedelta=timedelta)

# Register Blueprints
app.register_blueprint(common_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(doctor_bp)
app.register_blueprint(patient_bp)

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
    with app.app_context():
        db.create_all()

        admin_role = user_datastore.find_or_create_role(name='admin', description='Administrator')
        doctor_role = user_datastore.find_or_create_role(name='doctor', description='Doctor')
        patient_role = user_datastore.find_or_create_role(name='patient', description='Patient')

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

        admin_user = User.query.filter_by(username='admin').first()
        
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admin@hospital.com',
                full_name='System Administrator',
                phone='0000000000'
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit() 
        
        
        if not admin_user.has_role('admin'): admin_user.roles.append(admin_role)
        if not admin_user.has_role('doctor'): admin_user.roles.append(doctor_role)
        if not admin_user.has_role('patient'): admin_user.roles.append(patient_role)
        
        db.session.commit()

        if not Doctor.query.filter_by(user_id=admin_user.id).first():
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
            admin_patient = Patient(
                user_id=admin_user.id,
                date_of_birth=date(1990, 1, 1),
                gender="Other",
                address="Server Room",
                blood_group="O+"
            )
            db.session.add(admin_patient)

        db.session.commit()

if __name__ == '__main__':
    if not os.path.exists('hospital.db'):
        init_database()
    else:
        init_database()
        
    app.run(debug=True, port=8000)