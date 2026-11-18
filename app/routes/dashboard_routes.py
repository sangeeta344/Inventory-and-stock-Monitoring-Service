from flask import Blueprint, render_template, redirect, url_for, jsonify, request, flash
from flask_login import login_required, current_user
from app.models import db, Notification, Purchase, StockRequirement, GoodsReceivingReport, SupplierPayment, Product
from app.services.auth_service import role_required, log_audit
from app.services.analytics_service import AnalyticsService
from app.services.inventory_service import InventoryService

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def root():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    if current_user.role == 'CASHIER':
        return redirect(url_for('billing.pos'))
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/dashboard')
@login_required
@role_required('OWNER')
def index():
    # Scan for low stock and expiry alerts
    try:
        InventoryService.scan_for_system_alerts()
    except Exception as e:
        print(f"Alert scan notice: {e}")

    summary = AnalyticsService.get_dashboard_summary()
    perf = AnalyticsService.get_product_performance(timeframe='today')

    # Top unread notifications
    notifications = Notification.query.filter_by(is_read=False).order_by(Notification.created_at.desc()).limit(10).all()
    pending_approvals = Purchase.query.filter_by(status='PENDING_APPROVAL').count()
    pending_requirements = StockRequirement.query.filter_by(status='PENDING').count()
    pending_receiving = GoodsReceivingReport.query.filter(GoodsReceivingReport.status.in_(['SUBMITTED', 'UNDER_REVIEW', 'CORRECTION_REQUIRED'])).count()
    payment_count = SupplierPayment.query.count()

    return render_template(
        'dashboard/index.html',
        summary=summary,
        best_sellers=perf['best_sellers'][:5],
        slow_moving=perf['slow_moving'][:5],
        notifications=notifications,
        pending_approvals=pending_approvals,
        pending_requirements=pending_requirements,
        pending_receiving=pending_receiving,
        payment_count=payment_count
    )

@dashboard_bp.route('/api/dashboard/charts')
@login_required
@role_required('OWNER')
def chart_data():
    period = request.args.get('period', 'daily')
    sales_chart = AnalyticsService.get_sales_chart_data(period=period)
    category_chart = AnalyticsService.get_category_sales_chart_data()

    return jsonify({
        'sales_chart': sales_chart,
        'category_chart': category_chart
    })

@dashboard_bp.route('/staff/dashboard')
@login_required
@role_required('CASHIER')
def staff_dashboard():
    my_requirements = StockRequirement.query.filter_by(requested_by=current_user.id).count()
    my_reports = GoodsReceivingReport.query.filter_by(submitted_by=current_user.id).count()
    low_stock = Product.query.filter(
        Product.is_active == True,
        Product.current_stock > 0,
        Product.current_stock <= Product.min_stock_level
    ).count()
    out_of_stock = Product.query.filter(Product.is_active == True, Product.current_stock <= 0).count()
    pending_requirements = StockRequirement.query.filter_by(
        requested_by=current_user.id,
        status='PENDING'
    ).count()
    return render_template(
        'dashboard/staff.html',
        my_requirements=my_requirements,
        my_reports=my_reports,
        low_stock=low_stock,
        out_of_stock=out_of_stock,
        pending_requirements=pending_requirements
    )

@dashboard_bp.route('/notifications/mark-read/<int:id>', methods=['POST'])
@login_required
def mark_notification_read(id):
    notif = Notification.query.get_or_404(id)
    notif.is_read = True
    db.session.commit()
    return jsonify({'success': True})

@dashboard_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    Notification.query.filter_by(is_read=False).update({'is_read': True})
    db.session.commit()
    flash('All notifications marked as read.', 'info')
    return redirect(request.referrer or url_for('dashboard.index'))
