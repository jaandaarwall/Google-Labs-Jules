from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify
from models import db, User, Role, Doctor, Patient, Department, Appointment, Treatment, DoctorAvailability, Payment
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
    """Initialize database, create roles, and default admin with ALL profiles"""
    with app.app_context():
        db.create_all()

        # 1. Create Roles programmatically
        print("⚡ Initializing Roles...")
        admin_role = user_datastore.find_or_create_role(name='admin', description='Administrator')
        doctor_role = user_datastore.find_or_create_role(name='doctor', description='Doctor')
        patient_role = user_datastore.find_or_create_role(name='patient', description='Patient')

        # 2. Create Departments FIRST (needed for Doctor profile)
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

        # 3. Create Admin User
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
            
            # Assign ALL roles
            admin_user.roles.append(admin_role)
            admin_user.roles.append(doctor_role)
            admin_user.roles.append(patient_role)
            
            db.session.add(admin_user)
            db.session.flush() # Flush to get the ID

            # 4. Create Dummy Doctor Profile for Admin (Required to login as Doctor)
            # Assign to the first available department
            first_dept = Department.query.first()
            admin_doctor = Doctor(
                user_id=admin_user.id,
                department_id=first_dept.id if first_dept else 1,
                qualification="Super User",
                experience_years=10
            )
            db.session.add(admin_doctor)

            # 5. Create Dummy Patient Profile for Admin (Required to login as Patient)
            admin_patient = Patient(
                user_id=admin_user.id,
                date_of_birth=date(1990, 1, 1),
                gender="Other",
                address="Server Room",
                blood_group="O+"
            )
            db.session.add(admin_patient)

            db.session.commit()
            print("✅ Database initialized successfully!")
            print("📝 Default Admin Credentials: admin / admin123")
        else:
            print("ℹ️  Database already initialized.")


@app.route('/')
def index():
    """Landing page"""
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Unified login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        requested_role = request.form.get('role')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated.', 'warning')
                return redirect(url_for('login'))

            # Check permissions
            if not user.has_role(requested_role) and requested_role != 'admin': 
                flash(f'Access denied. You do not have {requested_role} privileges.', 'danger')
                return redirect(url_for('login'))
            
            session['user_id'] = user.id 
            session['user_name'] = user.full_name
            session['user_role'] = requested_role

            flash('Login successful!', 'success')

            if requested_role == 'admin':
                if user.has_role('admin'): return redirect(url_for('admin_dashboard'))
            elif requested_role == 'doctor':
                if user.has_role('doctor'): return redirect(url_for('doctor_dashboard'))
            elif requested_role == 'patient':
                if user.has_role('patient'): return redirect(url_for('patient_dashboard'))
            
            flash('Role mismatch or unauthorized.', 'danger')
            return redirect(url_for('login'))

        else:
            flash('Invalid credentials!', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout user"""
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

        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))

        new_user = User(username=username, email=email, full_name=full_name, phone=phone)
        new_user.set_password(password)
        
        patient_role = Role.query.filter_by(name='patient').first()
        if patient_role:
            new_user.roles.append(patient_role)
        
        db.session.add(new_user)
        db.session.flush()

        new_patient = Patient(
            user_id=new_user.id,
            date_of_birth=datetime.strptime(dob, '%Y-%m-%d').date() if dob else None,
            gender=gender,
            address=address,
            blood_group=blood_group
        )
        
        db.session.add(new_patient)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# ==================== ADMIN ROUTES ====================

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    total_doctors = Doctor.query.join(User).filter(User.is_active==True).count()
    total_patients = Patient.query.join(User).filter(User.is_active==True).count()
    total_appointments = Appointment.query.count()
    today_appointments = Appointment.query.filter_by(appointment_date=date.today()).count()
    recent_appointments = Appointment.query.order_by(Appointment.created_at.desc()).limit(5).all()
    return render_template('admin_dashboard.html',
                         total_doctors=total_doctors,
                         total_patients=total_patients,
                         total_appointments=total_appointments,
                         today_appointments=today_appointments,
                         recent_appointments=recent_appointments)

@app.route('/admin/doctors')
def admin_doctors():
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    doctors = Doctor.query.all() 
    return render_template('admin_doctors.html', doctors=doctors)

@app.route('/admin/doctor/add', methods=['GET', 'POST'])
def admin_add_doctor():
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        department_id = request.form.get('department_id')
        qualification = request.form.get('qualification')
        experience_years = request.form.get('experience_years')

        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'danger')
            return redirect(url_for('admin_add_doctor'))
        if User.query.filter_by(email=email).first():
            flash('Email already exists!', 'danger')
            return redirect(url_for('admin_add_doctor'))

        new_user = User(username=username, email=email, full_name=full_name, phone=phone)
        new_user.set_password(password)
        doctor_role = Role.query.filter_by(name='doctor').first()
        if doctor_role: new_user.roles.append(doctor_role)

        db.session.add(new_user)
        db.session.flush()

        new_doctor = Doctor(
            user_id=new_user.id,
            department_id=department_id,
            qualification=qualification,
            experience_years=int(experience_years) if experience_years else 0
        )

        db.session.add(new_doctor)
        db.session.commit()
        flash(f'Doctor {full_name} added successfully!', 'success')
        return redirect(url_for('admin_doctors'))
    departments = Department.query.all()
    return render_template('admin_add_doctor.html', departments=departments)

@app.route('/admin/doctor/edit/<int:doctor_id>', methods=['GET', 'POST'])
def admin_edit_doctor(doctor_id):
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    
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
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    doctor = Doctor.query.get_or_404(doctor_id)
    doctor.user.is_active = not doctor.user.is_active 
    db.session.commit()
    
    status = 'activated' if doctor.user.is_active else 'deactivated'
    flash(f'Doctor {doctor.user.full_name} has been {status}!', 'success')
    return redirect(url_for('admin_doctors'))

@app.route('/admin/patients')
def admin_patients():
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    patients = Patient.query.all()
    return render_template('admin_patients.html', patients=patients)

@app.route('/admin/patient/toggle/<int:patient_id>')
def admin_toggle_patient(patient_id):
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    patient = Patient.query.get_or_404(patient_id)
    patient.user.is_active = not patient.user.is_active 
    db.session.commit()
    
    status = 'activated' if patient.user.is_active else 'deactivated'
    flash(f'Patient {patient.user.full_name} has been {status}!', 'success')
    return redirect(url_for('admin_patients'))

@app.route('/admin/patient/view/<int:patient_id>')
def admin_view_patient(patient_id):
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    patient = Patient.query.get_or_404(patient_id)
    appointments = Appointment.query.filter_by(patient_id=patient.id).order_by(Appointment.appointment_date.desc()).all()
    return render_template('admin_view_patient.html', patient=patient, appointments=appointments)

@app.route('/admin/doctor/view/<int:doctor_id>')
def admin_view_doctor(doctor_id):
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    doctor = Doctor.query.get_or_404(doctor_id)
    appointments = Appointment.query.filter_by(doctor_id=doctor.id).order_by(Appointment.appointment_date.desc()).all()
    return render_template('admin_view_doctor.html', doctor=doctor, appointments=appointments)

@app.route('/admin/appointments')
def admin_appointments():
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    appointments = Appointment.query.order_by(Appointment.appointment_date.desc()).all()
    return render_template('admin_appointments.html', appointments=appointments)

@app.route('/admin/appointment/view/<int:appointment_id>')
def admin_view_appointment(appointment_id):
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    appointment = Appointment.query.get_or_404(appointment_id)
    return render_template('admin_view_appointment.html', appointment=appointment)

@app.route('/admin/search', methods=['GET', 'POST'])
def admin_search():
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    doctors = []
    patients = []
    search_query = ''

    if request.method == 'POST':
        search_query = request.form.get('search_query', '').strip()
        if search_query:
            doctors = Doctor.query.join(User).filter(
                db.or_(User.full_name.ilike(f'%{search_query}%'), User.email.ilike(f'%{search_query}%'))
            ).all()
            patients = Patient.query.join(User).filter(
                db.or_(User.full_name.ilike(f'%{search_query}%'), User.email.ilike(f'%{search_query}%'), User.phone.ilike(f'%{search_query}%'))
            ).all()

    return render_template('admin_search.html', doctors=doctors, patients=patients, search_query=search_query)

# ==================== DEPARTMENT MANAGEMENT ====================

@app.route('/admin/departments')
def admin_departments():
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    departments = Department.query.all()
    return render_template('admin_departments.html', departments=departments)

@app.route('/admin/department/add', methods=['GET', 'POST'])
def admin_add_department():
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')

        if Department.query.filter_by(name=name).first():
            flash('Department already exists!', 'danger')
            return redirect(url_for('admin_add_department'))
        
        try:
            new_dept = Department(
                name=name, 
                description=description, 
                price=float(price) if price else 0.0
            )
            db.session.add(new_dept)
            db.session.commit()
            flash('Department added successfully!', 'success')
            return redirect(url_for('admin_departments'))
        except ValueError:
            flash('Invalid price format.', 'danger')
    
    return render_template('admin_add_department.html')

@app.route('/admin/department/edit/<int:id>', methods=['GET', 'POST'])
def admin_edit_department(id):
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    department = Department.query.get_or_404(id)

    if request.method == 'POST':
        department.name = request.form.get('name')
        department.description = request.form.get('description')
        try:
            department.price = float(request.form.get('price'))
            db.session.commit()
            flash('Department updated successfully!', 'success')
            return redirect(url_for('admin_departments'))
        except ValueError:
            flash('Invalid price format.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash('Error updating department. Name might be duplicate.', 'danger')
            
    return render_template('admin_edit_department.html', department=department)

@app.route('/admin/department/delete/<int:id>')
def admin_delete_department(id):
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    department = Department.query.get_or_404(id)
    
    # Prevent deletion if doctors are assigned
    if department.doctors:
        flash(f'Cannot delete {department.name}. It has {len(department.doctors)} doctor(s) assigned. Please reassign or remove them first.', 'danger')
        return redirect(url_for('admin_departments'))
        
    db.session.delete(department)
    db.session.commit()
    flash('Department deleted successfully!', 'success')
    return redirect(url_for('admin_departments'))


# ==================== PATIENT ROUTES ====================

@app.route('/patient/dashboard')
def patient_dashboard():
    if session.get('user_role') != 'patient': return redirect(url_for('login'))
    user_id = session.get('user_id')
    patient = Patient.query.filter_by(user_id=user_id).first()
    if not patient:
        flash('Patient profile not found.', 'danger')
        return redirect(url_for('login'))
    departments = Department.query.all()
    upcoming_appointments = Appointment.query.filter(
        Appointment.patient_id == patient.id,
        Appointment.appointment_date >= date.today(),
        Appointment.status == 'Booked'
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).all()
    past_appointments = Appointment.query.filter(
        Appointment.patient_id == patient.id,
        Appointment.status == 'Completed'
    ).order_by(Appointment.appointment_date.desc()).limit(5).all()
    return render_template('patient_dashboard.html', patient=patient, departments=departments, upcoming_appointments=upcoming_appointments, past_appointments=past_appointments)

@app.route('/patient/doctors')
def patient_find_doctors():
    if session.get('user_role') != 'patient': return redirect(url_for('login'))
    department_id = request.args.get('department_id', type=int)
    query = Doctor.query.join(User).filter(User.is_active==True)
    if department_id:
        doctors = query.filter(Doctor.department_id==department_id).all()
        department = Department.query.get(department_id)
    else:
        doctors = query.all()
        department = None
    departments = Department.query.all()
    return render_template('patient_find_doctors.html', doctors=doctors, departments=departments, selected_department=department)

@app.route('/api/doctor/<int:doctor_id>/availability', methods=['GET'])
def get_doctor_availability(doctor_id):
    date_str = request.args.get('date')
    if not date_str: return jsonify({'error': 'Date parameter is required'}), 400
    try: check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError: return jsonify({'error': 'Invalid date format.'}), 400
    availabilities = DoctorAvailability.query.filter_by(doctor_id=doctor_id, date=check_date, is_available=True).all()
    slots = []
    for av in availabilities:
        start_time = datetime.combine(check_date, av.start_time)
        end_time = datetime.combine(check_date, av.end_time)
        while start_time < end_time:
            booked_count = Appointment.query.filter_by(
                doctor_id=doctor_id, appointment_date=check_date, appointment_time=start_time.time()
            ).count()
            if booked_count < av.total_seats:
                slots.append({'time': start_time.strftime('%H:%M')})
            start_time += timedelta(minutes=30)
    return jsonify(slots)

@app.route('/patient/book/<int:doctor_id>', methods=['GET', 'POST'])
def patient_book_appointment(doctor_id):
    if session.get('user_role') != 'patient': return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    patient = Patient.query.filter_by(user_id=user_id).first()
    doctor = Doctor.query.get_or_404(doctor_id)
    
    # Calculate Fee
    consultation_fee = doctor.department.price if doctor.department else 500.0

    if request.method == 'POST':
        appointment_date = datetime.strptime(request.form.get('appointment_date'), '%Y-%m-%d').date()
        appointment_time = datetime.strptime(request.form.get('appointment_time'), '%H:%M').time()
        reason = request.form.get('reason')
        
        availability = DoctorAvailability.query.filter(
            DoctorAvailability.doctor_id == doctor_id,
            DoctorAvailability.date == appointment_date,
            DoctorAvailability.start_time <= appointment_time,
            DoctorAvailability.end_time > appointment_time,
            DoctorAvailability.is_available == True
        ).first()

        if not availability:
            flash('Slot not available.', 'danger')
            return redirect(url_for('patient_book_appointment', doctor_id=doctor_id))

        booked_count = Appointment.query.filter_by(
            doctor_id=doctor_id, appointment_date=appointment_date, appointment_time=appointment_time
        ).count()

        if booked_count >= availability.total_seats:
            flash('Fully booked.', 'danger')
            return redirect(url_for('patient_book_appointment', doctor_id=doctor_id))

        # 1. Create Appointment with 'Pending Payment' status
        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            reason=reason,
            status='Pending Payment'  # Changed status
        )
        db.session.add(appointment)
        db.session.flush()

        # 2. Create Payment Record with 'Pending' status
        payment = Payment(
            appointment_id=appointment.id,
            amount=consultation_fee,
            status='Pending' # Changed status
        )
        db.session.add(payment)

        db.session.commit()
        # 3. Redirect to Payment Page
        return redirect(url_for('patient_pay', appointment_id=appointment.id))

    return render_template('patient_book_appointment.html', doctor=doctor, fee=consultation_fee)

@app.route('/patient/pay/<int:appointment_id>', methods=['GET', 'POST'])
def patient_pay(appointment_id):
    if session.get('user_role') != 'patient': return redirect(url_for('login'))
    
    appointment = Appointment.query.get_or_404(appointment_id)
    
    # Security check: Ensure appointment belongs to current user
    user_id = session.get('user_id')
    patient = Patient.query.filter_by(user_id=user_id).first()
    if appointment.patient_id != patient.id:
        flash('Unauthorized access to this payment.', 'danger')
        return redirect(url_for('patient_dashboard'))

    # Get the payment record for this appointment
    payment = Payment.query.filter_by(appointment_id=appointment.id).first()
    
    if request.method == 'POST':
        # Simulate payment processing
        payment.status = 'Success'
        payment.payment_date = datetime.utcnow()
        appointment.status = 'Booked' # Update appointment status to Booked
        
        db.session.commit()
        
        flash('Payment successful! Appointment confirmed.', 'success')
        return redirect(url_for('patient_dashboard'))

    return render_template('patient_payment.html', appointment=appointment, payment=payment)


@app.route('/patient/appointments')
def patient_appointments():
    if session.get('user_role') != 'patient': return redirect(url_for('login'))
    user_id = session.get('user_id')
    patient = Patient.query.filter_by(user_id=user_id).first()
    appointments = Appointment.query.filter_by(patient_id=patient.id).order_by(Appointment.appointment_date.desc()).all()
    return render_template('patient_appointments.html', appointments=appointments)

@app.route('/patient/cancel/<int:appointment_id>')
def patient_cancel_appointment(appointment_id):
    if session.get('user_role') != 'patient': return redirect(url_for('login'))
    user_id = session.get('user_id')
    patient = Patient.query.filter_by(user_id=user_id).first()
    appointment = Appointment.query.get_or_404(appointment_id)

    if appointment.patient_id != patient.id:
        flash('Unauthorized!', 'danger')
        return redirect(url_for('patient_dashboard'))

    if appointment.status == 'Booked' or appointment.status == 'Pending Payment':
        appointment.status = 'Cancelled'
        db.session.commit()
        flash('Cancelled successfully.', 'success')
    else:
        flash('Cannot cancel this appointment.', 'danger')
    return redirect(url_for('patient_appointments'))

@app.route('/patient/history')
def patient_medical_history():
    if session.get('user_role') != 'patient': return redirect(url_for('login'))
    user_id = session.get('user_id')
    patient = Patient.query.filter_by(user_id=user_id).first()
    appointments = Appointment.query.filter_by(patient_id=patient.id, status='Completed').order_by(Appointment.appointment_date.desc()).all()
    return render_template('patient_medical_history.html', appointments=appointments)

@app.route('/patient/profile', methods=['GET', 'POST'])
def patient_profile():
    if session.get('user_role') != 'patient': return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    patient = Patient.query.filter_by(user_id=user_id).first()

    if request.method == 'POST':
        patient.user.full_name = request.form.get('full_name')
        patient.user.email = request.form.get('email')
        patient.user.phone = request.form.get('phone')
        
        dob_str = request.form.get('date_of_birth')
        if dob_str: 
            patient.date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date()
        patient.gender = request.form.get('gender')
        patient.address = request.form.get('address')
        patient.blood_group = request.form.get('blood_group')

        db.session.commit()
        session['user_name'] = patient.user.full_name
        flash('Profile updated!', 'success')
        return redirect(url_for('patient_profile'))

    return render_template('patient_profile.html', patient=patient)

# ==================== DOCTOR ROUTES ====================

@app.route('/doctor/dashboard')
def doctor_dashboard():
    if session.get('user_role') != 'doctor': return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    if not doctor:
        flash('Doctor profile not found.', 'danger')
        return redirect(url_for('login'))

    today = date.today()
    today_appointments = Appointment.query.filter_by(
        doctor_id=doctor.id, appointment_date=today
    ).order_by(Appointment.appointment_time).all()

    week_later = today + timedelta(days=7)
    upcoming_appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date > today,
        Appointment.appointment_date <= week_later,
        Appointment.status == 'Booked'
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).all()

    patient_ids = db.session.query(Appointment.patient_id).filter_by(doctor_id=doctor.id).distinct().all()
    total_patients = len(patient_ids)

    return render_template('doctor_dashboard.html',
                         doctor=doctor,
                         today_appointments=today_appointments,
                         upcoming_appointments=upcoming_appointments,
                         total_patients=total_patients)

@app.route('/doctor/appointments')
def doctor_appointments():
    if session.get('user_role') != 'doctor': return redirect(url_for('login'))
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    appointments = Appointment.query.filter_by(doctor_id=doctor.id).order_by(Appointment.appointment_date.desc()).all()
    return render_template('doctor_appointments.html', appointments=appointments)

@app.route('/doctor/patients')
def doctor_patients():
    if session.get('user_role') != 'doctor': return redirect(url_for('login'))
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    patient_ids = db.session.query(Appointment.patient_id).filter_by(doctor_id=doctor.id).distinct().all()
    patients = Patient.query.filter(Patient.id.in_([p_id for p_id, in patient_ids])).all()
    return render_template('doctor_patients.html', patients=patients)

@app.route('/doctor/availability', methods=['GET', 'POST'])
def doctor_availability():
    if session.get('user_role') != 'doctor': return redirect(url_for('login'))
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()

    if request.method == 'POST':
        date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        start_time = datetime.strptime(request.form.get('start_time'), '%H:%M').time()
        end_time = datetime.strptime(request.form.get('end_time'), '%H:%M').time()
        total_seats = int(request.form.get('total_seats'))

        availability = DoctorAvailability(
            doctor_id=doctor.id,
            date=date,
            start_time=start_time,
            end_time=end_time,
            total_seats=total_seats
        )
        db.session.add(availability)
        db.session.commit()
        flash('Availability added!', 'success')
        return redirect(url_for('doctor_availability'))

    availabilities = DoctorAvailability.query.filter_by(doctor_id=doctor.id).order_by(DoctorAvailability.date.desc()).all()
    return render_template('doctor_availability.html', doctor=doctor, availabilities=availabilities)

@app.route('/doctor/availability/delete/<int:availability_id>')
def doctor_delete_availability(availability_id):
    if session.get('user_role') != 'doctor': return redirect(url_for('login'))
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    
    availability = DoctorAvailability.query.get_or_404(availability_id)
    if availability.doctor_id != doctor.id:
        flash('Unauthorized!', 'danger')
        return redirect(url_for('doctor_availability'))

    db.session.delete(availability)
    db.session.commit()
    flash('Deleted!', 'success')
    return redirect(url_for('doctor_availability'))

@app.route('/doctor/profile', methods=['GET', 'POST'])
def doctor_profile():
    if session.get('user_role') != 'doctor': return redirect(url_for('login'))
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()

    if request.method == 'POST':
        doctor.user.full_name = request.form.get('full_name')
        doctor.user.email = request.form.get('email')
        doctor.user.phone = request.form.get('phone')
        
        doctor.qualification = request.form.get('qualification')
        doctor.experience_years = int(request.form.get('experience_years', 0))

        db.session.commit()
        session['user_name'] = doctor.user.full_name
        flash('Profile updated!', 'success')
        return redirect(url_for('doctor_profile'))

    return render_template('doctor_profile.html', doctor=doctor)

@app.route('/doctor/appointment/complete/<int:appointment_id>')
def doctor_complete_appointment(appointment_id):
    if session.get('user_role') != 'doctor': return redirect(url_for('login'))
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.doctor_id != doctor.id:
        flash('Unauthorized!', 'danger')
        return redirect(url_for('doctor_dashboard'))
    if appointment.status == 'Booked':
        appointment.status = 'Completed'
        db.session.commit()
        flash('Marked as completed.', 'success')
    else:
        flash('Cannot mark as completed.', 'danger')
    return redirect(request.referrer or url_for('doctor_dashboard'))

@app.route('/doctor/appointment/treatment/<int:appointment_id>', methods=['GET', 'POST'])
def doctor_add_treatment(appointment_id):
    if session.get('user_role') != 'doctor': return redirect(url_for('login'))
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.doctor_id != doctor.id:
        flash('Unauthorized!', 'danger')
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
        flash('Treatment saved!', 'success')
        return redirect(url_for('doctor_appointments'))
    return render_template('doctor_add_treatment.html', appointment=appointment)

@app.route('/doctor/appointment/view/<int:appointment_id>')
def doctor_view_appointment(appointment_id):
    if session.get('user_role') != 'doctor': return redirect(url_for('login'))
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.doctor_id != doctor.id:
        flash('Unauthorized!', 'danger')
        return redirect(url_for('doctor_dashboard'))
    return render_template('doctor_view_appointment.html', appointment=appointment)

@app.route('/doctor/patient/history/<int:patient_id>')
def doctor_patient_history(patient_id):
    if session.get('user_role') != 'doctor': return redirect(url_for('login'))
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    patient = Patient.query.get_or_404(patient_id)
    appointments = Appointment.query.filter_by(patient_id=patient_id, doctor_id=doctor.id).order_by(Appointment.appointment_date.desc()).all()
    return render_template('doctor_patient_history.html', patient=patient, appointments=appointments)

if __name__ == '__main__':
    if not os.path.exists('hospital.db'):
        init_database()
    app.run(debug=True, port=8000)