from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, Purchase, PurchaseItem, Supplier, Product, AuditLog
from app.services.auth_service import role_required, log_audit
from app.services.inventory_service import InventoryService
from datetime import date, datetime

purchase_bp = Blueprint('purchases', __name__)

@purchase_bp.route('/purchases')
@login_required
@role_required('OWNER', 'CASHIER')
def index():
    query = Purchase.query
    if current_user.is_cashier:
        query = query.filter(Purchase.created_by == current_user.id)
    purchases = query.order_by(Purchase.purchase_date.desc(), Purchase.id.desc()).all()
    return render_template('purchases/index.html', purchases=purchases)

@purchase_bp.route('/purchases/new', methods=['GET', 'POST'])
@login_required
@role_required('OWNER', 'CASHIER')
def new_purchase():
    if current_user.is_cashier:
        return redirect(url_for('procurement.requirement_new'))
    if current_user.is_owner:
        return redirect(url_for('procurement.purchase_order_new'))
    if request.method == 'POST':
        supplier_id = request.form.get('supplier_id', type=int)
        invoice_number = request.form.get('invoice_number', '').strip()
        purchase_date_str = request.form.get('purchase_date', '').strip()
        payment_status = request.form.get('payment_status', 'PAID')
        notes = request.form.get('notes', '').strip()

        # Line items
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        batch_numbers = request.form.getlist('batch_number[]')
        expiry_dates = request.form.getlist('expiry_date[]')

        if not invoice_number or not product_ids:
            flash('Supplier, Invoice Number, and at least one product are required.', 'danger')
            return redirect(url_for('purchases.new_purchase'))

        try:
            purchase_date = date.fromisoformat(purchase_date_str) if purchase_date_str else date.today()
        except ValueError:
            purchase_date = date.today()

        try:
            # A cashier may reuse a supplier or submit basic details for a new one.
            supplier = Supplier.query.get(supplier_id) if supplier_id else None
            if not supplier:
                name = request.form.get('new_supplier_name', '').strip()
                company_name = request.form.get('new_supplier_company', '').strip()
                phone = request.form.get('new_supplier_phone', '').strip()
                if not name or not company_name or not phone:
                    flash('Select a supplier or enter the new supplier contact, company, and phone.', 'danger')
                    return redirect(url_for('purchases.new_purchase'))
                supplier = Supplier(name=name, company_name=company_name, phone=phone, is_active=True)
                db.session.add(supplier)
                db.session.flush()

            purchase = Purchase(
                supplier_id=supplier.id,
                invoice_number=invoice_number,
                purchase_date=purchase_date,
                payment_status=payment_status,
                status='PENDING_APPROVAL',
                notes=notes,
                created_by=current_user.id,
                total_amount=0.0
            )
            db.session.add(purchase)
            db.session.flush()

            total_amount = 0.0

            for i in range(len(product_ids)):
                prod_id = int(product_ids[i])
                qty = int(quantities[i])
                price = float(unit_prices[i])
                if qty <= 0:
                    raise ValueError('Submitted quantities must be greater than zero.')
                if price < 0:
                    raise ValueError('Purchase price cannot be negative.')
                b_num = batch_numbers[i].strip() if i < len(batch_numbers) and batch_numbers[i].strip() else f"B-{invoice_number[-4:]}-{i+1}"
                
                exp_date = None
                if i < len(expiry_dates) and expiry_dates[i].strip():
                    try:
                        exp_date = date.fromisoformat(expiry_dates[i].strip())
                    except ValueError:
                        exp_date = None

                subtotal = qty * price
                total_amount += subtotal

                p_item = PurchaseItem(
                    purchase_id=purchase.id,
                    product_id=prod_id,
                    batch_number=b_num,
                    expiry_date=exp_date,
                    quantity=qty,
                    unit_price=price,
                    subtotal=subtotal
                )
                db.session.add(p_item)
                db.session.flush()

            purchase.total_amount = total_amount
            db.session.commit()

            log_audit(current_user.id, 'SUBMIT_STOCK_REQUEST', 'PURCHASE_APPROVAL', f"Submitted purchase {invoice_number} for owner approval")
            flash(f"Stock request {invoice_number} submitted. Inventory will change only after owner approval.", 'success')
            return redirect(url_for('purchases.index'))

        except Exception as e:
            db.session.rollback()
            flash(f"Error processing purchase: {str(e)}", 'danger')
            return redirect(url_for('purchases.new_purchase'))

    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.company_name.asc()).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name.asc()).all()
    return render_template('purchases/form.html', suppliers=suppliers, products=products)

@purchase_bp.route('/purchases/view/<int:id>')
@login_required
@role_required('OWNER', 'CASHIER')
def view_purchase(id):
    purchase = Purchase.query.get_or_404(id)
    if current_user.is_cashier and purchase.created_by != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('purchases.index'))
    return render_template('purchases/view.html', purchase=purchase)

@purchase_bp.route('/purchases/<int:id>/approve', methods=['POST'])
@login_required
@role_required('OWNER')
def approve_purchase(id):
    purchase = Purchase.query.get_or_404(id)
    if purchase.status != 'PENDING_APPROVAL':
        flash('This stock request is no longer pending.', 'warning')
        return redirect(url_for('purchases.view_purchase', id=id))

    try:
        adjustment_reason = request.form.get('quantity_adjustment_reason', '').strip()
        adjustments = []

        for item in purchase.items:
            approved_value = request.form.get(f'approved_quantity_{item.id}', type=int)
            if approved_value is None or approved_value <= 0:
                raise ValueError(f"Invalid approved quantity for {item.product.name}.")
            changed = approved_value != item.quantity
            if approved_value != item.quantity:
                if not adjustment_reason:
                    raise ValueError('A quantity adjustment reason is required.')
                adjustments.append(f"{item.product.name}: {item.quantity}->{approved_value}")

            item.approved_quantity = approved_value
            item.quantity_adjustment_reason = adjustment_reason if changed else None

        purchase.status = 'APPROVED'
        purchase.approved_by = current_user.id
        purchase.approved_at = datetime.utcnow()

        for item in purchase.items:
            if item.approved_quantity <= 0:
                continue
            batch = InventoryService.receive_purchase_batch(
                product_id=item.product_id,
                supplier_id=purchase.supplier_id,
                purchase_item_id=item.id,
                batch_number=item.batch_number,
                purchase_date=purchase.purchase_date,
                expiry_date=item.expiry_date,
                unit_cost=float(item.unit_price),
                quantity=item.approved_quantity,
                invoice_number=purchase.invoice_number,
                user_id=current_user.id
            )
            product = Product.query.get(item.product_id)
            if product:
                product.purchase_price = item.unit_price

        purchase.total_amount = sum(float(item.unit_price) * (item.approved_quantity or 0) for item in purchase.items)
        db.session.add(AuditLog(
            user_id=current_user.id,
            action='APPROVE_STOCK_REQUEST',
            module='PURCHASE_APPROVAL',
            details=f"Approved purchase {purchase.invoice_number}; adjustments: {', '.join(adjustments) or 'none'}"
        ))
        db.session.commit()
        flash(f"Stock request {purchase.invoice_number} approved.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Approval failed: {str(e)}", 'danger')
    return redirect(url_for('purchases.view_purchase', id=id))

@purchase_bp.route('/purchases/<int:id>/reject', methods=['POST'])
@login_required
@role_required('OWNER')
def reject_purchase(id):
    purchase = Purchase.query.get_or_404(id)
    if purchase.status != 'PENDING_APPROVAL':
        flash('This stock request is no longer pending.', 'warning')
        return redirect(url_for('purchases.view_purchase', id=id))

    reason = request.form.get('rejection_reason', '').strip()
    if not reason:
        flash('A rejection reason is required.', 'danger')
        return redirect(url_for('purchases.view_purchase', id=id))

    purchase.status = 'REJECTED'
    purchase.rejection_reason = reason
    purchase.approved_by = current_user.id
    purchase.approved_at = datetime.utcnow()
    db.session.add(AuditLog(
        user_id=current_user.id,
        action='REJECT_STOCK_REQUEST',
        module='PURCHASE_APPROVAL',
        details=f"Rejected purchase {purchase.invoice_number}: {reason}"
    ))
    db.session.commit()
    flash(f"Stock request {purchase.invoice_number} rejected.", 'warning')
    return redirect(url_for('purchases.view_purchase', id=id))
