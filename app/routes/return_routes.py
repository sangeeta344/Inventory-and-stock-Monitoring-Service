import random
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, Sale, SaleItem, Return, ReturnItem, Product
from app.services.inventory_service import InventoryService
from app.services.auth_service import log_audit

return_bp = Blueprint('returns', __name__)

@return_bp.route('/returns')
@login_required
def index():
    returns = Return.query.order_by(Return.return_date.desc()).all()
    return render_template('returns/index.html', returns=returns)

@return_bp.route('/returns/search-sale')
@login_required
def search_sale():
    invoice_number = request.args.get('invoice_number', '').strip()
    if not invoice_number:
        return jsonify({'success': False, 'message': 'Please enter an invoice number.'})

    sale = Sale.query.filter_by(invoice_number=invoice_number).first()
    if not sale:
        return jsonify({'success': False, 'message': f"No invoice found matching '{invoice_number}'."})

    items = []
    for item in sale.items:
        # Calculate how many were already returned
        already_returned = sum(ri.quantity for ri in item.return_items)
        max_returnable = max(0, item.quantity - already_returned)
        items.append({
            'sale_item_id': item.id,
            'product_id': item.product_id,
            'product_name': item.product.name,
            'barcode': item.product.barcode,
            'unit_price': float(item.unit_price),
            'quantity_sold': item.quantity,
            'already_returned': already_returned,
            'max_returnable': max_returnable
        })

    return jsonify({
        'success': True,
        'sale': {
            'id': sale.id,
            'invoice_number': sale.invoice_number,
            'transaction_date': sale.transaction_date.strftime('%Y-%m-%d %H:%M'),
            'customer_name': sale.customer_name,
            'final_amount': float(sale.final_amount),
            'items': items
        }
    })

@return_bp.route('/returns/new', methods=['GET', 'POST'])
@login_required
def new_return():
    if request.method == 'POST':
        sale_id = request.form.get('sale_id', type=int)
        notes = request.form.get('notes', '').strip()

        sale_item_ids = request.form.getlist('sale_item_id[]')
        return_quantities = request.form.getlist('return_quantity[]')
        conditions = request.form.getlist('condition[]')
        reasons = request.form.getlist('reason[]')

        sale = Sale.query.get(sale_id)
        if not sale:
            flash('Invalid sale transaction selected.', 'danger')
            return redirect(url_for('returns.new_return'))

        date_str = datetime.utcnow().strftime('%Y%m%d')
        return_number = f"RET-{date_str}-{random.randint(1000, 9999)}"

        total_refund = 0.0
        return_items_to_save = []

        for i in range(len(sale_item_ids)):
            s_item_id = int(sale_item_ids[i])
            qty = int(return_quantities[i])
            if qty <= 0:
                continue

            sale_item = SaleItem.query.get(s_item_id)
            if not sale_item or sale_item.sale_id != sale.id:
                continue

            already_returned = sum(ri.quantity for ri in sale_item.return_items)
            max_returnable = sale_item.quantity - already_returned
            if qty > max_returnable:
                flash(f"Cannot return {qty} of {sale_item.product.name}. Max returnable is {max_returnable}.", 'danger')
                return redirect(url_for('returns.new_return'))

            cond = conditions[i] if i < len(conditions) else 'RESELLABLE'
            rsn = reasons[i].strip() if i < len(reasons) else 'Customer return'
            refund_amount = round(float(sale_item.unit_price) * qty, 2)
            total_refund += refund_amount

            return_items_to_save.append({
                'sale_item': sale_item,
                'quantity': qty,
                'refund_amount': refund_amount,
                'condition': cond,
                'reason': rsn
            })

        if not return_items_to_save:
            flash('No items were selected for return.', 'warning')
            return redirect(url_for('returns.new_return'))

        try:
            return_record = Return(
                return_number=return_number,
                sale_id=sale.id,
                cashier_id=current_user.id,
                return_date=datetime.utcnow(),
                total_refund_amount=total_refund,
                notes=notes
            )
            db.session.add(return_record)
            db.session.flush()

            for item_data in return_items_to_save:
                s_item = item_data['sale_item']
                r_item = ReturnItem(
                    return_id=return_record.id,
                    sale_item_id=s_item.id,
                    product_id=s_item.product_id,
                    quantity=item_data['quantity'],
                    refund_amount=item_data['refund_amount'],
                    condition=item_data['condition'],
                    reason=item_data['reason']
                )
                db.session.add(r_item)

                # Process inventory adjustment
                InventoryService.process_return_item(
                    sale_item=s_item,
                    quantity=item_data['quantity'],
                    condition=item_data['condition'],
                    reason=item_data['reason'],
                    return_number=return_number,
                    user_id=current_user.id
                )

            db.session.commit()
            log_audit(current_user.id, 'PROCESS_RETURN', 'RETURN_MANAGEMENT', f"Processed return {return_number} (Refund: ${total_refund})")
            flash(f"Return {return_number} processed successfully! Refund Amount: ${total_refund:.2f}", 'success')
            return redirect(url_for('returns.index'))

        except Exception as e:
            db.session.rollback()
            flash(f"Return failed: {str(e)}", 'danger')
            return redirect(url_for('returns.new_return'))

    return render_template('returns/form.html')
