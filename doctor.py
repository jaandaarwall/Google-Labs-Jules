from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from models import db, Doctor, Patient, Appointment, Treatment, DoctorAvailability
from datetime import datetime, date, timedelta

doctor_bp = Blueprint('doctor', __name__, url_prefix='/doctor')

@doctor_bp.before_request
def check_doctor():
    if session.get('user_role') != 'doctor':
        return redirect(url_for('common.login'))

@doctor_bp.route('/dashboard')
def doctor_dashboard():
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    if not doctor:
        flash('Doctor profile not found.', 'danger')
        return redirect(url_for('common.login'))

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

@doctor_bp.route('/appointments')
def doctor_appointments():
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    appointments = Appointment.query.filter_by(doctor_id=doctor.id).order_by(Appointment.appointment_date.desc()).all()
    return render_template('doctor_appointments.html', appointments=appointments)

@doctor_bp.route('/patients')
def doctor_patients():
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    patient_ids = db.session.query(Appointment.patient_id).filter_by(doctor_id=doctor.id).distinct().all()
    patients = Patient.query.filter(Patient.id.in_([p_id for p_id, in patient_ids])).all()
    return render_template('doctor_patients.html', patients=patients)

@doctor_bp.route('/availability', methods=['GET', 'POST'])
def doctor_availability():
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()

    if request.method == 'POST':
        date_obj = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        start_time = datetime.strptime(request.form.get('start_time'), '%H:%M').time()
        end_time = datetime.strptime(request.form.get('end_time'), '%H:%M').time()
        total_seats = int(request.form.get('total_seats'))

        availability = DoctorAvailability(
            doctor_id=doctor.id,
            date=date_obj,
            start_time=start_time,
            end_time=end_time,
            total_seats=total_seats
        )
        db.session.add(availability)
        db.session.commit()
        flash('Availability added!', 'success')
        return redirect(url_for('doctor.doctor_availability'))

    availabilities = DoctorAvailability.query.filter_by(doctor_id=doctor.id).order_by(DoctorAvailability.date.desc()).all()
    return render_template('doctor_availability.html', doctor=doctor, availabilities=availabilities)

@doctor_bp.route('/availability/delete/<int:availability_id>')
def doctor_delete_availability(availability_id):
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    
    availability = DoctorAvailability.query.get_or_404(availability_id)
    if availability.doctor_id != doctor.id:
        flash('Unauthorized!', 'danger')
        return redirect(url_for('doctor.doctor_availability'))

    db.session.delete(availability)
    db.session.commit()
    flash('Deleted!', 'success')
    return redirect(url_for('doctor.doctor_availability'))

@doctor_bp.route('/profile', methods=['GET', 'POST'])
def doctor_profile():
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
        return redirect(url_for('doctor.doctor_profile'))

    return render_template('doctor_profile.html', doctor=doctor)

@doctor_bp.route('/appointment/complete/<int:appointment_id>')
def doctor_complete_appointment(appointment_id):
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.doctor_id != doctor.id:
        flash('Unauthorized!', 'danger')
        return redirect(url_for('doctor.doctor_dashboard'))
    if appointment.status == 'Booked':
        appointment.status = 'Completed'
        db.session.commit()
        flash('Marked as completed.', 'success')
    else:
        flash('Cannot mark as completed.', 'danger')
    return redirect(request.referrer or url_for('doctor.doctor_dashboard'))

@doctor_bp.route('/appointment/treatment/<int:appointment_id>', methods=['GET', 'POST'])
def doctor_add_treatment(appointment_id):
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.doctor_id != doctor.id:
        flash('Unauthorized!', 'danger')
        return redirect(url_for('doctor.doctor_dashboard'))
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
        return redirect(url_for('doctor.doctor_appointments'))
    return render_template('doctor_add_treatment.html', appointment=appointment)

@doctor_bp.route('/appointment/view/<int:appointment_id>')
def doctor_view_appointment(appointment_id):
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.doctor_id != doctor.id:
        flash('Unauthorized!', 'danger')
        return redirect(url_for('doctor.doctor_dashboard'))
    return render_template('doctor_view_appointment.html', appointment=appointment)

@doctor_bp.route('/patient/history/<int:patient_id>')
def doctor_patient_history(patient_id):
    user_id = session.get('user_id')
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    patient = Patient.query.get_or_404(patient_id)
    appointments = Appointment.query.filter_by(patient_id=patient_id, doctor_id=doctor.id).order_by(Appointment.appointment_date.desc()).all()
    return render_template('doctor_patient_history.html', patient=patient, appointments=appointments)