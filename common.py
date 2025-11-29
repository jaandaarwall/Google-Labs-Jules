from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from models import db, User, Role, Doctor, Patient
from datetime import datetime, date
from sqlalchemy import or_
from werkzeug.security import generate_password_hash
import mail # Import the mail module

common_bp = Blueprint('common', __name__)

# Simple in-memory store for rate limiting (IP -> Date)
# In production, use Redis or Database
registration_log = {}

@common_bp.before_app_request
def check_account_status():
    """Global check to expire session if user is deactivated"""
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if not user or not user.is_active:
            session.clear()
            flash('Your session has expired or your account was deactivated.', 'danger')
            return redirect(url_for('common.login'))

@common_bp.route('/')
def index():
    """Landing page with auto-redirect if logged in"""
    if 'user_id' in session:
        role = session.get('user_role')
        if role == 'admin': return redirect(url_for('admin.admin_dashboard'))
        elif role == 'doctor': return redirect(url_for('doctor.doctor_dashboard'))
        elif role == 'patient': return redirect(url_for('patient.patient_dashboard'))
    
    return render_template('index.html')

@common_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Unified login page"""
    # Auto-redirect if already logged in
    if 'user_id' in session:
        return redirect(url_for('common.index'))

    if request.method == 'POST':
        login_input = request.form.get('username') 
        password = request.form.get('password')
        requested_role = request.form.get('role')

        user = User.query.filter(
            or_(User.username == login_input, User.email == login_input)
        ).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated.', 'warning')
                return redirect(url_for('common.login'))

            if not user.has_role(requested_role) and requested_role != 'admin': 
                flash(f'Access denied. You do not have {requested_role} privileges.', 'danger')
                return redirect(url_for('common.login'))
            
            # Check specific profiles
            if requested_role == 'doctor' and not Doctor.query.filter_by(user_id=user.id).first():
                flash('Doctor profile not found.', 'danger')
                return redirect(url_for('common.login'))
            
            if requested_role == 'patient' and not Patient.query.filter_by(user_id=user.id).first():
                flash('Patient profile not found.', 'danger')
                return redirect(url_for('common.login'))

            session['user_id'] = user.id 
            session['user_name'] = user.full_name
            session['user_role'] = requested_role

            flash('Login successful!', 'success')
            return redirect(url_for('common.index'))

        else:
            flash('Invalid credentials!', 'danger')
            return redirect(url_for('common.login'))

    return render_template('login.html')

@common_bp.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('common.login'))

@common_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Patient registration with 1-per-day rate limit"""
    if request.method == 'POST':
        # 1. Rate Limit Check
        user_ip = request.remote_addr
        today = date.today()
        
        if user_ip in registration_log and registration_log[user_ip] == today:
             flash('You can only register once per day from this IP address.', 'warning')
             return redirect(url_for('common.register'))
        
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

        # Log the registration for rate limiting
        registration_log[user_ip] = today

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('common.login'))

    return render_template('register.html')

@common_bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('common.login'))
        
    if request.method == 'POST':
        old_pass = request.form.get('old_password')
        new_pass = request.form.get('new_password')
        
        user = User.query.get(session['user_id'])
        if user.check_password(old_pass):
            user.set_password(new_pass)
            db.session.commit()
            flash('Password updated successfully.', 'success')
            return redirect(url_for('common.index'))
        else:
            flash('Incorrect current password.', 'danger')
            
    return render_template('change_password.html')

@common_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # In a real app, generate a secure token. 
            # Here we will generate a temporary password for simplicity as requested.
            import secrets
            temp_pass = secrets.token_hex(4)
            user.set_password(temp_pass)
            db.session.commit()
            
            subject = "Password Reset - HMS"
            body = f"Hello {user.full_name},\n\nYour temporary password is: {temp_pass}\n\nPlease login and change it immediately."
            
            # Send email
            mail.send_email(user.email, subject, body)
            flash(f'A temporary password has been sent to {email}', 'info')
            return redirect(url_for('common.login'))
        else:
            flash('Email not found in our system.', 'danger')
            
    return render_template('forgot_password.html')