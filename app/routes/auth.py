from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
import requests
import secrets
from app import db
from app.models.user import User
from app.models.session import UserSession
from app.forms import LoginForm, RegistrationForm, OTPVerificationForm
from app.utils.email import send_otp_email

auth_bp = Blueprint('auth', __name__)


def create_user_session(user, token):
    """Helper to create a user session record"""
    try:
        UserSession.create_session(
            user=user,
            session_token=token,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Failed to create session record: {e}")
        db.session.rollback()


# ==================== STANDARD AUTH ====================

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    if request.method == 'POST':
        if not form.validate_on_submit():
            # Log form validation errors for debugging
            if form.errors:
                for field, errors in form.errors.items():
                    for error in errors:
                        if field == 'csrf_token':
                            flash('Session expired. Please try again.', 'warning')
                        else:
                            flash(f'{field}: {error}', 'danger')
            return render_template('auth/login.html', form=form)
        
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact admin.', 'danger')
                return redirect(url_for('auth.login'))
            
            # Check if user is approved (admins, super_admins, finance, viewer roles skip approval check)
            # Finance and viewer can only be created by admins, so they're inherently trusted
            if user.role not in ['admin', 'super_admin', 'finance', 'viewer']:
                # Check if user needs approval
                if user.approval_status == 'pending':
                    flash('Your registration is pending admin approval. Please wait for approval.', 'warning')
                    return redirect(url_for('auth.login'))
                elif user.approval_status == 'rejected':
                    flash(f'Your registration was rejected. Reason: {user.rejection_reason or "Not specified"}', 'danger')
                    return redirect(url_for('auth.login'))
                elif user.approval_status != 'approved' and not user.is_approved:
                    # If approval_status is not set and is_approved is False, require approval
                    flash('Your account is not approved. Please contact admin.', 'warning')
                    return redirect(url_for('auth.login'))
            
            # Check if OTP is required for this user (chairs only)
            otp_required = current_app.config.get('OTP_REQUIRED_FOR_CHAIRS', True)
            if otp_required and user.role == 'chair':
                # Generate and send OTP
                otp_code = user.generate_otp()
                db.session.commit()
                
                success, message = send_otp_email(user, otp_code)
                if success:
                    # Store user ID in session for OTP verification
                    session['otp_user_id'] = user.id
                    session['otp_next'] = request.args.get('next')
                    flash(f'A verification code has been sent to {user.email}. Please check your email.', 'info')
                    return redirect(url_for('auth.verify_otp'))
                else:
                    # If email fails, log them in anyway with a warning
                    current_app.logger.error(f"OTP email failed for {user.email}: {message}")
                    flash('Email verification unavailable. Proceeding with login.', 'warning')
            
            # Direct login for non-chair users or if OTP not required
            user.last_login = datetime.utcnow()
            token = user.generate_session_token()
            db.session.commit()
            
            login_user(user)
            session['session_token'] = token
            
            # Create session record
            create_user_session(user, token)
            
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('auth/login.html', form=form)


@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    """Verify OTP for chair login"""
    # Check if we have a pending OTP verification
    user_id = session.get('otp_user_id')
    if not user_id:
        flash('No pending verification. Please login again.', 'warning')
        return redirect(url_for('auth.login'))
    
    user = User.query.get(user_id)
    if not user:
        session.pop('otp_user_id', None)
        flash('User not found. Please login again.', 'danger')
        return redirect(url_for('auth.login'))
    
    form = OTPVerificationForm()
    if form.validate_on_submit():
        otp_code = form.otp.data.strip()
        
        if user.verify_otp(otp_code):
            # OTP verified - complete login
            user.clear_otp()
            user.last_login = datetime.utcnow()
            token = user.generate_session_token()
            db.session.commit()
            
            login_user(user)
            session['session_token'] = token
            
            # Create session record
            create_user_session(user, token)
            
            # Clear OTP session data
            next_page = session.pop('otp_next', None)
            session.pop('otp_user_id', None)
            
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
        else:
            flash('Invalid or expired verification code. Please try again.', 'danger')
    
    return render_template('auth/verify_otp.html', form=form, user=user)


@auth_bp.route('/resend-otp', methods=['POST'])
def resend_otp():
    """Resend OTP to user's email"""
    user_id = session.get('otp_user_id')
    if not user_id:
        flash('No pending verification. Please login again.', 'warning')
        return redirect(url_for('auth.login'))
    
    user = User.query.get(user_id)
    if not user:
        session.pop('otp_user_id', None)
        flash('User not found. Please login again.', 'danger')
        return redirect(url_for('auth.login'))
    
    # Generate new OTP
    otp_code = user.generate_otp()
    db.session.commit()
    
    success, message = send_otp_email(user, otp_code)
    if success:
        flash(f'A new verification code has been sent to {user.email}.', 'info')
    else:
        flash('Failed to send verification code. Please try again.', 'danger')
    
    return redirect(url_for('auth.verify_otp'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if email already exists
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Email already registered. Please login or use a different email.', 'danger')
            return render_template('auth/register.html', form=form)
        
        # Check if parish already has an approved chair
        if form.role.data == 'chair':
            existing_chair = User.get_parish_chair(form.parish.data)
            if existing_chair:
                flash(f'Parish "{form.parish.data}" already has an approved chair ({existing_chair.name}). Only one chair per parish is allowed.', 'danger')
                return render_template('auth/register.html', form=form)
            
            # Check if there's a pending request for this parish
            pending_chair = User.query.filter_by(
                parish=form.parish.data,
                role='chair',
                approval_status='pending'
            ).first()
            if pending_chair:
                flash(f'There is already a pending registration for parish "{form.parish.data}". Please wait for admin review.', 'warning')
                return render_template('auth/register.html', form=form)
        
        user = User(
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data or None,
            role=form.role.data,
            local_church=form.local_church.data,
            parish=form.parish.data,
            archdeaconry=form.archdeaconry.data,
            oauth_provider='local',
            is_approved=False,
            approval_status='pending'
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration submitted successfully! Your account is pending admin approval. You will receive an email once approved.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    # Mark session as inactive (with error handling for missing table)
    try:
        from app.models.session import UserSession
        token = session.get('session_token')
        if token:
            session_record = UserSession.query.filter_by(
                session_token=token,
                user_id=current_user.id
            ).first()
            if session_record:
                session_record.is_active = False
                db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Error deactivating session (table may not exist): {e}")
        try:
            db.session.rollback()
        except:
            pass
    
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


# ==================== GOOGLE OAUTH ====================

@auth_bp.route('/login/google')
def google_login():
    """Initiate Google OAuth flow"""
    # Check if Google OAuth is configured
    client_id = current_app.config.get('GOOGLE_CLIENT_ID')
    if not client_id:
        flash('Google login is not configured. Please contact administrator.', 'warning')
        return redirect(url_for('auth.login'))
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    
    # Build Google OAuth URL
    redirect_uri = url_for('auth.google_callback', _external=True)
    
    google_auth_url = (
        'https://accounts.google.com/o/oauth2/v2/auth?'
        f'client_id={client_id}&'
        f'redirect_uri={redirect_uri}&'
        'response_type=code&'
        'scope=openid email profile&'
        f'state={state}&'
        'access_type=offline&'
        'prompt=select_account'
    )
    
    return redirect(google_auth_url)


@auth_bp.route('/login/google/callback')
def google_callback():
    """Handle Google OAuth callback"""
    # Verify state
    state = request.args.get('state')
    stored_state = session.pop('oauth_state', None)
    
    if state != stored_state:
        flash('Invalid OAuth state. Please try again.', 'danger')
        return redirect(url_for('auth.login'))
    
    # Check for errors
    error = request.args.get('error')
    if error:
        flash(f'Google login failed: {error}', 'danger')
        return redirect(url_for('auth.login'))
    
    # Get authorization code
    code = request.args.get('code')
    if not code:
        flash('No authorization code received.', 'danger')
        return redirect(url_for('auth.login'))
    
    try:
        # Exchange code for tokens
        client_id = current_app.config.get('GOOGLE_CLIENT_ID')
        client_secret = current_app.config.get('GOOGLE_CLIENT_SECRET')
        redirect_uri = url_for('auth.google_callback', _external=True)
        
        token_response = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code'
            },
            timeout=10
        )
        
        if token_response.status_code != 200:
            flash('Failed to get access token from Google.', 'danger')
            return redirect(url_for('auth.login'))
        
        tokens = token_response.json()
        access_token = tokens.get('access_token')
        
        # Get user info from Google
        user_info_response = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        
        if user_info_response.status_code != 200:
            flash('Failed to get user info from Google.', 'danger')
            return redirect(url_for('auth.login'))
        
        user_info = user_info_response.json()
        google_id = user_info.get('id')
        email = user_info.get('email')
        name = user_info.get('name')
        picture = user_info.get('picture')
        
        if not email:
            flash('Email not provided by Google. Please try again.', 'danger')
            return redirect(url_for('auth.login'))
        
        # Find or create user
        user = User.query.filter_by(google_id=google_id).first()
        
        if not user:
            # Check if email exists (user registered manually)
            user = User.query.filter_by(email=email).first()
            
            if user:
                # Link Google account to existing user
                user.google_id = google_id
                user.profile_picture = picture
                if not user.oauth_provider:
                    user.oauth_provider = 'google'
            else:
                # Create new user
                user = User(
                    name=name,
                    email=email,
                    google_id=google_id,
                    profile_picture=picture,
                    oauth_provider='google',
                    role='user',  # Default role for Google sign-ups
                    is_active=True
                )
                db.session.add(user)
        
        # Update profile picture if changed
        if user.profile_picture != picture:
            user.profile_picture = picture
        
        # Update last login
        user.last_login = datetime.utcnow()
        
        # Check if user is active
        if not user.is_active:
            flash('Your account has been deactivated. Please contact admin.', 'danger')
            return redirect(url_for('auth.login'))
        
        # Generate new session token (invalidates other sessions)
        token = user.generate_session_token()
        db.session.commit()
        
        # Log in user
        login_user(user)
        
        # Store session token in browser session
        session['session_token'] = token
        
        # Create session record
        create_user_session(user, token)
        
        # Check if user needs to complete profile
        if not user.local_church or not user.parish:
            flash(f'Welcome {user.name}! Please complete your profile.', 'info')
            return redirect(url_for('auth.complete_profile'))
        
        flash(f'Welcome back, {user.name}!', 'success')
        return redirect(url_for('main.dashboard'))
        
    except requests.RequestException as e:
        current_app.logger.error(f'Google OAuth error: {str(e)}')
        flash('An error occurred during Google login. Please try again.', 'danger')
        return redirect(url_for('auth.login'))
    except Exception as e:
        current_app.logger.error(f'Google OAuth error: {str(e)}')
        flash('An unexpected error occurred. Please try again.', 'danger')
        return redirect(url_for('auth.login'))


@auth_bp.route('/complete-profile', methods=['GET', 'POST'])
@login_required
def complete_profile():
    """Allow OAuth users to complete their profile"""
    if request.method == 'POST':
        current_user.phone = request.form.get('phone') or None
        current_user.local_church = request.form.get('local_church')
        current_user.parish = request.form.get('parish')
        current_user.archdeaconry = request.form.get('archdeaconry')
        
        # Update role if provided and user is new
        role = request.form.get('role')
        if role and current_user.role == 'user':
            current_user.role = role
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('main.dashboard'))
    
    # Get church hierarchy data
    archdeaconries = [
        'Amagoro', 'Angurai', 'Budalangi', 'Busia', 'Butula',
        'Funyula', 'Matayos', 'Teso North', 'Teso South'
    ]
    
    return render_template('auth/complete_profile.html', archdeaconries=archdeaconries)
