from flask import Blueprint, render_template, request
from flask_login import login_required
from app.services.auth_service import role_required
from app.services.analytics_service import AnalyticsService
from datetime import date

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/analytics/profit-loss')
@login_required
@role_required('OWNER')
def profit_loss():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    start_date = None
    end_date = None

    if start_date_str:
        try:
            start_date = date.fromisoformat(start_date_str)
        except ValueError:
            pass

    if end_date_str:
        try:
            end_date = date.fromisoformat(end_date_str)
        except ValueError:
            pass

    pnl = AnalyticsService.get_profit_and_loss_statement(start_date=start_date, end_date=end_date)
    return render_template('analytics/profit_loss.html', pnl=pnl)

@analytics_bp.route('/analytics/products')
@login_required
@role_required('OWNER')
def products_analysis():
    timeframe = request.args.get('timeframe', 'month') # 'today', 'month', 'all'
    performance = AnalyticsService.get_product_performance(timeframe=timeframe)
    return render_template('analytics/products.html', performance=performance, current_timeframe=timeframe)
