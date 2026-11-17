from flask import Blueprint, render_template, request, send_file, flash, redirect, url_for
from flask_login import login_required
from app.services.auth_service import role_required
from app.services.report_service import ReportService
from app.services.analytics_service import AnalyticsService
from datetime import datetime, date

report_bp = Blueprint('reports', __name__)

@report_bp.route('/reports')
@login_required
@role_required('OWNER')
def index():
    today = date.today().strftime('%Y-%m-%d')
    first_of_month = date.today().replace(day=1).strftime('%Y-%m-%d')
    return render_template('reports/index.html', today=today, first_of_month=first_of_month)

@report_bp.route('/reports/export/<format_type>/<report_type>')
@login_required
@role_required('OWNER')
def export_report(format_type, report_type):
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

    title = "Report"
    headers = []
    data = []
    landscape_mode = False

    if report_type == 'sales':
        title = "Sales Transactions Report"
        headers, data = ReportService.get_sales_report_data(start_date=start_date, end_date=end_date)
        landscape_mode = True

    elif report_type == 'inventory':
        title = "Product Inventory Report"
        headers, data = ReportService.get_inventory_report_data()
        landscape_mode = True

    elif report_type == 'low_stock':
        title = "Low Stock & Out of Stock Alert Report"
        headers, data = ReportService.get_low_stock_report_data()

    elif report_type == 'expiry':
        title = "Inventory Batch Expiry Report"
        headers, data = ReportService.get_expiry_report_data()
        landscape_mode = True

    elif report_type == 'profit_loss':
        title = "Profit and Loss Statement Report"
        pnl = AnalyticsService.get_profit_and_loss_statement(start_date=start_date, end_date=end_date)
        headers = ['Financial Line Item', 'Amount ($)']
        data = [
            ['Gross Sales Revenue', f"{pnl['gross_revenue']:.2f}"],
            ['Sales Returns Deducted', f"-{pnl['sales_returns']:.2f}"],
            ['Net Revenue', f"{pnl['net_revenue']:.2f}"],
            ['Cost of Goods Sold (COGS)', f"-{pnl['cogs']:.2f}"],
            ['Gross Profit', f"{pnl['gross_profit']:.2f}"],
            ['Wastage / Spoilage Losses', f"-{pnl['wastage_loss']:.2f}"],
            ['Total Operating Expenses', f"-{pnl['total_expenses']:.2f}"],
            ['NET PROFIT / (LOSS)', f"{pnl['net_profit']:.2f}"]
        ]

    elif report_type == 'best_sellers':
        title = "Best-Selling Products Analysis Report"
        perf = AnalyticsService.get_product_performance(timeframe='all')
        headers = ['Barcode', 'Product Name', 'Total Sold', 'Revenue ($)', 'Gross Profit ($)', 'Current Stock']
        data = []
        for p in perf['best_sellers']:
            data.append([
                p['barcode'],
                p['name'],
                p['total_sold'],
                f"{p['total_revenue']:.2f}",
                f"{p['total_gross_profit']:.2f}",
                p['current_stock']
            ])

    else:
        flash('Invalid report type specified.', 'danger')
        return redirect(url_for('reports.index'))

    date_tag = datetime.now().strftime('%Y%m%d_%H%M%S')

    if format_type == 'pdf':
        buffer = ReportService.generate_pdf(
            title=title,
            headers=headers,
            data=data,
            landscape_mode=landscape_mode,
            summary_text=f"Period: {start_date_str or 'All'} to {end_date_str or 'Today'}"
        )
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"{report_type}_report_{date_tag}.pdf",
            mimetype='application/pdf'
        )

    elif format_type == 'excel':
        buffer = ReportService.generate_excel(
            title=title,
            headers=headers,
            data=data
        )
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"{report_type}_report_{date_tag}.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    else:
        flash('Invalid format. Choose PDF or Excel.', 'danger')
        return redirect(url_for('reports.index'))
