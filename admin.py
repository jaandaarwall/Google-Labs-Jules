from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from models import db, User, Role, Doctor, Patient, Department, Appointment, Payment
from datetime import date
from sqlalchemy import or_

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.before_request
def check_admin():
    if session.get('user_role') != 'admin':
        return redirect(url_for('common.login'))

# ... [Keep dashboard, doctors, add_doctor, edit_doctor routes same as before] ...

@admin_bp.route('/dashboard')
def admin_dashboard():
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

@admin_bp.route('/doctors')
def admin_doctors():
    doctors = Doctor.query.all() 
    return render_template('admin_doctors.html', doctors=doctors)

@admin_bp.route('/doctor/add', methods=['GET', 'POST'])
def admin_add_doctor():
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
            return redirect(url_for('admin.admin_add_doctor'))
        if User.query.filter_by(email=email).first():
            flash('Email already exists!', 'danger')
            return redirect(url_for('admin.admin_add_doctor'))

        new_user = User(username=username, email=email, full_name=full_name, phone=phone)
        new_user.set_password(password)
        
        doctor_role = Role.query.filter_by(name='doctor').first()
        if doctor_role: new_user.roles.append(doctor_role)
        patient_role = Role.query.filter_by(name='patient').first()
        if patient_role: new_user.roles.append(patient_role)

        db.session.add(new_user)
        db.session.flush()

        new_doctor = Doctor(
            user_id=new_user.id,
            department_id=department_id,
            qualification=qualification,
            experience_years=int(experience_years) if experience_years else 0
        )
        db.session.add(new_doctor)
        new_patient = Patient(user_id=new_user.id, address="N/A", blood_group="N/A")
        db.session.add(new_patient)

        db.session.commit()
        flash(f'Doctor {full_name} added successfully!', 'success')
        return redirect(url_for('admin.admin_doctors'))
    departments = Department.query.all()
    return render_template('admin_add_doctor.html', departments=departments)

@admin_bp.route('/doctor/edit/<int:doctor_id>', methods=['GET', 'POST'])
def admin_edit_doctor(doctor_id):
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
        return redirect(url_for('admin.admin_doctors'))

    departments = Department.query.all()
    return render_template('admin_edit_doctor.html', doctor=doctor, departments=departments)

# --- MODIFIED TOGGLE ROUTES ---

@admin_bp.route('/doctor/toggle/<int:doctor_id>')
def admin_toggle_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    new_status = not doctor.user.is_active
    doctor.user.is_active = new_status
    
    msg_extra = ""
    if not new_status: # If deactivating
        # Cancel all future appointments
        future_appointments = Appointment.query.filter(
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date >= date.today(),
            Appointment.status.in_(['Booked', 'Pending Payment'])
        ).all()
        
        count = 0
        for appt in future_appointments:
            appt.status = 'Cancelled'
            # Refund Payment
            payment = Payment.query.filter_by(appointment_id=appt.id).first()
            if payment and payment.status == 'Success':
                payment.status = 'Refunded'
            count += 1
        
        msg_extra = f" {count} future appointments cancelled and refunded."

    db.session.commit()
    status_str = 'activated' if new_status else 'deactivated'
    flash(f'Doctor {doctor.user.full_name} has been {status_str}.{msg_extra}', 'success')
    return redirect(url_for('admin.admin_doctors'))

@admin_bp.route('/patients')
def admin_patients():
    patients = Patient.query.all()
    return render_template('admin_patients.html', patients=patients)

@admin_bp.route('/patient/toggle/<int:patient_id>')
def admin_toggle_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    new_status = not patient.user.is_active
    patient.user.is_active = new_status
    
    msg_extra = ""
    if not new_status: # If deactivating
        # Cancel all future appointments
        future_appointments = Appointment.query.filter(
            Appointment.patient_id == patient.id,
            Appointment.appointment_date >= date.today(),
            Appointment.status.in_(['Booked', 'Pending Payment'])
        ).all()
        
        count = 0
        for appt in future_appointments:
            appt.status = 'Cancelled'
            payment = Payment.query.filter_by(appointment_id=appt.id).first()
            if payment and payment.status == 'Success':
                payment.status = 'Refunded'
            count += 1
            
        msg_extra = f" {count} future appointments cancelled and refunded."

    db.session.commit()
    status_str = 'activated' if new_status else 'deactivated'
    flash(f'Patient {patient.user.full_name} has been {status_str}.{msg_extra}', 'success')
    return redirect(url_for('admin.admin_patients'))

# ... [Keep remaining routes: view_patient, view_doctor, appointments, search, departments] ...

@admin_bp.route('/patient/view/<int:patient_id>')
def admin_view_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    appointments = Appointment.query.filter_by(patient_id=patient.id).order_by(Appointment.appointment_date.desc()).all()
    return render_template('admin_view_patient.html', patient=patient, appointments=appointments)

@admin_bp.route('/doctor/view/<int:doctor_id>')
def admin_view_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    appointments = Appointment.query.filter_by(doctor_id=doctor.id).order_by(Appointment.appointment_date.desc()).all()
    return render_template('admin_view_doctor.html', doctor=doctor, appointments=appointments)

@admin_bp.route('/appointments')
def admin_appointments():
    appointments = Appointment.query.order_by(Appointment.appointment_date.desc()).all()
    return render_template('admin_appointments.html', appointments=appointments)

@admin_bp.route('/appointment/view/<int:appointment_id>')
def admin_view_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    return render_template('admin_view_appointment.html', appointment=appointment)

@admin_bp.route('/search', methods=['GET', 'POST'])
def admin_search():
    doctors = []
    patients = []
    search_query = ''

    if request.method == 'POST':
        search_query = request.form.get('search_query', '').strip()
        if search_query:
            doctors = Doctor.query.join(User).filter(
                or_(User.full_name.ilike(f'%{search_query}%'), User.email.ilike(f'%{search_query}%'))
            ).all()
            patients = Patient.query.join(User).filter(
                or_(User.full_name.ilike(f'%{search_query}%'), User.email.ilike(f'%{search_query}%'), User.phone.ilike(f'%{search_query}%'))
            ).all()

    return render_template('admin_search.html', doctors=doctors, patients=patients, search_query=search_query)

@admin_bp.route('/departments')
def admin_departments():
    departments = Department.query.all()
    return render_template('admin_departments.html', departments=departments)

@admin_bp.route('/department/add', methods=['GET', 'POST'])
def admin_add_department():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')

        if Department.query.filter_by(name=name).first():
            flash('Department already exists!', 'danger')
            return redirect(url_for('admin.admin_add_department'))
        
        try:
            new_dept = Department(name=name, description=description, price=float(price) if price else 0.0)
            db.session.add(new_dept)
            db.session.commit()
            flash('Department added successfully!', 'success')
            return redirect(url_for('admin.admin_departments'))
        except ValueError:
            flash('Invalid price format.', 'danger')
    
    return render_template('admin_add_department.html')

@admin_bp.route('/department/edit/<int:id>', methods=['GET', 'POST'])
def admin_edit_department(id):
    department = Department.query.get_or_404(id)

    if request.method == 'POST':
        department.name = request.form.get('name')
        department.description = request.form.get('description')
        try:
            department.price = float(request.form.get('price'))
            db.session.commit()
            flash('Department updated successfully!', 'success')
            return redirect(url_for('admin.admin_departments'))
        except ValueError:
            flash('Invalid price format.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash('Error updating department.', 'danger')
            
    return render_template('admin_edit_department.html', department=department)

@admin_bp.route('/department/delete/<int:id>')
def admin_delete_department(id):
    department = Department.query.get_or_404(id)
    if department.doctors:
        flash(f'Cannot delete {department.name}. It has {len(department.doctors)} doctor(s) assigned.', 'danger')
        return redirect(url_for('admin.admin_departments'))
    db.session.delete(department)
    db.session.commit()
    flash('Department deleted successfully!', 'success')
    return redirect(url_for('admin.admin_departments'))