from flask import Flask, render_template, redirect, url_for, flash, request, session
from models import db, Admin, Doctor, Patient, Department, Appointment, Treatment, DoctorAvailability
from datetime import datetime, date, timedelta
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hospital.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

def init_database():
    """Initialize database and create default admin"""
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if admin exists, if not create one
        admin = Admin.query.filter_by(username='admin').first()
        if not admin:
            admin = Admin(
                username='admin',
                email='admin@hospital.com',
                full_name='System Administrator'
            )
            admin.set_password('admin123')  # Default password
            db.session.add(admin)
            
            # Create some default departments
            departments = [
                Department(name='Cardiology', description='Heart and cardiovascular system'),
                Department(name='Neurology', description='Brain and nervous system'),
                Department(name='Orthopedics', description='Bones and muscles'),
                Department(name='Pediatrics', description='Children healthcare'),
                Department(name='Dermatology', description='Skin, hair, and nails'),
                Department(name='General Medicine', description='General health issues')
            ]
            
            for dept in departments:
                db.session.add(dept)
            
            db.session.commit()
            print("✅ Database initialized successfully!")
            print("📝 Default Admin Created:")
            print("   Username: admin")
            print("   Password: admin123")
        else:
            print("ℹ️  Database already initialized.")


@app.route('/')
def index():
    """Landing page"""
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Common login page for all users"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        
        if role == 'admin':
            user = Admin.query.filter_by(username=username).first()
            if user and user.check_password(password):
                session['user_id'] = user.id
                session['user_role'] = 'admin'
                session['user_name'] = user.full_name
                flash('Login successful!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid credentials!', 'danger')
        
        elif role == 'doctor':
            user = Doctor.query.filter_by(username=username).first()
            if user and user.check_password(password):
                if not user.is_active:
                    flash('Your account has been deactivated. Contact admin.', 'warning')
                    return redirect(url_for('login'))
                session['user_id'] = user.id
                session['user_role'] = 'doctor'
                session['user_name'] = user.full_name
                flash('Login successful!', 'success')
                return redirect(url_for('doctor_dashboard'))
            else:
                flash('Invalid credentials!', 'danger')
        
        elif role == 'patient':
            user = Patient.query.filter_by(username=username).first()
            if user and user.check_password(password):
                if not user.is_active:
                    flash('Your account has been deactivated. Contact admin.', 'warning')
                    return redirect(url_for('login'))
                session['user_id'] = user.id
                session['user_role'] = 'patient'
                session['user_name'] = user.full_name
                flash('Login successful!', 'success')
                return redirect(url_for('patient_dashboard'))
            else:
                flash('Invalid credentials!', 'danger')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))


@app.route('/admin/dashboard')
def admin_dashboard():
    """Admin dashboard"""
    if session.get('user_role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))
    
    # Get statistics
    total_doctors = Doctor.query.filter_by(is_active=True).count()
    total_patients = Patient.query.filter_by(is_active=True).count()
    total_appointments = Appointment.query.count()
    today_appointments = Appointment.query.filter_by(appointment_date=date.today()).count()
    
    # Get recent appointments
    recent_appointments = Appointment.query.order_by(Appointment.created_at.desc()).limit(5).all()
    
    return render_template('admin_dashboard.html',
                         total_doctors=total_doctors,
                         total_patients=total_patients,
                         total_appointments=total_appointments,
                         today_appointments=today_appointments,
                         recent_appointments=recent_appointments)


@app.route('/doctor/dashboard')
def doctor_dashboard():
    """Doctor dashboard"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))
    
    doctor_id = session.get('user_id')
    doctor = Doctor.query.get(doctor_id)
    
    # Get today's appointments
    today = date.today()
    today_appointments = Appointment.query.filter_by(
        doctor_id=doctor_id,
        appointment_date=today
    ).order_by(Appointment.appointment_time).all()
    
    # Get upcoming appointments (next 7 days)
    week_later = today + timedelta(days=7)
    upcoming_appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date > today,
        Appointment.appointment_date <= week_later,
        Appointment.status == 'Booked'
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).all()
    
    # Get unique patients
    patient_ids = db.session.query(Appointment.patient_id).filter_by(doctor_id=doctor_id).distinct().all()
    total_patients = len(patient_ids)
    
    return render_template('doctor_dashboard.html',
                         doctor=doctor,
                         today_appointments=today_appointments,
                         upcoming_appointments=upcoming_appointments,
                         total_patients=total_patients)


@app.route('/patient/dashboard')
def patient_dashboard():
    """Patient dashboard"""
    if session.get('user_role') != 'patient':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))
    
    patient_id = session.get('user_id')
    patient = Patient.query.get(patient_id)
    
    # Get all departments
    departments = Department.query.all()
    
    # Get upcoming appointments
    upcoming_appointments = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.appointment_date >= date.today(),
        Appointment.status == 'Booked'
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).all()
    
    # Get past appointments with treatment
    past_appointments = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.status == 'Completed'
    ).order_by(Appointment.appointment_date.desc()).limit(5).all()
    
    return render_template('patient_dashboard.html',
                         patient=patient,
                         departments=departments,
                         upcoming_appointments=upcoming_appointments,
                         past_appointments=past_appointments)


@app.route('/admin/doctors')
def admin_manage_doctors():
    """Manage doctors"""
    if session.get('user_role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctors = Doctor.query.all()
    return render_template('admin_manage_doctors.html', doctors=doctors)


@app.route('/admin/patients')
def admin_manage_patients():
    """Manage patients"""
    if session.get('user_role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    patients = Patient.query.all()
    return render_template('admin_manage_patients.html', patients=patients)


@app.route('/admin/appointments')
def admin_all_appointments():
    """View all appointments"""
    if session.get('user_role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    appointments = Appointment.query.order_by(Appointment.appointment_date.desc()).all()
    return render_template('admin_all_appointments.html', appointments=appointments)


@app.route('/doctor/appointments')
def doctor_my_appointments():
    """Doctor's appointments"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor_id = session.get('user_id')
    appointments = Appointment.query.filter_by(doctor_id=doctor_id).order_by(Appointment.appointment_date.desc()).all()
    return render_template('doctor_my_appointments.html', appointments=appointments)

@app.route('/doctor/patients')
def doctor_my_patients():
    """Doctor's patients"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor_id = session.get('user_id')
    patient_ids = db.session.query(Appointment.patient_id).filter_by(doctor_id=doctor_id).distinct().all()
    patients = Patient.query.filter(Patient.id.in_([p_id for p_id, in patient_ids])).all()
    return render_template('doctor_my_patients.html', patients=patients)


@app.route('/patient/find_doctors', methods=['GET', 'POST'])
def patient_find_doctors():
    """Find doctors"""
    if session.get('user_role') != 'patient':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    departments = Department.query.all()
    doctors = Doctor.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        department_id = request.form.get('department_id')
        if department_id:
            doctors = Doctor.query.filter_by(department_id=department_id, is_active=True).all()

    return render_template('patient_find_doctors.html', doctors=doctors, departments=departments)


@app.route('/patient/book_appointment/<int:doctor_id>', methods=['GET', 'POST'])
def patient_book_appointment(doctor_id):
    """Book an appointment"""
    if session.get('user_role') != 'patient':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor = Doctor.query.get_or_404(doctor_id)
    if request.method == 'POST':
        appointment_date = request.form.get('appointment_date')
        appointment_time = request.form.get('appointment_time')
        reason = request.form.get('reason')

        appointment = Appointment(
            patient_id=session['user_id'],
            doctor_id=doctor.id,
            appointment_date=datetime.strptime(appointment_date, '%Y-%m-%d').date(),
            appointment_time=datetime.strptime(appointment_time, '%H:%M').time(),
            reason=reason
        )
        db.session.add(appointment)
        db.session.commit()
        flash('Appointment booked successfully!', 'success')
        return redirect(url_for('patient_my_appointments'))

    return render_template('patient_book_appointment.html', doctor=doctor)


@app.route('/patient/my_appointments')
def patient_my_appointments():
    """Patient's appointments"""
    if session.get('user_role') != 'patient':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    patient_id = session.get('user_id')
    appointments = Appointment.query.filter_by(patient_id=patient_id).order_by(Appointment.appointment_date.desc()).all()
    return render_template('patient_my_appointments.html', appointments=appointments)


@app.route('/admin/departments', methods=['GET', 'POST'])
def admin_manage_departments():
    """Manage departments"""
    if session.get('user_role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')

        if Department.query.filter_by(name=name).first():
            flash('Department with this name already exists.', 'warning')
        else:
            department = Department(name=name, description=description)
            db.session.add(department)
            db.session.commit()
            flash('Department added successfully!', 'success')
        return redirect(url_for('admin_manage_departments'))

    departments = Department.query.all()
    return render_template('admin_departments.html', departments=departments)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Patient registration"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        dob = request.form.get('date_of_birth')
        gender = request.form.get('gender')
        address = request.form.get('address')
        blood_group = request.form.get('blood_group')
        
        # Check if username or email already exists
        if Patient.query.filter_by(username=username).first():
            flash('Username already exists!', 'danger')
            return redirect(url_for('register'))
        
        if Patient.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))
        
        # Create new patient
        patient = Patient(
            username=username,
            email=email,
            full_name=full_name,
            phone=phone,
            date_of_birth=datetime.strptime(dob, '%Y-%m-%d').date() if dob else None,
            gender=gender,
            address=address,
            blood_group=blood_group
        )
        patient.set_password(password)
        
        db.session.add(patient)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')


if __name__ == '__main__':
    # Initialize database on first run
    if not os.path.exists('hospital.db'):
        init_database()
    
    app.run(debug=True)