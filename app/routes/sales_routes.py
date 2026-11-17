from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from app.models import db, Sale, User
from app.services.auth_service import role_required
from datetime import datetime, date

sales_bp = Blueprint('sales', __name__)

@sales_bp.route('/sales')
@login_required
def index():
    invoice_search = request.args.get('invoice', '').strip()
    cashier_id = request.args.get('cashier_id', type=int)
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()
    payment_method = request.args.get('payment_method', 'all')

    query = Sale.query

    # Cashier can only see permitted recent history if restricted, OWNER sees all
    if current_user.role == 'CASHIER':
        query = query.filter(Sale.cashier_id == current_user.id)
    elif cashier_id:
        query = query.filter(Sale.cashier_id == cashier_id)

    if invoice_search:
        query = query.filter(Sale.invoice_number.ilike(f"%{invoice_search}%"))

    if payment_method != 'all':
        query = query.filter(Sale.payment_method == payment_method)

    if start_date_str:
        try:
            s_date = date.fromisoformat(start_date_str)
            query = query.filter(Sale.transaction_date >= datetime.combine(s_date, datetime.min.time()))
        except ValueError:
            pass

    if end_date_str:
        try:
            e_date = date.fromisoformat(end_date_str)
            query = query.filter(Sale.transaction_date <= datetime.combine(e_date, datetime.max.time()))
        except ValueError:
            pass

    sales = query.order_by(Sale.transaction_date.desc()).limit(200).all()
    cashiers = User.query.filter_by(is_active=True).all() if current_user.is_owner else []

    return render_template(
        'sales/index.html',
        sales=sales,
        cashiers=cashiers,
        current_invoice=invoice_search,
        current_cashier=cashier_id,
        current_start=start_date_str,
        current_end=end_date_str,
        current_method=payment_method
    )
