from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for, abort
from flask_login import current_user, login_required

from app.models import (
    db,
    AuditLog,
    Product,
    Purchase,
    PurchaseItem,
    Supplier,
    StockRequirement,
    StockRequirementItem,
    GoodsReceivingReport,
    GoodsReceivingItem,
    GoodsReceivingCorrection,
    GoodsReceivingCorrectionItem,
    SupplierInvoice,
    SupplierPayment,
    InventoryBatch,
    StockMovement,
)
from app.services.auth_service import role_required
from app.services.inventory_service import InventoryService
from app.services.procurement_service import ProcurementService


procurement_bp = Blueprint('procurement', __name__)


@procurement_bp.route('/requirements')
@login_required
@role_required('OWNER', 'CASHIER')
def requirements_index():
    query = StockRequirement.query
    if current_user.is_cashier:
        query = query.filter(StockRequirement.requested_by == current_user.id)
    requirements = query.order_by(StockRequirement.created_at.desc()).all()
    return render_template('procurement/requirements/index.html', requirements=requirements)


@procurement_bp.route('/requirements/new', methods=['GET', 'POST'])
@login_required
@role_required('CASHIER')
def requirement_new():
    if request.method == 'POST':
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        notes = request.form.get('notes', '').strip()
        if not product_ids:
            flash('Select at least one product.', 'danger')
            return redirect(url_for('procurement.requirement_new'))

        try:
            requirement = StockRequirement(
                request_number=ProcurementService.next_number('REQ', StockRequirement, 'request_number'),
                requested_by=current_user.id,
                status='PENDING',
                notes=notes
            )
            db.session.add(requirement)
            db.session.flush()
            for index, product_id in enumerate(product_ids):
                product = Product.query.get(int(product_id))
                quantity = int(quantities[index])
                if not product or quantity <= 0:
                    raise ValueError('Invalid product or quantity.')
                db.session.add(StockRequirementItem(
                    stock_requirement_id=requirement.id,
                    product_id=product.id,
                    original_quantity=quantity,
                    unit=product.unit_of_measure
                ))
            ProcurementService.log(current_user.id, 'CREATE_STOCK_REQUIREMENT', 'PROCUREMENT', f"Created stock requirement {requirement.request_number}")
            db.session.commit()
            flash(f'Stock requirement {requirement.request_number} submitted.', 'success')
            return redirect(url_for('procurement.requirements_index'))
        except Exception as exc:
            db.session.rollback()
            flash(f'Could not submit stock requirement: {exc}', 'danger')
            return redirect(url_for('procurement.requirement_new'))

    products = Product.query.filter_by(is_active=True).order_by(Product.name.asc()).all()
    return render_template('procurement/requirements/form.html', products=products)


@procurement_bp.route('/requirements/<int:id>')
@login_required
@role_required('OWNER', 'CASHIER')
def requirement_view(id):
    requirement = StockRequirement.query.get_or_404(id)
    if current_user.is_cashier and requirement.requested_by != current_user.id:
        abort(403)
    return render_template('procurement/requirements/view.html', requirement=requirement)


@procurement_bp.route('/requirements/<int:id>/approve', methods=['POST'])
@login_required
@role_required('OWNER')
def requirement_approve(id):
    requirement = StockRequirement.query.get_or_404(id)
    if requirement.status != 'PENDING':
        flash('This requirement is not pending.', 'warning')
        return redirect(url_for('procurement.requirement_view', id=id))
    try:
        for item in requirement.items:
            approved = request.form.get(f'approved_quantity_{item.id}', type=int)
            if approved is None or approved < 0:
                raise ValueError('Approved quantity is invalid.')
            if approved != item.original_quantity:
                reason = request.form.get(f'adjustment_reason_{item.id}', '').strip()
                if not reason:
                    raise ValueError('A reason is required for every quantity adjustment.')
                item.quantity_adjustment_reason = reason
            item.approved_quantity = approved
        requirement.status = 'APPROVED'
        requirement.reviewed_by = current_user.id
        requirement.reviewed_at = datetime.utcnow()
        ProcurementService.log(current_user.id, 'APPROVE_STOCK_REQUIREMENT', 'PROCUREMENT', f"Approved {requirement.request_number}")
        db.session.commit()
        flash('Stock requirement approved.', 'success')
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), 'danger')
    return redirect(url_for('procurement.requirement_view', id=id))


@procurement_bp.route('/requirements/<int:id>/reject', methods=['POST'])
@login_required
@role_required('OWNER')
def requirement_reject(id):
    requirement = StockRequirement.query.get_or_404(id)
    if requirement.status != 'PENDING':
        flash('This requirement is not pending.', 'warning')
        return redirect(url_for('procurement.requirement_view', id=id))
    reason = request.form.get('rejection_reason', '').strip()
    if not reason:
        flash('A rejection reason is required.', 'danger')
        return redirect(url_for('procurement.requirement_view', id=id))
    requirement.status = 'REJECTED'
    requirement.rejection_reason = reason
    requirement.reviewed_by = current_user.id
    requirement.reviewed_at = datetime.utcnow()
    ProcurementService.log(current_user.id, 'REJECT_STOCK_REQUIREMENT', 'PROCUREMENT', f"Rejected {requirement.request_number}: {reason}")
    db.session.commit()
    flash('Stock requirement rejected.', 'warning')
    return redirect(url_for('procurement.requirement_view', id=id))


@procurement_bp.route('/purchase-orders')
@login_required
@role_required('OWNER')
def purchase_orders_index():
    purchases = Purchase.query.order_by(Purchase.purchase_date.desc(), Purchase.id.desc()).all()
    return render_template('procurement/purchase_orders/index.html', purchases=purchases)


@procurement_bp.route('/purchase-orders/new', methods=['GET', 'POST'])
@login_required
@role_required('OWNER')
def purchase_order_new():
    if request.method == 'POST':
        supplier_id = request.form.get('supplier_id', type=int)
        requirement_id = request.form.get('stock_requirement_id', type=int)
        invoice_number = request.form.get('invoice_number', '').strip()
        purchase_date = request.form.get('purchase_date', '').strip()
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('unit_price[]')
        supplier = Supplier.query.get(supplier_id) if supplier_id else None
        if not supplier or not invoice_number or not product_ids:
            flash('Supplier, invoice and at least one product are required.', 'danger')
            return redirect(url_for('procurement.purchase_order_new'))
        try:
            order_date = date.fromisoformat(purchase_date) if purchase_date else date.today()
            purchase = Purchase(
                supplier_id=supplier.id,
                invoice_number=invoice_number,
                purchase_date=order_date,
                total_amount=0,
                payment_status='PENDING',
                status='ORDERED',
                order_status='ORDERED',
                stock_requirement_id=requirement_id,
                ordered_by=current_user.id,
                ordered_at=datetime.utcnow(),
                created_by=current_user.id
            )
            db.session.add(purchase)
            db.session.flush()
            total = Decimal('0')
            for index, product_id in enumerate(product_ids):
                product = Product.query.get(int(product_id))
                qty = int(quantities[index])
                price = Decimal(prices[index])
                if not product or qty <= 0 or price < 0:
                    raise ValueError('Invalid purchase order line.')
                subtotal = Decimal(qty) * price
                total += subtotal
                db.session.add(PurchaseItem(
                    purchase_id=purchase.id,
                    product_id=product.id,
                    batch_number=f"PO-{invoice_number[-6:]}-{index + 1}",
                    quantity=qty,
                    unit_price=price,
                    subtotal=subtotal
                ))
            purchase.total_amount = total
            if requirement_id:
                requirement = StockRequirement.query.get(requirement_id)
                if requirement:
                    requirement.status = 'ORDER_CREATED'
            ProcurementService.log(current_user.id, 'CREATE_PURCHASE_ORDER', 'PROCUREMENT', f"Created purchase order {invoice_number}")
            db.session.commit()
            flash('Purchase order created.', 'success')
            return redirect(url_for('procurement.purchase_orders_index'))
        except Exception as exc:
            db.session.rollback()
            flash(f'Could not create purchase order: {exc}', 'danger')
            return redirect(url_for('procurement.purchase_order_new'))

    requirements = StockRequirement.query.filter_by(status='APPROVED').order_by(StockRequirement.created_at.desc()).all()
    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.company_name.asc()).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name.asc()).all()
    return render_template('procurement/purchase_orders/form.html', requirements=requirements, suppliers=suppliers, products=products)


@procurement_bp.route('/purchase-orders/<int:id>/receive', methods=['GET', 'POST'])
@login_required
@role_required('CASHIER')
def receive_order(id):
    purchase = Purchase.query.get_or_404(id)
    if purchase.order_status not in ('ORDERED', 'PARTIALLY_RECEIVED', None):
        flash('This purchase order is not eligible for receiving.', 'warning')
        return redirect(url_for('procurement.receiving_reports_index'))
    if request.method == 'POST':
        delivery_date = request.form.get('delivery_date', '').strip()
        invoice_number = request.form.get('invoice_number', '').strip()
        delivery_reference = request.form.get('delivery_reference', '').strip()
        notes = request.form.get('notes', '').strip()
        item_ids = request.form.getlist('purchase_item_id[]')
        delivered_values = request.form.getlist('delivered[]')
        accepted_values = request.form.getlist('accepted[]')
        damaged_values = request.form.getlist('damaged[]')
        rejected_values = request.form.getlist('rejected[]')
        batch_numbers = request.form.getlist('batch_number[]')
        expiry_dates = request.form.getlist('expiry_date[]')
        reasons = request.form.getlist('reason[]')
        if not item_ids:
            flash('No receiving items submitted.', 'danger')
            return redirect(url_for('procurement.receive_order', id=id))
        try:
            report = GoodsReceivingReport(
                report_number=ProcurementService.next_number('GRR', GoodsReceivingReport, 'report_number'),
                purchase_id=purchase.id,
                submitted_by=current_user.id,
                status='SUBMITTED',
                invoice_number=invoice_number or purchase.invoice_number,
                delivery_reference=delivery_reference,
                delivery_date=date.fromisoformat(delivery_date) if delivery_date else date.today(),
                notes=notes
            )
            db.session.add(report)
            db.session.flush()
            for index, item_id in enumerate(item_ids):
                item = PurchaseItem.query.get(int(item_id))
                if not item or item.purchase_id != purchase.id:
                    raise ValueError('Invalid purchase order item.')
                delivered = int(delivered_values[index])
                accepted = int(accepted_values[index])
                damaged = int(damaged_values[index])
                rejected = int(rejected_values[index])
                if delivered < 0 or accepted < 0 or damaged < 0 or rejected < 0:
                    raise ValueError('Quantity cannot be negative.')
                if delivered != accepted + damaged + rejected:
                    raise ValueError('Delivered must equal accepted + damaged + rejected.')
                cumulative_delivered = sum(
                    ri.delivered_quantity for ri in GoodsReceivingItem.query.join(GoodsReceivingReport).filter(
                        GoodsReceivingItem.purchase_item_id == item.id,
                        GoodsReceivingReport.inventory_applied == True
                    ).all()
                )
                remaining = item.quantity - cumulative_delivered
                if delivered > remaining:
                    raise ValueError(f'Delivery exceeds outstanding quantity for {item.product.name}.')
                outstanding = item.quantity - (cumulative_delivered + delivered)
                if accepted > 0 and not batch_numbers[index].strip():
                    raise ValueError('Batch number is required for accepted goods.')
                exp_date = None
                if expiry_dates[index].strip():
                    exp_date = date.fromisoformat(expiry_dates[index].strip())
                receiving_item = GoodsReceivingItem(
                    receiving_report_id=report.id,
                    purchase_item_id=item.id,
                    product_id=item.product_id,
                    ordered_quantity=item.quantity,
                    delivered_quantity=delivered,
                    accepted_quantity=accepted,
                    damaged_quantity=damaged,
                    rejected_quantity=rejected,
                    outstanding_quantity=outstanding,
                    batch_number=batch_numbers[index].strip() or None,
                    expiry_date=exp_date,
                    unit_cost=item.unit_price,
                    reason=reasons[index].strip() or None
                )
                db.session.add(receiving_item)
                db.session.flush()
                if accepted > 0:
                    InventoryService.receive_purchase_batch(
                        product_id=item.product_id,
                        supplier_id=purchase.supplier_id,
                        purchase_item_id=item.id,
                        batch_number=receiving_item.batch_number,
                        purchase_date=report.delivery_date,
                        expiry_date=receiving_item.expiry_date,
                        unit_cost=float(item.unit_price),
                        quantity=accepted,
                        invoice_number=invoice_number or purchase.invoice_number,
                        user_id=current_user.id
                    )
            report.inventory_applied = True
            report.inventory_applied_at = datetime.utcnow()
            all_delivered = sum(
                ri.delivered_quantity for ri in GoodsReceivingItem.query.join(GoodsReceivingReport).filter(
                    GoodsReceivingItem.purchase_item_id.in_([i.id for i in purchase.items]),
                    GoodsReceivingReport.inventory_applied == True
                ).all()
            )
            purchase.order_status = 'RECEIVED' if all_delivered >= sum(i.quantity for i in purchase.items) else 'PARTIALLY_RECEIVED'
            ProcurementService.log(current_user.id, 'SUBMIT_GOODS_RECEIVING', 'PROCUREMENT', f"Submitted receiving report {report.report_number}")
            db.session.commit()
            flash(f'Receiving report {report.report_number} submitted and accepted stock added.', 'success')
            return redirect(url_for('procurement.receiving_reports_index'))
        except Exception as exc:
            db.session.rollback()
            flash(f'Receiving report failed: {exc}', 'danger')
    return render_template('procurement/receiving/form.html', purchase=purchase)


@procurement_bp.route('/receiving-reports')
@login_required
@role_required('OWNER', 'CASHIER')
def receiving_reports_index():
    query = GoodsReceivingReport.query
    if current_user.is_cashier:
        query = query.filter(GoodsReceivingReport.submitted_by == current_user.id)
    reports = query.order_by(GoodsReceivingReport.submitted_at.desc()).all()
    return render_template('procurement/receiving/index.html', reports=reports)


@procurement_bp.route('/receiving-reports/<int:id>')
@login_required
@role_required('OWNER', 'CASHIER')
def receiving_report_view(id):
    report = GoodsReceivingReport.query.get_or_404(id)
    if current_user.is_cashier and report.submitted_by != current_user.id:
        abort(403)
    return render_template('procurement/receiving/view.html', report=report)


@procurement_bp.route('/receiving-reports/<int:id>/review', methods=['POST'])
@login_required
@role_required('OWNER')
def receiving_report_review(id):
    report = GoodsReceivingReport.query.get_or_404(id)
    action = request.form.get('action', '').strip()
    reason = request.form.get('reason', '').strip()
    if action not in ('APPROVED', 'CORRECTION_REQUIRED'):
        flash('Invalid review action.', 'danger')
        return redirect(url_for('procurement.receiving_report_view', id=id))
    if action == 'CORRECTION_REQUIRED' and not reason:
        flash('A correction reason is required.', 'danger')
        return redirect(url_for('procurement.receiving_report_view', id=id))
    report.status = action
    report.reviewed_by = current_user.id
    report.reviewed_at = datetime.utcnow()
    if reason:
        report.notes = (report.notes + '\n' if report.notes else '') + f"Review: {reason}"
    ProcurementService.log(current_user.id, 'REVIEW_GOODS_RECEIVING', 'PROCUREMENT', f"Reviewed receiving report {report.report_number}: {action}")
    db.session.commit()
    flash('Receiving report reviewed.', 'success')
    return redirect(url_for('procurement.receiving_report_view', id=id))


@procurement_bp.route('/receiving-reports/<int:id>/correct', methods=['POST'])
@login_required
@role_required('OWNER', 'CASHIER')
def receiving_report_correct(id):
    report = GoodsReceivingReport.query.get_or_404(id)
    if current_user.is_cashier and report.submitted_by != current_user.id:
        abort(403)
    reason = request.form.get('correction_reason', '').strip()
    if not reason:
        flash('A correction reason is required.', 'danger')
        return redirect(url_for('procurement.receiving_report_view', id=id))
    try:
        correction = GoodsReceivingCorrection(
            original_report_id=report.id,
            corrected_by=current_user.id,
            created_by_owner=current_user.is_owner,
            correction_reason=reason,
            status='SUBMITTED'
        )
        db.session.add(correction)
        db.session.flush()
        for item in report.items:
            accepted = request.form.get(f'accepted_{item.id}', type=int)
            damaged = request.form.get(f'damaged_{item.id}', type=int)
            rejected = request.form.get(f'rejected_{item.id}', type=int)
            if accepted is None or damaged is None or rejected is None:
                raise ValueError('All corrected quantities are required.')
            if accepted < 0 or damaged < 0 or rejected < 0:
                raise ValueError('Corrected quantities cannot be negative.')
            delivered = accepted + damaged + rejected
            if delivered != item.delivered_quantity:
                raise ValueError('Corrected delivered quantity must remain equal to accepted + damaged + rejected.')
            correction_item = GoodsReceivingCorrectionItem(
                correction_id=correction.id,
                receiving_item_id=item.id,
                before_accepted_quantity=item.accepted_quantity,
                after_accepted_quantity=accepted,
                before_damaged_quantity=item.damaged_quantity,
                after_damaged_quantity=damaged,
                before_rejected_quantity=item.rejected_quantity,
                after_rejected_quantity=rejected
            )
            db.session.add(correction_item)
            delta = accepted - item.accepted_quantity
            if delta > 0:
                batch = InventoryService.receive_purchase_batch(
                    product_id=item.product_id,
                    supplier_id=report.purchase.supplier_id,
                    purchase_item_id=item.purchase_item_id,
                    batch_number=f"{item.batch_number or 'RCV'}-CORR-{correction.id}",
                    purchase_date=report.delivery_date,
                    expiry_date=item.expiry_date,
                    unit_cost=float(item.unit_cost),
                    quantity=delta,
                    invoice_number=report.invoice_number or report.purchase.invoice_number,
                    user_id=current_user.id
                )
                movement = StockMovement.query.filter_by(batch_id=batch.id).order_by(StockMovement.id.desc()).first()
                correction_item.stock_movement_id = movement.id if movement else None
            elif delta < 0:
                product = Product.query.get(item.product_id)
                batch = InventoryBatch.query.filter(
                    InventoryBatch.product_id == item.product_id,
                    InventoryBatch.purchase_item_id == item.purchase_item_id,
                    InventoryBatch.quantity_remaining > 0
                ).order_by(InventoryBatch.created_at.desc()).first()
                if not batch or batch.quantity_remaining < abs(delta):
                    raise ValueError('Insufficient corrected batch quantity.')
                batch.quantity_remaining -= abs(delta)
                product.current_stock -= abs(delta)
                movement = StockMovement(
                    product_id=product.id,
                    batch_id=batch.id,
                    movement_type='MANUAL_ADJUSTMENT',
                    reference_id=f"CORR-{correction.id}",
                    quantity_change=-abs(delta),
                    quantity_after=product.current_stock,
                    notes=f"Receiving correction for report {report.report_number}: accepted quantity reduced",
                    created_by=current_user.id
                )
                db.session.add(movement)
                db.session.flush()
                correction_item.stock_movement_id = movement.id
            item.accepted_quantity = accepted
            item.damaged_quantity = damaged
            item.rejected_quantity = rejected
        correction.status = 'APPLIED'
        correction.applied_at = datetime.utcnow()
        report.status = 'CORRECTED'
        ProcurementService.log(current_user.id, 'CORRECT_GOODS_RECEIVING', 'PROCUREMENT', f"Corrected receiving report {report.report_number}: {reason}")
        db.session.commit()
        flash('Receiving correction applied and inventory reconciled.', 'success')
    except Exception as exc:
        db.session.rollback()
        flash(f'Correction failed: {exc}', 'danger')
    return redirect(url_for('procurement.receiving_report_view', id=id))


@procurement_bp.route('/suppliers/<int:supplier_id>/payments', methods=['GET', 'POST'])
@login_required
@role_required('OWNER')
def supplier_payments(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    if request.method == 'POST':
        purchase_id = request.form.get('purchase_id', type=int)
        invoice_id = request.form.get('supplier_invoice_id', type=int)
        amount = request.form.get('amount', type=float)
        if amount is None or amount <= 0:
            flash('Payment amount must be greater than zero.', 'danger')
            return redirect(url_for('procurement.supplier_payments', supplier_id=supplier_id))
        try:
            target_purchase = Purchase.query.get(purchase_id) if purchase_id else None
            target_invoice = SupplierInvoice.query.get(invoice_id) if invoice_id else None
            if target_purchase and target_purchase.supplier_id != supplier.id:
                raise ValueError('Purchase belongs to another supplier.')
            if target_invoice and target_invoice.supplier_id != supplier.id:
                raise ValueError('Invoice belongs to another supplier.')
            payable = Decimal(str(target_invoice.total_amount)) if target_invoice else (Decimal(str(target_purchase.total_amount)) if target_purchase else Decimal('0'))
            existing_query = SupplierPayment.query.filter_by(supplier_id=supplier.id)
            if target_invoice:
                existing_query = existing_query.filter_by(supplier_invoice_id=target_invoice.id)
            elif target_purchase:
                existing_query = existing_query.filter_by(purchase_id=target_purchase.id)
            paid = sum((Decimal(str(p.amount)) for p in existing_query.all()), Decimal('0'))
            if Decimal(str(amount)) > payable - paid:
                raise ValueError('Payment exceeds outstanding balance.')
            payment = SupplierPayment(
                payment_number=ProcurementService.next_number('PAY', SupplierPayment, 'payment_number'),
                supplier_id=supplier.id,
                purchase_id=purchase_id,
                supplier_invoice_id=invoice_id,
                amount=amount,
                payment_date=date.fromisoformat(request.form.get('payment_date', '').strip()) if request.form.get('payment_date', '').strip() else date.today(),
                payment_method=request.form.get('payment_method', 'BANK').strip().upper(),
                reference_number=request.form.get('reference_number', '').strip() or None,
                recorded_by=current_user.id,
                notes=request.form.get('notes', '').strip() or None
            )
            db.session.add(payment)
            ProcurementService.log(current_user.id, 'RECORD_SUPPLIER_PAYMENT', 'PROCUREMENT', f"Recorded payment {payment.payment_number} for supplier {supplier.company_name}")
            db.session.commit()
            flash('Supplier payment recorded.', 'success')
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), 'danger')
        return redirect(url_for('procurement.supplier_payments', supplier_id=supplier_id))

    purchases = Purchase.query.filter_by(supplier_id=supplier.id).order_by(Purchase.purchase_date.desc()).all()
    payments = SupplierPayment.query.filter_by(supplier_id=supplier.id).order_by(SupplierPayment.payment_date.desc()).all()
    invoices = SupplierInvoice.query.filter_by(supplier_id=supplier.id).order_by(SupplierInvoice.invoice_date.desc()).all()
    return render_template('procurement/payments/index.html', supplier=supplier, purchases=purchases, payments=payments, invoices=invoices)


@procurement_bp.route('/supplier-invoices/new', methods=['GET', 'POST'])
@login_required
@role_required('OWNER')
def supplier_invoice_new():
    if request.method == 'POST':
        supplier_id = request.form.get('supplier_id', type=int)
        purchase_id = request.form.get('purchase_id', type=int)
        invoice_number = request.form.get('invoice_number', '').strip()
        invoice_date = request.form.get('invoice_date', '').strip()
        due_date = request.form.get('due_date', '').strip()
        total_amount = request.form.get('total_amount', type=float)
        supplier = Supplier.query.get(supplier_id) if supplier_id else None
        if not supplier or not invoice_number or total_amount is None or total_amount <= 0:
            flash('Supplier, invoice number and positive total are required.', 'danger')
            return redirect(url_for('procurement.supplier_invoice_new'))
        if purchase_id:
            purchase = Purchase.query.get(purchase_id)
            if not purchase or purchase.supplier_id != supplier.id:
                flash('Purchase belongs to a different supplier.', 'danger')
                return redirect(url_for('procurement.supplier_invoice_new'))
        try:
            invoice = SupplierInvoice(
                invoice_number=invoice_number,
                supplier_id=supplier.id,
                purchase_id=purchase_id,
                invoice_date=date.fromisoformat(invoice_date) if invoice_date else date.today(),
                due_date=date.fromisoformat(due_date) if due_date else None,
                total_amount=total_amount,
                status='PENDING',
                created_by=current_user.id
            )
            db.session.add(invoice)
            ProcurementService.log(current_user.id, 'CREATE_SUPPLIER_INVOICE', 'PROCUREMENT', f"Created supplier invoice {invoice_number}")
            db.session.commit()
            flash('Supplier invoice created.', 'success')
            return redirect(url_for('procurement.supplier_payments', supplier_id=supplier.id))
        except Exception as exc:
            db.session.rollback()
            flash(f'Could not create supplier invoice: {exc}', 'danger')
    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.company_name.asc()).all()
    purchases = Purchase.query.order_by(Purchase.purchase_date.desc()).all()
    return render_template('procurement/invoices/form.html', suppliers=suppliers, purchases=purchases)
