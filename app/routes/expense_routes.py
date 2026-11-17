from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, Expense
from app.services.auth_service import role_required, log_audit
from datetime import date

expense_bp = Blueprint('expenses', __name__)

@expense_bp.route('/expenses')
@login_required
@role_required('OWNER')
def index():
    expenses = Expense.query.order_by(Expense.expense_date.desc(), Expense.id.desc()).all()
    categories = ['RENT', 'ELECTRICITY', 'SALARY', 'MAINTENANCE', 'SUPPLIES', 'OTHER']
    return render_template('expenses/index.html', expenses=expenses, categories=categories)

@expense_bp.route('/expenses/add', methods=['POST'])
@login_required
@role_required('OWNER')
def add_expense():
    title = request.form.get('title', '').strip()
    category = request.form.get('category', 'OTHER')
    amount = request.form.get('amount', type=float, default=0.0)
    expense_date_str = request.form.get('expense_date', '').strip()
    notes = request.form.get('notes', '').strip()

    if not title or amount <= 0:
        flash('Valid title and expense amount are required.', 'danger')
        return redirect(url_for('expenses.index'))

    try:
        exp_date = date.fromisoformat(expense_date_str) if expense_date_str else date.today()
    except ValueError:
        exp_date = date.today()

    expense = Expense(
        title=title,
        category=category,
        amount=amount,
        expense_date=exp_date,
        notes=notes,
        created_by=current_user.id
    )
    db.session.add(expense)
    db.session.commit()
    log_audit(current_user.id, 'ADD_EXPENSE', 'EXPENSE_MANAGEMENT', f"Logged {category} expense: {title} (${amount})")
    flash(f"Expense '{title}' (${amount:.2f}) added successfully.", 'success')
    return redirect(url_for('expenses.index'))

@expense_bp.route('/expenses/delete/<int:id>', methods=['POST'])
@login_required
@role_required('OWNER')
def delete_expense(id):
    expense = Expense.query.get_or_404(id)
    title = expense.title
    db.session.delete(expense)
    db.session.commit()
    log_audit(current_user.id, 'DELETE_EXPENSE', 'EXPENSE_MANAGEMENT', f"Deleted expense: {title}")
    flash(f"Expense '{title}' deleted.", 'info')
    return redirect(url_for('expenses.index'))
