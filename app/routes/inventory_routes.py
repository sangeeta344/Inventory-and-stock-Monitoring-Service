from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, Product, InventoryBatch, StockMovement, Notification
from app.services.auth_service import role_required, log_audit
from app.services.inventory_service import InventoryService
from datetime import date, timedelta

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/inventory')
@login_required
@role_required('OWNER', 'CASHIER')
def index():
    status = request.args.get('status', 'all') # 'all', 'near_expiry', 'expired', 'active'
    product_id = request.args.get('product_id', type=int)

    query = InventoryBatch.query.filter(InventoryBatch.quantity_remaining > 0)

    if product_id:
        query = query.filter(InventoryBatch.product_id == product_id)

    today = date.today()
    if status == 'expired':
        query = query.filter(InventoryBatch.expiry_date != None, InventoryBatch.expiry_date < today)
    elif status == 'near_expiry':
        threshold = today + timedelta(days=30)
        query = query.filter(InventoryBatch.expiry_date != None, InventoryBatch.expiry_date >= today, InventoryBatch.expiry_date <= threshold)
    elif status == 'active':
        query = query.filter(InventoryBatch.is_active == True, db.or_(InventoryBatch.expiry_date == None, InventoryBatch.expiry_date >= today))

    batches = query.order_by(
        db.case((InventoryBatch.expiry_date.is_(None), 1), else_=0),
        InventoryBatch.expiry_date.asc()
    ).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name.asc()).all()

    return render_template(
        'inventory/index.html',
        batches=batches,
        products=products,
        current_status=status,
        current_product=product_id
    )

@inventory_bp.route('/inventory/movements')
@login_required
@role_required('OWNER', 'CASHIER')
def movements():
    movement_type = request.args.get('type', 'all')
    product_id = request.args.get('product_id', type=int)

    query = StockMovement.query

    if movement_type != 'all':
        query = query.filter(StockMovement.movement_type == movement_type)

    if product_id:
        query = query.filter(StockMovement.product_id == product_id)

    records = query.order_by(StockMovement.created_at.desc()).limit(150).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name.asc()).all()

    return render_template(
        'inventory/movements.html',
        movements=records,
        products=products,
        current_type=movement_type,
        current_product=product_id
    )

@inventory_bp.route('/inventory/wastage', methods=['GET', 'POST'])
@login_required
@role_required('OWNER')
def wastage():
    if request.method == 'POST':
        batch_id = request.form.get('batch_id', type=int)
        quantity = request.form.get('quantity', type=int)
        wastage_type = request.form.get('wastage_type', 'DAMAGED') # DAMAGED or EXPIRED
        reason = request.form.get('reason', '').strip()

        if not batch_id or not quantity or quantity <= 0:
            flash('Please select a valid batch and enter a quantity greater than zero.', 'danger')
            return redirect(url_for('inventory.wastage'))

        try:
            InventoryService.record_batch_wastage(
                batch_id=batch_id,
                quantity=quantity,
                wastage_type=wastage_type,
                reason=reason,
                user_id=current_user.id
            )
            log_audit(current_user.id, 'RECORD_WASTAGE', 'INVENTORY_MANAGEMENT', f"Recorded {quantity} items as {wastage_type} wastage")
            flash(f"Successfully recorded wastage for {quantity} items.", 'success')
        except Exception as e:
            flash(f"Wastage recording failed: {str(e)}", 'danger')

        return redirect(url_for('inventory.wastage'))

    # Get active batches with stock
    available_batches = InventoryBatch.query.filter(
        InventoryBatch.quantity_remaining > 0,
        InventoryBatch.is_active == True
    ).order_by(InventoryBatch.created_at.desc()).all()

    # Recent wastage movements
    wastage_history = StockMovement.query.filter(
        StockMovement.movement_type.in_(['DAMAGE_WASTAGE', 'EXPIRED_WASTAGE'])
    ).order_by(StockMovement.created_at.desc()).limit(30).all()

    return render_template(
        'inventory/wastage.html',
        batches=available_batches,
        history=wastage_history
    )

@inventory_bp.route('/inventory/alerts')
@login_required
@role_required('OWNER', 'CASHIER')
def alerts():
    InventoryService.scan_for_system_alerts()
    all_notifications = Notification.query.order_by(Notification.created_at.desc()).limit(100).all()
    return render_template('inventory/alerts.html', notifications=all_notifications)
