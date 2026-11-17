from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, User, Employee, AuditLog, Sale
from app.services.auth_service import role_required, log_audit
from sqlalchemy import func
from datetime import date

employee_bp = Blueprint('employees', __name__)

@employee_bp.route('/employees')
@login_required
@role_required('OWNER')
def index():
    users = User.query.order_by(User.role.asc(), User.full_name.asc()).all()
    
    # Calculate performance for each user (sales count and total sales)
    user_stats = {}
    for u in users:
        sales_agg = db.session.query(
            func.count(Sale.id),
            func.coalesce(func.sum(Sale.final_amount), 0.0)
        ).filter(Sale.cashier_id == u.id, Sale.payment_status == 'COMPLETED').first()
        
        user_stats[u.id] = {
            'sales_count': sales_agg[0] if sales_agg else 0,
            'total_sales_amount': float(sales_agg[1]) if sales_agg else 0.0
        }

    return render_template('employees/index.html', users=users, stats=user_stats)

@employee_bp.route('/employees/add', methods=['POST'])
@login_required
@role_required('OWNER')
def add_employee():
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    full_name = request.form.get('full_name', '').strip()
    role = request.form.get('role', 'CASHIER')
    phone = request.form.get('phone', '').strip()
    designation = request.form.get('designation', 'Cashier').strip()
    salary = request.form.get('salary', type=float, default=0.0)
    employee_code = request.form.get('employee_code', '').strip()

    if not username or not email or not password or not full_name:
        flash('Username, email, password, and full name are required.', 'danger')
        return redirect(url_for('employees.index'))

    if User.query.filter_by(username=username).first():
        flash(f"Username '{username}' is already taken.", 'danger')
        return redirect(url_for('employees.index'))

    if User.query.filter_by(email=email).first():
        flash(f"Email '{email}' is already registered.", 'danger')
        return redirect(url_for('employees.index'))

    if not employee_code:
        employee_code = f"EMP-{username.upper()[:4]}-{User.query.count() + 1:03d}"

    try:
        user = User(
            username=username,
            email=email,
            role=role,
            full_name=full_name,
            phone=phone,
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        emp = Employee(
            user_id=user.id,
            employee_code=employee_code,
            designation=designation,
            salary=salary,
            hire_date=date.today()
        )
        db.session.add(emp)
        db.session.commit()

        log_audit(current_user.id, 'CREATE_EMPLOYEE', 'EMPLOYEE_MANAGEMENT', f"Created account {username} ({role})")
        flash(f"Employee '{full_name}' ({role}) created successfully!", 'success')

    except Exception as e:
        db.session.rollback()
        flash(f"Error creating employee: {str(e)}", 'danger')

    return redirect(url_for('employees.index'))

@employee_bp.route('/employees/toggle-status/<int:id>', methods=['POST'])
@login_required
@role_required('OWNER')
def toggle_status(id):
    if id == current_user.id:
        flash('You cannot deactivate your own owner account!', 'danger')
        return redirect(url_for('employees.index'))

    user = User.query.get_or_404(id)
    user.is_active = not user.is_active
    db.session.commit()
    status_label = 'Activated' if user.is_active else 'Deactivated'
    log_audit(current_user.id, 'TOGGLE_USER_STATUS', 'EMPLOYEE_MANAGEMENT', f"{status_label} user {user.username}")
    flash(f"User '{user.full_name}' has been {status_label.lower()}.", 'info')
    return redirect(url_for('employees.index'))

@employee_bp.route('/employees/activity')
@login_required
@role_required('OWNER')
def activity_logs():
    user_id = request.args.get('user_id', type=int)
    module = request.args.get('module', 'all')

    query = AuditLog.query
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if module != 'all':
        query = query.filter(AuditLog.module == module)

    logs = query.order_by(AuditLog.created_at.desc()).limit(200).all()
    users = User.query.all()
    modules = ['AUTHENTICATION', 'POS_BILLING', 'PRODUCT_CATALOG', 'INVENTORY_MANAGEMENT', 'PURCHASE_MANAGEMENT', 'RETURN_MANAGEMENT', 'EMPLOYEE_MANAGEMENT', 'EXPENSE_MANAGEMENT', 'SUPPLIER_MANAGEMENT']

    return render_template(
        'employees/activity.html',
        logs=logs,
        users=users,
        modules=modules,
        current_user_id=user_id,
        current_module=module
    )
