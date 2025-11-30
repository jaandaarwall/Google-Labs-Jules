from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from models import db, User, Doctor, Patient, Department, Appointment, DoctorAvailability, Payment
from datetime import datetime, date, timedelta
from sqlalchemy.exc import IntegrityError

patient_bp = Blueprint('patient', __name__)

@patient_bp.before_request
def check_patient():
    if request.path.startswith('/api'):
        pass
    
    if session.get('user_role') != 'patient' and not request.path.startswith('/api'):
        return redirect(url_for('common.login'))

@patient_bp.route('/patient/dashboard')
def patient_dashboard():
    user_id = session.get('user_id')
    patient = Patient.query.filter_by(user_id=user_id).first()
    if not patient:
        flash('Patient profile not found. Please contact admin.', 'danger')
        return redirect(url_for('common.logout'))
        
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

@patient_bp.route('/patient/doctors')
def patient_find_doctors():
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

@patient_bp.route('/api/doctor/<int:doctor_id>/availability', methods=['GET'])
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
            ).filter(Appointment.status != 'Cancelled').count() 
            
            if booked_count < av.total_seats:
                slots.append({'time': start_time.strftime('%H:%M')})
            start_time += timedelta(minutes=30)
    return jsonify(slots)

@patient_bp.route('/patient/book/<int:doctor_id>', methods=['GET', 'POST'])
def patient_book_appointment(doctor_id):
    user_id = session.get('user_id')
    patient = Patient.query.filter_by(user_id=user_id).first()
    if not patient:
        flash('Patient profile error.', 'danger')
        return redirect(url_for('patient.patient_dashboard'))

    doctor = Doctor.query.get_or_404(doctor_id)
    
    consultation_fee = doctor.department.price if doctor.department else 500.0

    available_dates_query = DoctorAvailability.query.filter(
        DoctorAvailability.doctor_id == doctor_id,
        DoctorAvailability.date >= date.today(),
        DoctorAvailability.is_available == True
    ).with_entities(DoctorAvailability.date).distinct().order_by(DoctorAvailability.date).all()
    
    available_dates = [d.date for d in available_dates_query]

    if request.method == 'POST':
        appointment_date = datetime.strptime(request.form.get('appointment_date'), '%Y-%m-%d').date()
        appointment_time = datetime.strptime(request.form.get('appointment_time'), '%H:%M').time()
        reason = request.form.get('reason')
        
        existing_appt = Appointment.query.filter_by(
            patient_id=patient.id,
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            appointment_time=appointment_time
        ).filter(Appointment.status != 'Cancelled').first()

        if existing_appt:
            if existing_appt.status == 'Pending Payment':
                flash('You already have a pending booking for this slot. Redirecting to payment.', 'info')
                return redirect(url_for('patient.patient_pay', appointment_id=existing_appt.id))
            elif existing_appt.status == 'Booked':
                flash('You have already booked this appointment.', 'warning')
                return redirect(url_for('patient.patient_appointments'))

        availability = DoctorAvailability.query.filter(
            DoctorAvailability.doctor_id == doctor_id,
            DoctorAvailability.date == appointment_date,
            DoctorAvailability.start_time <= appointment_time,
            DoctorAvailability.end_time > appointment_time,
            DoctorAvailability.is_available == True
        ).first()

        if not availability:
            flash('Slot not available.', 'danger')
            return redirect(url_for('patient.patient_book_appointment', doctor_id=doctor_id))

        booked_count = Appointment.query.filter_by(
            doctor_id=doctor_id, appointment_date=appointment_date, appointment_time=appointment_time
        ).filter(Appointment.status != 'Cancelled').count()

        if booked_count >= availability.total_seats:
            flash('This slot is fully booked.', 'danger')
            return redirect(url_for('patient.patient_book_appointment', doctor_id=doctor_id))

        try:
            appointment = Appointment(
                patient_id=patient.id,
                doctor_id=doctor_id,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                reason=reason,
                status='Pending Payment'
            )
            db.session.add(appointment)
            db.session.flush()

            # 4. Create Payment Record
            payment = Payment(
                appointment_id=appointment.id,
                amount=consultation_fee,
                status='Pending'
            )
            db.session.add(payment)
            db.session.commit()
            
            return redirect(url_for('patient.patient_pay', appointment_id=appointment.id))
            
        except IntegrityError:
            db.session.rollback()
            flash('This time slot was just booked by someone else. Please choose another.', 'danger')
            return redirect(url_for('patient.patient_book_appointment', doctor_id=doctor_id))

    return render_template('patient_book_appointment.html', doctor=doctor, fee=consultation_fee, available_dates=available_dates)

@patient_bp.route('/patient/pay/<int:appointment_id>', methods=['GET', 'POST'])
def patient_pay(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    
    user_id = session.get('user_id')
    patient = Patient.query.filter_by(user_id=user_id).first()
    if appointment.patient_id != patient.id:
        flash('Unauthorized access to this payment.', 'danger')
        return redirect(url_for('patient.patient_dashboard'))

    payment = Payment.query.filter_by(appointment_id=appointment.id).first()
    
    # Check if already paid
    if payment.status == 'Success':
        flash('Payment already completed for this appointment.', 'info')
        return redirect(url_for('patient.patient_appointments'))
    
    if request.method == 'POST':
        payment.status = 'Success'
        payment.payment_date = datetime.utcnow()
        appointment.status = 'Booked' 
        
        db.session.commit()
        
        flash('Payment successful! Appointment confirmed.', 'success')
        return redirect(url_for('patient.patient_appointments')) 

    return render_template('patient_payment.html', appointment=appointment, payment=payment)


@patient_bp.route('/patient/appointments')
def patient_appointments():
    user_id = session.get('user_id')
    patient = Patient.query.filter_by(user_id=user_id).first()
    appointments = Appointment.query.filter_by(patient_id=patient.id).order_by(Appointment.appointment_date.desc()).all()
    return render_template('patient_appointments.html', appointments=appointments)

@patient_bp.route('/patient/cancel/<int:appointment_id>')
def patient_cancel_appointment(appointment_id):
    user_id = session.get('user_id')
    patient = Patient.query.filter_by(user_id=user_id).first()
    appointment = Appointment.query.get_or_404(appointment_id)

    if appointment.patient_id != patient.id:
        flash('Unauthorized!', 'danger')
        return redirect(url_for('patient.patient_dashboard'))

    if appointment.status == 'Booked' or appointment.status == 'Pending Payment':
        appointment.status = 'Cancelled'
        db.session.commit()
        flash('Cancelled successfully.', 'success')
    else:
        flash('Cannot cancel this appointment.', 'danger')
    return redirect(url_for('patient.patient_appointments'))

@patient_bp.route('/patient/appointment/view/<int:appointment_id>')
def patient_view_appointment(appointment_id):
    user_id = session.get('user_id')
    patient = Patient.query.filter_by(user_id=user_id).first()
    appointment = Appointment.query.get_or_404(appointment_id)

    if appointment.patient_id != patient.id:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('patient.patient_appointments'))

    return render_template('patient_view_appointment.html', appointment=appointment)


@patient_bp.route('/patient/history')
def patient_medical_history():
    user_id = session.get('user_id')
    patient = Patient.query.filter_by(user_id=user_id).first()
    appointments = Appointment.query.filter_by(patient_id=patient.id, status='Completed').order_by(Appointment.appointment_date.desc()).all()
    return render_template('patient_medical_history.html', appointments=appointments)

@patient_bp.route('/patient/profile', methods=['GET', 'POST'])
def patient_profile():
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
        return redirect(url_for('patient.patient_profile'))

    return render_template('patient_profile.html', patient=patient)