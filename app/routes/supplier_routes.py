from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, Supplier
from app.services.auth_service import role_required, log_audit

supplier_bp = Blueprint('suppliers', __name__)

@supplier_bp.route('/suppliers')
@login_required
@role_required('OWNER')
def index():
    suppliers = Supplier.query.order_by(Supplier.company_name.asc()).all()
    return render_template('suppliers/index.html', suppliers=suppliers)

@supplier_bp.route('/suppliers/add', methods=['POST'])
@login_required
@role_required('OWNER')
def add_supplier():
    name = request.form.get('name', '').strip()
    company_name = request.form.get('company_name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    address = request.form.get('address', '').strip()
    payment_details = request.form.get('payment_details', '').strip()

    if not name or not company_name or not phone:
        flash('Contact name, company name, and phone number are required.', 'danger')
        return redirect(url_for('suppliers.index'))

    supplier = Supplier(
        name=name,
        company_name=company_name,
        phone=phone,
        email=email,
        address=address,
        payment_details=payment_details,
        is_active=True
    )
    db.session.add(supplier)
    db.session.commit()
    log_audit(current_user.id, 'ADD_SUPPLIER', 'SUPPLIER_MANAGEMENT', f"Added supplier {company_name}")
    flash(f"Supplier '{company_name}' registered successfully.", 'success')
    return redirect(url_for('suppliers.index'))

@supplier_bp.route('/suppliers/edit/<int:id>', methods=['POST'])
@login_required
@role_required('OWNER')
def edit_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    supplier.name = request.form.get('name', '').strip()
    supplier.company_name = request.form.get('company_name', '').strip()
    supplier.phone = request.form.get('phone', '').strip()
    supplier.email = request.form.get('email', '').strip()
    supplier.address = request.form.get('address', '').strip()
    supplier.payment_details = request.form.get('payment_details', '').strip()

    db.session.commit()
    log_audit(current_user.id, 'EDIT_SUPPLIER', 'SUPPLIER_MANAGEMENT', f"Updated supplier {supplier.company_name}")
    flash(f"Supplier '{supplier.company_name}' updated successfully.", 'success')
    return redirect(url_for('suppliers.index'))

@supplier_bp.route('/suppliers/delete/<int:id>', methods=['POST'])
@login_required
@role_required('OWNER')
def delete_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    if supplier.purchases.count() > 0 or supplier.batches.count() > 0:
        supplier.is_active = False
        db.session.commit()
        flash(f"Supplier '{supplier.company_name}' has associated purchases and cannot be removed. It was marked inactive.", 'warning')
    else:
        name = supplier.company_name
        db.session.delete(supplier)
        db.session.commit()
        log_audit(current_user.id, 'DELETE_SUPPLIER', 'SUPPLIER_MANAGEMENT', f"Deleted supplier {name}")
        flash(f"Supplier '{name}' was deleted.", 'success')
    return redirect(url_for('suppliers.index'))
