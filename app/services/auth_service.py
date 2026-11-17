from functools import wraps
from flask import abort, flash, redirect, url_for, request
from flask_login import current_user
from app.models import db, AuditLog

def role_required(*allowed_roles):
    """
    Decorator to restrict route access by user role (OWNER, CASHIER).
    Provides backend role-based access control, preventing unauthorized access.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login', next=request.url))
            
            if current_user.role not in allowed_roles:
                flash('Access denied: You do not have permission to access this resource.', 'danger')
                return abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_audit(user_id, action, module, details=None):
    """
    Records an immutable audit trail entry for critical employee and management operations.
    """
    try:
        ip = request.remote_addr if request else '127.0.0.1'
        log = AuditLog(
            user_id=user_id,
            action=action,
            module=module,
            details=details,
            ip_address=ip
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[AUDIT LOG ERROR] Failed to record audit log: {e}")
