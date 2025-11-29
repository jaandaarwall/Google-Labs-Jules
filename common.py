from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from models import db, User, Role, Doctor, Patient
from datetime import datetime
from sqlalchemy import or_

common_bp = Blueprint('common', __name__)

@common_bp.route('/')
def index():
    """Landing page"""
    return render_template('index.html')

@common_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Unified login page with Username OR Email support"""
    if request.method == 'POST':
        login_input = request.form.get('username') # Contains username OR email
        password = request.form.get('password')
        requested_role = request.form.get('role')

        # Allow login by Username OR Email
        user = User.query.filter(
            or_(User.username == login_input, User.email == login_input)
        ).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated.', 'warning')
                return redirect(url_for('common.login'))

            # Check permissions
            if not user.has_role(requested_role) and requested_role != 'admin': 
                flash(f'Access denied. You do not have {requested_role} privileges.', 'danger')
                return redirect(url_for('common.login'))
            
            # Check if specific profile exists (prevents crashes)
            if requested_role == 'doctor' and not Doctor.query.filter_by(user_id=user.id).first():
                flash('Doctor profile not found. Please contact admin.', 'danger')
                return redirect(url_for('common.login'))
            
            if requested_role == 'patient' and not Patient.query.filter_by(user_id=user.id).first():
                flash('Patient profile not found. Please contact admin.', 'danger')
                return redirect(url_for('common.login'))

            session['user_id'] = user.id 
            session['user_name'] = user.full_name
            session['user_role'] = requested_role

            flash('Login successful!', 'success')

            if requested_role == 'admin':
                if user.has_role('admin'): return redirect(url_for('admin.admin_dashboard'))
            elif requested_role == 'doctor':
                if user.has_role('doctor'): return redirect(url_for('doctor.doctor_dashboard'))
            elif requested_role == 'patient':
                if user.has_role('patient'): return redirect(url_for('patient.patient_dashboard'))
            
            flash('Role mismatch or unauthorized.', 'danger')
            return redirect(url_for('common.login'))

        else:
            flash('Invalid credentials! Please check your username/email and password.', 'danger')
            return redirect(url_for('common.login'))

    return render_template('login.html')

@common_bp.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('common.index'))

@common_bp.route('/register', methods=['GET', 'POST'])
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
            return redirect(url_for('common.register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('common.register'))

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
        return redirect(url_for('common.login'))

    return render_template('register.html')