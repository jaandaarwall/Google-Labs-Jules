

from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify
from backend.config import Config
from backend.Sqldatabase import db
from backend.models import *
from backend.user_datastore import user_datastore
from flask_security import Security, login_user, logout_user, current_user, utils
from datetime import datetime, date, timedelta
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    Security(app, user_datastore)
    
    # Make datetime available in templates
    app.jinja_env.globals.update(datetime=datetime, timedelta=timedelta)
    
    return app

app = create_app()

def init_db(app):
    """Initialize database with default data"""
    with app.app_context():
        db.create_all()
        
        # Create roles
        admin_role = user_datastore.find_or_create_role(name='admin', description='Administrator')
        doctor_role = user_datastore.find_or_create_role(name='doctor', description='Doctor')
        patient_role = user_datastore.find_or_create_role(name='patient', description='Patient')
        
        # Create admin user
        admin = user_datastore.find_user(username='admin')
        if not admin:
            admin_user = user_datastore.create_user(
                username='admin',
                full_name='System Administrator',
                email='admin@hospital.com',
                password='admin123',
                active=True,
                roles=[admin_role],
                fs_uniquifier=os.urandom(16).hex()
            )
            
            # Create default departments
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


# ==================== HELPER FUNCTIONS ====================

def get_user_role():
    """Get current user's primary role"""
    if current_user.is_authenticated:
        if any(role.name == 'admin' for role in current_user.roles):
            return 'admin'
        elif any(role.name == 'doctor' for role in current_user.roles):
            return 'doctor'
        elif any(role.name == 'patient' for role in current_user.roles):
            return 'patient'
    return None


# ==================== PUBLIC ROUTES ====================

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

        user = user_datastore.find_user(username=username)
        
        if user and utils.verify_password(password, user.password):
            # Check if user has the selected role
            user_roles = [r.name for r in user.roles]
            
            if role not in user_roles:
                flash('You do not have access to this role!', 'danger')
                return redirect(url_for('login'))
            
            if not user.active:
                flash('Your account has been deactivated. Contact admin.', 'warning')
                return redirect(url_for('login'))
            
            # Login user
            login_user(user)
            session['user_role'] = role
            session['user_name'] = username
            
            flash('Login successful!', 'success')
            
            # Redirect based on role
            if role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif role == 'doctor':
                return redirect(url_for('doctor_dashboard'))
            elif role == 'patient':
                return redirect(url_for('patient_dashboard'))
        else:
            flash('Invalid credentials!', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout user"""
    logout_user()
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))


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
        if user_datastore.find_user(username=username):
            flash('Username already exists!', 'danger')
            return redirect(url_for('register'))

        if user_datastore.find_user(email=email):
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))

        # Get patient role
        patient_role = user_datastore.find_role('patient')
        
        # Create new user
        new_user = user_datastore.create_user(
            username=username,
            full_name=full_name,
            email=email,
            password=password,
            active=True,
            roles=[patient_role],
            phone=phone,
            date_of_birth=datetime.strptime(dob, '%Y-%m-%d').date() if dob else None,
            gender=gender,
            address=address,
            blood_group=blood_group,
            fs_uniquifier=os.urandom(16).hex()
        )
        
        # Create patient record
        patient = Patient(user_id=new_user.id)
        db.session.add(patient)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# ==================== ADMIN ROUTES ====================

@app.route('/admin/dashboard')
def admin_dashboard():
    """Admin dashboard"""
    if session.get('user_role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    # Get statistics
    total_doctors = Doctor.query.filter_by(is_active=True).count()
    total_patients = Patient.query.count()
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


@app.route('/admin/doctors')
def admin_doctors():
    """Manage doctors"""
    if session.get('user_role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctors = Doctor.query.all()
    return render_template('admin_doctors.html', doctors=doctors)


@app.route('/admin/doctor/add', methods=['GET', 'POST'])
def admin_add_doctor():
    """Add new doctor"""
    if session.get('user_role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        department_id = request.form.get('department_id')
        qualification = request.form.get('qualification')
        experience_years = request.form.get('experience_years')

        # Check if username or email exists
        if user_datastore.find_user(username=username):
            flash('Username already exists!', 'danger')
            return redirect(url_for('admin_add_doctor'))

        if user_datastore.find_user(email=email):
            flash('Email already exists!', 'danger')
            return redirect(url_for('admin_add_doctor'))

        # Get doctor role
        doctor_role = user_datastore.find_role('doctor')
        
        # Create new user
        new_user = user_datastore.create_user(
            username=username,
            full_name=full_name,
            email=email,
            password=password,
            active=True,
            roles=[doctor_role],
            phone=phone,
            fs_uniquifier=os.urandom(16).hex()
        )
        
        # Create doctor record
        doctor = Doctor(
            user_id=new_user.id,
            department_id=department_id,
            qualification=qualification,
            experience_years=int(experience_years) if experience_years else 0
        )
        db.session.add(doctor)
        db.session.commit()

        flash(f'Doctor {username} added successfully!', 'success')
        return redirect(url_for('admin_doctors'))

    departments = Department.query.all()
    return render_template('admin_add_doctor.html', departments=departments)


@app.route('/admin/doctor/edit/<int:doctor_id>', methods=['GET', 'POST'])
def admin_edit_doctor(doctor_id):
    """Edit doctor details"""
    if session.get('user_role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor = Doctor.query.get_or_404(doctor_id)
    user = doctor.user

    if request.method == 'POST':
        user.full_name = request.form.get('full_name')
        user.email = request.form.get('email')
        user.phone = request.form.get('phone')
        doctor.department_id = request.form.get('department_id')
        doctor.qualification = request.form.get('qualification')
        doctor.experience_years = int(request.form.get('experience_years', 0))

        db.session.commit()
        flash('Doctor details updated successfully!', 'success')
        return redirect(url_for('admin_doctors'))

    departments = Department.query.all()
    return render_template('admin_edit_doctor.html', doctor=doctor, departments=departments)


@app.route('/admin/doctor/toggle/<int:doctor_id>')
def admin_toggle_doctor(doctor_id):
    """Activate/Deactivate doctor"""
    if session.get('user_role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor = Doctor.query.get_or_404(doctor_id)
    doctor.is_active = not doctor.is_active
    doctor.user.active = doctor.is_active
    db.session.commit()

    status = 'activated' if doctor.is_active else 'deactivated'
    flash(f'Doctor {doctor.user.username} has been {status}!', 'success')
    return redirect(url_for('admin_doctors'))


@app.route('/admin/patients')
def admin_patients():
    """Manage patients"""
    if session.get('user_role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    patients = Patient.query.all()
    return render_template('admin_patients.html', patients=patients)


@app.route('/admin/patient/toggle/<int:patient_id>')
def admin_toggle_patient(patient_id):
    """Activate/Deactivate patient"""
    if session.get('user_role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    patient = Patient.query.get_or_404(patient_id)
    patient.user.active = not patient.user.active
    db.session.commit()

    status = 'activated' if patient.user.active else 'deactivated'
    flash(f'Patient {patient.user.username} has been {status}!', 'success')
    return redirect(url_for('admin_patients'))


@app.route('/admin/patient/view/<int:patient_id>')
def admin_view_patient(patient_id):
    """View patient details and appointment history"""
    if session.get('user_role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    patient = Patient.query.get_or_404(patient_id)
    appointments = Appointment.query.filter_by(patient_id=patient.id).order_by(Appointment.appointment_date.desc()).all()

    return render_template('admin_view_patient.html', patient=patient, appointments=appointments)


@app.route('/admin/doctor/view/<int:doctor_id>')
def admin_view_doctor(doctor_id):
    """View doctor details and appointment history"""
    if session.get('user_role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor = Doctor.query.get_or_404(doctor_id)
    appointments = Appointment.query.filter_by(doctor_id=doctor.id).order_by(Appointment.appointment_date.desc()).all()

    return render_template('admin_view_doctor.html', doctor=doctor, appointments=appointments)


@app.route('/admin/appointments')
def admin_appointments():
    """View all appointments"""
    if session.get('user_role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    appointments = Appointment.query.order_by(Appointment.appointment_date.desc()).all()
    return render_template('admin_appointments.html', appointments=appointments)


@app.route('/admin/appointment/view/<int:appointment_id>')
def admin_view_appointment(appointment_id):
    """View full details of an appointment"""
    if session.get('user_role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    appointment = Appointment.query.get_or_404(appointment_id)
    return render_template('admin_view_appointment.html', appointment=appointment)


@app.route('/admin/search', methods=['GET', 'POST'])
def admin_search():
    """Search for doctors and patients"""
    if session.get('user_role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctors = []
    patients = []
    search_query = ''

    if request.method == 'POST':
        search_query = request.form.get('search_query', '').strip()

        if search_query:
            # Search in User table and join with Doctor/Patient
            doctor_users = User.query.join(Doctor).filter(
                db.or_(
                    User.username.ilike(f'%{search_query}%'),
                    User.email.ilike(f'%{search_query}%'),
                    User.phone.ilike(f'%{search_query}%')
                )
            ).all()
            doctors = [user.doctor for user in doctor_users if user.doctor]

            patient_users = User.query.join(Patient).filter(
                db.or_(
                    User.username.ilike(f'%{search_query}%'),
                    User.email.ilike(f'%{search_query}%'),
                    User.phone.ilike(f'%{search_query}%')
                )
            ).all()
            patients = [user.patient for user in patient_users if user.patient]

    return render_template('admin_search.html', doctors=doctors, patients=patients, search_query=search_query)


# ==================== PATIENT ROUTES ====================

@app.route('/patient/dashboard')
def patient_dashboard():
    """Patient dashboard"""
    if session.get('user_role') != 'patient':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    patient = Patient.query.filter_by(user_id=current_user.id).first()

    # Get all departments
    departments = Department.query.all()

    # Get upcoming appointments
    upcoming_appointments = Appointment.query.filter(
        Appointment.patient_id == patient.id,
        Appointment.appointment_date >= date.today(),
        Appointment.status == 'Booked'
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).all()

    # Get past appointments
    past_appointments = Appointment.query.filter(
        Appointment.patient_id == patient.id,
        Appointment.status == 'Completed'
    ).order_by(Appointment.appointment_date.desc()).limit(5).all()

    return render_template('patient_dashboard.html',
                         patient=patient,
                         departments=departments,
                         upcoming_appointments=upcoming_appointments,
                         past_appointments=past_appointments)


@app.route('/patient/doctors')
def patient_find_doctors():
    """Find doctors by specialization"""
    if session.get('user_role') != 'patient':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    department_id = request.args.get('department_id', type=int)

    if department_id:
        doctors = Doctor.query.filter_by(department_id=department_id, is_active=True).all()
        department = Department.query.get(department_id)
    else:
        doctors = Doctor.query.filter_by(is_active=True).all()
        department = None

    departments = Department.query.all()
    return render_template('patient_find_doctors.html', doctors=doctors, departments=departments, selected_department=department)


@app.route('/api/doctor/<int:doctor_id>/availability', methods=['GET'])
def get_doctor_availability(doctor_id):
    """API endpoint to get doctor availability"""
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'error': 'Date parameter is required'}), 400

    try:
        check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    availabilities = DoctorAvailability.query.filter_by(
        doctor_id=doctor_id, 
        date=check_date, 
        is_available=True
    ).all()

    slots = []
    for av in availabilities:
        start_time = datetime.combine(check_date, av.start_time)
        end_time = datetime.combine(check_date, av.end_time)

        while start_time < end_time:
            booked_count = Appointment.query.filter_by(
                doctor_id=doctor_id,
                appointment_date=check_date,
                appointment_time=start_time.time()
            ).count()

            if booked_count < av.total_seats:
                slots.append({'time': start_time.strftime('%H:%M')})

            start_time += timedelta(minutes=30)

    return jsonify(slots)


@app.route('/patient/book/<int:doctor_id>', methods=['GET', 'POST'])
def patient_book_appointment(doctor_id):
    """Book appointment with doctor"""
    if session.get('user_role') != 'patient':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor = Doctor.query.get_or_404(doctor_id)
    patient = Patient.query.filter_by(user_id=current_user.id).first()

    if request.method == 'POST':
        appointment_date = datetime.strptime(request.form.get('appointment_date'), '%Y-%m-%d').date()
        appointment_time = datetime.strptime(request.form.get('appointment_time'), '%H:%M').time()
        reason = request.form.get('reason')

        # Check availability
        availability = DoctorAvailability.query.filter(
            DoctorAvailability.doctor_id == doctor_id,
            DoctorAvailability.date == appointment_date,
            DoctorAvailability.start_time <= appointment_time,
            DoctorAvailability.end_time > appointment_time,
            DoctorAvailability.is_available == True
        ).first()

        if not availability:
            flash('The selected time slot is not available.', 'danger')
            return redirect(url_for('patient_book_appointment', doctor_id=doctor_id))

        booked_count = Appointment.query.filter_by(
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            appointment_time=appointment_time
        ).count()

        if booked_count >= availability.total_seats:
            flash('This time slot is fully booked! Please choose another time.', 'danger')
            return redirect(url_for('patient_book_appointment', doctor_id=doctor_id))

        # Create appointment
        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            reason=reason,
            status='Booked'
        )

        db.session.add(appointment)
        db.session.commit()

        flash('Appointment booked successfully!', 'success')
        return redirect(url_for('patient_dashboard'))

    return render_template('patient_book_appointment.html', doctor=doctor)


@app.route('/patient/appointments')
def patient_appointments():
    """View all patient appointments"""
    if session.get('user_role') != 'patient':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    patient = Patient.query.filter_by(user_id=current_user.id).first()
    appointments = Appointment.query.filter_by(patient_id=patient.id).order_by(Appointment.appointment_date.desc()).all()

    return render_template('patient_appointments.html', appointments=appointments)


@app.route('/patient/cancel/<int:appointment_id>')
def patient_cancel_appointment(appointment_id):
    """Cancel appointment"""
    if session.get('user_role') != 'patient':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    appointment = Appointment.query.get_or_404(appointment_id)
    patient = Patient.query.filter_by(user_id=current_user.id).first()

    if appointment.patient_id != patient.id:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('patient_dashboard'))

    if appointment.status == 'Booked':
        appointment.status = 'Cancelled'
        db.session.commit()
        flash('Appointment cancelled successfully!', 'success')
    else:
        flash('Cannot cancel this appointment!', 'danger')

    return redirect(url_for('patient_appointments'))


@app.route('/patient/history')
def patient_medical_history():
    """View patient's medical history"""
    if session.get('user_role') != 'patient':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    patient = Patient.query.filter_by(user_id=current_user.id).first()
    appointments = Appointment.query.filter_by(
        patient_id=patient.id, 
        status='Completed'
    ).order_by(Appointment.appointment_date.desc()).all()
    
    return render_template('patient_medical_history.html', appointments=appointments)


@app.route('/patient/profile', methods=['GET', 'POST'])
def patient_profile():
    """Manage patient profile"""
    if session.get('user_role') != 'patient':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    patient = Patient.query.filter_by(user_id=current_user.id).first()
    user = patient.user

    if request.method == 'POST':
        user.full_name = request.form.get('full_name')
        user.email = request.form.get('email')
        user.phone = request.form.get('phone')
        dob_str = request.form.get('date_of_birth')
        if dob_str:
            user.date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date()
        user.gender = request.form.get('gender')
        user.address = request.form.get('address')
        user.blood_group = request.form.get('blood_group')

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('patient_profile'))

    return render_template('patient_profile.html', patient=patient)


# ==================== DOCTOR ROUTES ====================

@app.route('/doctor/dashboard')
def doctor_dashboard():
    """Doctor dashboard"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor = Doctor.query.filter_by(user_id=current_user.id).first()

    # Get today's appointments
    today = date.today()
    today_appointments = Appointment.query.filter_by(
        doctor_id=doctor.id,
        appointment_date=today
    ).order_by(Appointment.appointment_time).all()

    # Get upcoming appointments
    week_later = today + timedelta(days=7)
    upcoming_appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date > today,
        Appointment.appointment_date <= week_later,
        Appointment.status == 'Booked'
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).all()

    # Get unique patients
    patient_ids = db.session.query(Appointment.patient_id).filter_by(doctor_id=doctor.id).distinct().all()
    total_patients = len(patient_ids)

    return render_template('doctor_dashboard.html',
                         doctor=doctor,
                         today_appointments=today_appointments,
                         upcoming_appointments=upcoming_appointments,
                         total_patients=total_patients)


@app.route('/doctor/appointments')
def doctor_appointments():
    """View all doctor appointments"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    appointments = Appointment.query.filter_by(doctor_id=doctor.id).order_by(Appointment.appointment_date.desc()).all()
    
    return render_template('doctor_appointments.html', appointments=appointments)


@app.route('/doctor/patients')
def doctor_patients():
    """View doctor's patients"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    patient_ids = db.session.query(Appointment.patient_id).filter_by(doctor_id=doctor.id).distinct().all()
    patients = Patient.query.filter(Patient.id.in_([p_id for p_id, in patient_ids])).all()

    return render_template('doctor_patients.html', patients=patients)


@app.route('/doctor/availability', methods=['GET', 'POST'])
def doctor_availability():
    """Manage doctor availability"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor = Doctor.query.filter_by(user_id=current_user.id).first()

    if request.method == 'POST':
        check_date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        start_time = datetime.strptime(request.form.get('start_time'), '%H:%M').time()
        end_time = datetime.strptime(request.form.get('end_time'), '%H:%M').time()
        total_seats = int(request.form.get('total_seats'))

        availability = DoctorAvailability(
            doctor_id=doctor.id,
            date=check_date,
            start_time=start_time,
            end_time=end_time,
            total_seats=total_seats
        )
        db.session.add(availability)
        db.session.commit()
        flash('Availability added successfully!', 'success')
        return redirect(url_for('doctor_availability'))

    availabilities = DoctorAvailability.query.filter_by(doctor_id=doctor.id).order_by(DoctorAvailability.date.desc()).all()
    return render_template('doctor_availability.html', doctor=doctor, availabilities=availabilities)


@app.route('/doctor/availability/delete/<int:availability_id>')
def doctor_delete_availability(availability_id):
    """Delete doctor availability"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    availability = DoctorAvailability.query.get_or_404(availability_id)
    
    if availability.doctor_id != doctor.id:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('doctor_availability'))

    db.session.delete(availability)
    db.session.commit()
    flash('Availability deleted successfully!', 'success')
    return redirect(url_for('doctor_availability'))


@app.route('/doctor/profile', methods=['GET', 'POST'])
def doctor_profile():
    """Manage doctor profile"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    user = doctor.user

    if request.method == 'POST':
        user.full_name = request.form.get('full_name')
        user.email = request.form.get('email')
        user.phone = request.form.get('phone')
        doctor.qualification = request.form.get('qualification')
        doctor.experience_years = int(request.form.get('experience_years', 0))

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('doctor_profile'))

    return render_template('doctor_profile.html', doctor=doctor)


@app.route('/doctor/appointment/complete/<int:appointment_id>')
def doctor_complete_appointment(appointment_id):
    """Mark appointment as completed"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    appointment = Appointment.query.get_or_404(appointment_id)

    if appointment.doctor_id != doctor.id:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('doctor_dashboard'))

    if appointment.status == 'Booked':
        appointment.status = 'Completed'
        db.session.commit()
        flash('Appointment marked as completed.', 'success')
    else:
        flash('This appointment cannot be marked as completed.', 'danger')

    return redirect(request.referrer or url_for('doctor_dashboard'))


@app.route('/doctor/appointment/treatment/<int:appointment_id>', methods=['GET', 'POST'])
def doctor_add_treatment(appointment_id):
    """Add or edit treatment for appointment"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    appointment = Appointment.query.get_or_404(appointment_id)

    if appointment.doctor_id != doctor.id:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('doctor_dashboard'))

    if request.method == 'POST':
        diagnosis = request.form.get('diagnosis')
        prescription = request.form.get('prescription')
        notes = request.form.get('notes')
        follow_up_required = 'follow_up_required' in request.form
        follow_up_date_str = request.form.get('follow_up_date')

        follow_up_date = None
        if follow_up_required and follow_up_date_str:
            follow_up_date = datetime.strptime(follow_up_date_str, '%Y-%m-%d').date()

        treatment = appointment.treatment
        if not treatment:
            treatment = Treatment(appointment_id=appointment.id)
            db.session.add(treatment)

        treatment.diagnosis = diagnosis
        treatment.prescription = prescription
        treatment.notes = notes
        treatment.follow_up_required = follow_up_required
        treatment.follow_up_date = follow_up_date

        appointment.status = 'Completed'

        db.session.commit()
        flash('Treatment details saved successfully!', 'success')
        return redirect(url_for('doctor_appointments'))

    return render_template('doctor_add_treatment.html', appointment=appointment)


@app.route('/doctor/appointment/view/<int:appointment_id>')
def doctor_view_appointment(appointment_id):
    """View appointment and treatment details"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    appointment = Appointment.query.get_or_404(appointment_id)

    if appointment.doctor_id != doctor.id:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('doctor_dashboard'))

    return render_template('doctor_view_appointment.html', appointment=appointment)


@app.route('/doctor/patient/history/<int:patient_id>')
def doctor_patient_history(patient_id):
    """View patient medical history with this doctor"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    patient = Patient.query.get_or_404(patient_id)

    appointments = Appointment.query.filter_by(
        patient_id=patient_id,
        doctor_id=doctor.id
    ).order_by(Appointment.appointment_date.desc()).all()

    return render_template('doctor_patient_history.html', patient=patient, appointments=appointments)


if __name__ == '__main__':
    init_db(app)
    app.run(debug=True)
 
