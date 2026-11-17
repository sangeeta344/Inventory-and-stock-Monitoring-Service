from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User
from app.services.auth_service import log_audit

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'CASHIER':
            return redirect(url_for('billing.pos'))
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.query.filter((User.username == username) | (User.email == username)).first()

        if not user or not user.check_password(password):
            flash('Invalid username or password. Please verify your credentials.', 'danger')
            return render_template('auth/login.html')

        if not user.is_active:
            flash('This account has been deactivated. Please contact the supermarket owner.', 'warning')
            return render_template('auth/login.html')

        login_user(user, remember=remember)
        log_audit(user.id, 'LOGIN', 'AUTHENTICATION', f"User {user.username} logged in successfully.")
        flash(f'Welcome back, {user.full_name}!', 'success')

        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        
        if user.role == 'CASHIER':
            return redirect(url_for('billing.pos'))
        return redirect(url_for('dashboard.index'))

    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    log_audit(current_user.id, 'LOGOUT', 'AUTHENTICATION', f"User {current_user.username} logged out.")
    logout_user()
    flash('You have been securely logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        new_password = request.form.get('new_password', '').strip()

        if not full_name:
            flash('Full Name is required.', 'danger')
            return redirect(url_for('auth.profile'))

        current_user.full_name = full_name
        current_user.phone = phone

        if new_password:
            if len(new_password) < 6:
                flash('Password must be at least 6 characters long.', 'danger')
                return redirect(url_for('auth.profile'))
            current_user.set_password(new_password)
            flash('Profile and password updated successfully.', 'success')
        else:
            flash('Profile updated successfully.', 'success')

        db.session.commit()
        log_audit(current_user.id, 'UPDATE_PROFILE', 'USER_MANAGEMENT', 'Updated user profile')
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html')
