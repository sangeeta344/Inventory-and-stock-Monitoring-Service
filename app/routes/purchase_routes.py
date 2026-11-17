from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, Purchase, PurchaseItem, Supplier, Product
from app.services.auth_service import role_required, log_audit
from app.services.inventory_service import InventoryService
from datetime import date, datetime

purchase_bp = Blueprint('purchases', __name__)

@purchase_bp.route('/purchases')
@login_required
@role_required('OWNER')
def index():
    purchases = Purchase.query.order_by(Purchase.purchase_date.desc(), Purchase.id.desc()).all()
    return render_template('purchases/index.html', purchases=purchases)

@purchase_bp.route('/purchases/new', methods=['GET', 'POST'])
@login_required
@role_required('OWNER')
def new_purchase():
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

        if not supplier_id or not invoice_number or not product_ids:
            flash('Supplier, Invoice Number, and at least one product are required.', 'danger')
            return redirect(url_for('purchases.new_purchase'))

        try:
            purchase_date = date.fromisoformat(purchase_date_str) if purchase_date_str else date.today()
        except ValueError:
            purchase_date = date.today()

        try:
            purchase = Purchase(
                supplier_id=supplier_id,
                invoice_number=invoice_number,
                purchase_date=purchase_date,
                payment_status=payment_status,
                status='RECEIVED', # Marked as received to auto-stock
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

                # Automatically update inventory and create batch
                InventoryService.receive_purchase_batch(
                    product_id=prod_id,
                    supplier_id=supplier_id,
                    purchase_item_id=p_item.id,
                    batch_number=b_num,
                    purchase_date=purchase_date,
                    expiry_date=exp_date,
                    unit_cost=price,
                    quantity=qty,
                    invoice_number=invoice_number,
                    user_id=current_user.id
                )

                # Update product default purchase price if desired
                product = Product.query.get(prod_id)
                if product:
                    product.purchase_price = price

            purchase.total_amount = total_amount
            db.session.commit()

            log_audit(current_user.id, 'CREATE_PURCHASE', 'PURCHASE_MANAGEMENT', f"Recorded purchase {invoice_number} total ${total_amount}")
            flash(f"Purchase order {invoice_number} successfully received. Inventory stock automatically increased!", 'success')
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
@role_required('OWNER')
def view_purchase(id):
    purchase = Purchase.query.get_or_404(id)
    return render_template('purchases/view.html', purchase=purchase)
