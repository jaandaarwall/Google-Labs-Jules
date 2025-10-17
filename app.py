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

# Make datetime available in templates
app.jinja_env.globals.update(datetime=datetime, timedelta=timedelta)

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


# ==================== ADMIN ROUTES ====================

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
        if Doctor.query.filter_by(username=username).first():
            flash('Username already exists!', 'danger')
            return redirect(url_for('admin_add_doctor'))

        if Doctor.query.filter_by(email=email).first():
            flash('Email already exists!', 'danger')
            return redirect(url_for('admin_add_doctor'))

        # Create new doctor
        doctor = Doctor(
            username=username,
            email=email,
            full_name=full_name,
            phone=phone,
            department_id=department_id,
            qualification=qualification,
            experience_years=int(experience_years) if experience_years else 0
        )
        doctor.set_password(password)

        db.session.add(doctor)
        db.session.commit()

        flash(f'Doctor {full_name} added successfully!', 'success')
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

    if request.method == 'POST':
        doctor.full_name = request.form.get('full_name')
        doctor.email = request.form.get('email')
        doctor.phone = request.form.get('phone')
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
    db.session.commit()

    status = 'activated' if doctor.is_active else 'deactivated'
    flash(f'Doctor {doctor.full_name} has been {status}!', 'success')
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
    patient.is_active = not patient.is_active
    db.session.commit()

    status = 'activated' if patient.is_active else 'deactivated'
    flash(f'Patient {patient.full_name} has been {status}!', 'success')
    return redirect(url_for('admin_patients'))


@app.route('/admin/patient/view/<int:patient_id>')
def admin_view_patient(patient_id):
    """View patient details and their appointment history"""
    if session.get('user_role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    patient = Patient.query.get_or_404(patient_id)
    appointments = Appointment.query.filter_by(patient_id=patient.id).order_by(Appointment.appointment_date.desc()).all()

    return render_template('admin_view_patient.html', patient=patient, appointments=appointments)


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
            # Search doctors
            doctors = Doctor.query.filter(
                db.or_(
                    Doctor.full_name.ilike(f'%{search_query}%'),
                    Doctor.email.ilike(f'%{search_query}%')
                )
            ).all()

            # Search patients
            patients = Patient.query.filter(
                db.or_(
                    Patient.full_name.ilike(f'%{search_query}%'),
                    Patient.email.ilike(f'%{search_query}%'),
                    Patient.phone.ilike(f'%{search_query}%')
                )
            ).all()

    return render_template('admin_search.html', doctors=doctors, patients=patients, search_query=search_query)


# ==================== PATIENT ROUTES ====================

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


@app.route('/patient/book/<int:doctor_id>', methods=['GET', 'POST'])
def patient_book_appointment(doctor_id):
    """Book appointment with doctor"""
    if session.get('user_role') != 'patient':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor = Doctor.query.get_or_404(doctor_id)
    patient_id = session.get('user_id')

    if request.method == 'POST':
        appointment_date = datetime.strptime(request.form.get('appointment_date'), '%Y-%m-%d').date()
        appointment_time = datetime.strptime(request.form.get('appointment_time'), '%H:%M').time()
        reason = request.form.get('reason')

        # Check if slot is available
        existing = Appointment.query.filter_by(
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            appointment_time=appointment_time
        ).first()

        if existing:
            flash('This time slot is already booked! Please choose another time.', 'danger')
            return redirect(url_for('patient_book_appointment', doctor_id=doctor_id))

        # Create appointment
        appointment = Appointment(
            patient_id=patient_id,
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

    patient_id = session.get('user_id')
    appointments = Appointment.query.filter_by(patient_id=patient_id).order_by(Appointment.appointment_date.desc()).all()

    return render_template('patient_appointments.html', appointments=appointments)


@app.route('/patient/cancel/<int:appointment_id>')
def patient_cancel_appointment(appointment_id):
    """Cancel appointment"""
    if session.get('user_role') != 'patient':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    appointment = Appointment.query.get_or_404(appointment_id)

    # Verify it's the patient's appointment
    if appointment.patient_id != session.get('user_id'):
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
    """View patient's full medical history"""
    if session.get('user_role') != 'patient':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    patient_id = session.get('user_id')
    appointments = Appointment.query.filter_by(patient_id=patient_id, status='Completed').order_by(Appointment.appointment_date.desc()).all()
    return render_template('patient_medical_history.html', appointments=appointments)


@app.route('/patient/profile', methods=['GET', 'POST'])
def patient_profile():
    """Manage patient's profile"""
    if session.get('user_role') != 'patient':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    patient_id = session.get('user_id')
    patient = Patient.query.get_or_404(patient_id)

    if request.method == 'POST':
        patient.full_name = request.form.get('full_name')
        patient.email = request.form.get('email')
        patient.phone = request.form.get('phone')
        dob_str = request.form.get('date_of_birth')
        if dob_str:
            patient.date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date()
        patient.gender = request.form.get('gender')
        patient.address = request.form.get('address')
        patient.blood_group = request.form.get('blood_group')

        db.session.commit()
        session['user_name'] = patient.full_name # Update session
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('patient_profile'))

    return render_template('patient_profile.html', patient=patient)


# ==================== DOCTOR ROUTES ====================

@app.route('/doctor/appointments')
def doctor_appointments():
    """View all doctor's appointments"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor_id = session.get('user_id')
    appointments = Appointment.query.filter_by(doctor_id=doctor_id).order_by(Appointment.appointment_date.desc()).all()
    return render_template('doctor_appointments.html', appointments=appointments)


@app.route('/doctor/patients')
def doctor_patients():
    """View doctor's patients"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor_id = session.get('user_id')
    patient_ids = db.session.query(Appointment.patient_id).filter_by(doctor_id=doctor_id).distinct().all()
    patients = Patient.query.filter(Patient.id.in_([p_id for p_id, in patient_ids])).all()

    return render_template('doctor_patients.html', patients=patients)


@app.route('/doctor/availability', methods=['GET', 'POST'])
def doctor_availability():
    """Manage doctor's availability"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor_id = session.get('user_id')
    doctor = Doctor.query.get_or_404(doctor_id)

    if request.method == 'POST':
        # NOTE: This is a placeholder for a more complex feature.
        # For now, it just demonstrates the form submission.
        flash('Availability settings updated (demo)!', 'info')
        return redirect(url_for('doctor_availability'))

    availabilities = DoctorAvailability.query.filter_by(doctor_id=doctor_id).order_by(DoctorAvailability.date.desc()).all()
    return render_template('doctor_availability.html', doctor=doctor, availabilities=availabilities)


@app.route('/doctor/profile', methods=['GET', 'POST'])
def doctor_profile():
    """Manage doctor's profile"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    doctor_id = session.get('user_id')
    doctor = Doctor.query.get_or_404(doctor_id)

    if request.method == 'POST':
        doctor.full_name = request.form.get('full_name')
        doctor.email = request.form.get('email')
        doctor.phone = request.form.get('phone')
        doctor.qualification = request.form.get('qualification')
        doctor.experience_years = int(request.form.get('experience_years', 0))

        db.session.commit()
        session['user_name'] = doctor.full_name # Update session name
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('doctor_profile'))

    return render_template('doctor_profile.html', doctor=doctor)


@app.route('/doctor/appointment/complete/<int:appointment_id>')
def doctor_complete_appointment(appointment_id):
    """Mark an appointment as completed"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    appointment = Appointment.query.get_or_404(appointment_id)

    if appointment.doctor_id != session.get('user_id'):
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
    """Add or edit treatment for an appointment"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    appointment = Appointment.query.get_or_404(appointment_id)

    if appointment.doctor_id != session.get('user_id'):
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

    appointment = Appointment.query.get_or_404(appointment_id)

    if appointment.doctor_id != session.get('user_id'):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('doctor_dashboard'))

    return render_template('doctor_view_appointment.html', appointment=appointment)


@app.route('/doctor/patient/history/<int:patient_id>')
def doctor_patient_history(patient_id):
    """View patient's medical history with this doctor"""
    if session.get('user_role') != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    patient = Patient.query.get_or_404(patient_id)

    appointments = Appointment.query.filter_by(
        patient_id=patient_id,
        doctor_id=session.get('user_id')
    ).order_by(Appointment.appointment_date.desc()).all()

    return render_template('doctor_patient_history.html', patient=patient, appointments=appointments)


if __name__ == '__main__':
    # Initialize database on first run
    if not os.path.exists('hospital.db'):
        init_database()

    app.run(debug=True)