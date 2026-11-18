from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app.models import db, Product, Category, Sale, SaleItem
from app.services.billing_service import BillingService
from app.services.auth_service import log_audit, role_required
from datetime import datetime

billing_bp = Blueprint('billing', __name__)

@billing_bp.route('/billing')
@login_required
@role_required('CASHIER')
def pos():
    """
    Main Point-of-Sale (POS) Billing Terminal.
    Accessible to both CASHIER and OWNER roles.
    """
    categories = Category.query.filter_by(is_active=True).order_by(Category.name.asc()).all()
    # Featured quick products with stock
    popular_products = Product.query.filter(Product.is_active == True, Product.current_stock > 0)\
                                    .order_by(Product.current_stock.desc()).limit(12).all()

    default_tax_rate = current_app.config.get('STORE_DEFAULT_TAX_RATE', 5.0)

    return render_template(
        'billing/index.html',
        categories=categories,
        popular_products=popular_products,
        default_tax_rate=default_tax_rate
    )

@billing_bp.route('/api/billing/product-lookup/<barcode>')
@login_required
@role_required('CASHIER')
def lookup_barcode(barcode):
    """
    API endpoint invoked immediately after mobile camera or barcode scanner scans a barcode.
    Returns product details and live sellable stock.
    """
    product_data = BillingService.find_product_by_barcode(barcode)
    if not product_data:
        return jsonify({
            'success': False,
            'message': f"No active product found for barcode '{barcode}'"
        }), 404

    if product_data['is_out_of_stock']:
        return jsonify({
            'success': False,
            'message': f"Product '{product_data['name']}' is out of stock!",
            'product': product_data
        }), 400

    return jsonify({
        'success': True,
        'product': product_data
    })

@billing_bp.route('/api/billing/search-products')
@login_required
@role_required('CASHIER')
def search_products():
    """
    Typeahead search for products by name, barcode, or category.
    """
    query_str = request.args.get('q', '').strip()
    if not query_str or len(query_str) < 2:
        return jsonify({'results': []})

    pattern = f"%{query_str}%"
    products = Product.query.filter(
        Product.is_active == True,
        db.or_(
            Product.name.ilike(pattern),
            Product.barcode.ilike(pattern)
        )
    ).limit(10).all()

    results = []
    for p in products:
        results.append({
            'id': p.id,
            'name': p.name,
            'barcode': p.barcode,
            'selling_price': float(p.selling_price),
            'current_stock': p.current_stock,
            'unit_of_measure': p.unit_of_measure,
            'is_out_of_stock': p.current_stock <= 0
        })

    return jsonify({'results': results})

@billing_bp.route('/api/billing/checkout', methods=['POST'])
@login_required
@role_required('CASHIER')
def checkout():
    """
    Processes final cart checkout and generates invoice.
    Uses FEFO stock deduction and database transaction.
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'message': 'Invalid or empty request data'}), 400

        cart_items = data.get('cart', [])
        if not cart_items:
            return jsonify({'success': False, 'message': 'Cart is empty. Please add items before checking out.'}), 400

        customer_name = (data.get('customer_name') or 'Walk-in Customer').strip()
        customer_phone = (data.get('customer_phone') or '').strip()
        payment_method = (data.get('payment_method') or 'CASH').upper()
        
        try:
            discount_amount = float(data.get('discount_amount') or 0.0)
        except (ValueError, TypeError):
            discount_amount = 0.0

        try:
            default_rate = current_app.config.get('STORE_DEFAULT_TAX_RATE', 5.0)
            tax_rate = float(data.get('tax_rate', default_rate) or 0.0)
        except (ValueError, TypeError):
            tax_rate = 5.0

        success, result = BillingService.process_checkout(
            cashier_id=current_user.id,
            cart_items=cart_items,
            customer_name=customer_name,
            customer_phone=customer_phone,
            payment_method=payment_method,
            discount_amount=discount_amount,
            tax_rate=tax_rate
        )

        if not success:
            return jsonify({'success': False, 'message': result}), 400

        sale = result
        try:
            log_audit(
                current_user.id,
                'BILLING_CHECKOUT',
                'POS_BILLING',
                f"Completed sale {sale.invoice_number} for amount ${sale.final_amount} (Method: {payment_method})"
            )
        except Exception as audit_err:
            print(f"[AUDIT LOG WARNING] Failed to record checkout audit: {audit_err}")

        return jsonify({
            'success': True,
            'invoice_number': sale.invoice_number,
            'final_amount': float(sale.final_amount),
            'redirect_url': url_for('billing.view_invoice', invoice_number=sale.invoice_number)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f"Checkout error: {str(e)}"}), 500

@billing_bp.route('/billing/invoice/<invoice_number>')
@login_required
def view_invoice(invoice_number):
    """
    Digital invoice view with instant print and PDF download buttons.
    """
    sale = Sale.query.filter_by(invoice_number=invoice_number).first_or_404()
    return render_template('billing/invoice.html', sale=sale)
