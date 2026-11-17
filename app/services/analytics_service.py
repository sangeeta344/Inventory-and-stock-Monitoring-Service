from datetime import datetime, date, timedelta
from sqlalchemy import func, desc, and_
from app.models import (
    db, Product, InventoryBatch, Supplier, Sale, SaleItem, 
    Return, ReturnItem, Expense, StockMovement
)

class AnalyticsService:

    @staticmethod
    def get_dashboard_summary():
        """
        Calculates real-time metrics for the Owner dashboard:
        - Total products, total stock quantity, low-stock count, out-of-stock count
        - Today's sales, this month's sales
        - Gross profit & Net profit
        - Products nearing expiry (within 30 days)
        - Total suppliers
        - Recent sales transactions
        """
        today = date.today()
        start_of_today = datetime.combine(today, datetime.min.time())
        end_of_today = datetime.combine(today, datetime.max.time())
        start_of_month = datetime(today.year, today.month, 1)

        # 1. Product & Stock KPIs
        total_products = Product.query.filter_by(is_active=True).count()
        total_stock_qty = db.session.query(func.coalesce(func.sum(Product.current_stock), 0))\
                                    .filter(Product.is_active == True).scalar()
        
        low_stock_count = Product.query.filter(
            Product.is_active == True,
            Product.current_stock > 0,
            Product.current_stock <= Product.min_stock_level
        ).count()

        out_of_stock_count = Product.query.filter(
            Product.is_active == True,
            Product.current_stock <= 0
        ).count()

        # 2. Expiry KPIs
        nearing_expiry_date = today + timedelta(days=30)
        nearing_expiry_count = InventoryBatch.query.filter(
            InventoryBatch.is_active == True,
            InventoryBatch.quantity_remaining > 0,
            InventoryBatch.expiry_date != None,
            InventoryBatch.expiry_date >= today,
            InventoryBatch.expiry_date <= nearing_expiry_date
        ).count()

        expired_batches_count = InventoryBatch.query.filter(
            InventoryBatch.is_active == True,
            InventoryBatch.quantity_remaining > 0,
            InventoryBatch.expiry_date != None,
            InventoryBatch.expiry_date < today
        ).count()

        # 3. Suppliers KPI
        total_suppliers = Supplier.query.filter_by(is_active=True).count()

        # 4. Sales Today & This Month
        sales_today = db.session.query(func.coalesce(func.sum(Sale.final_amount), 0.0))\
                                .filter(Sale.payment_status == 'COMPLETED')\
                                .filter(Sale.transaction_date >= start_of_today)\
                                .filter(Sale.transaction_date <= end_of_today).scalar()

        sales_month = db.session.query(func.coalesce(func.sum(Sale.final_amount), 0.0))\
                                .filter(Sale.payment_status == 'COMPLETED')\
                                .filter(Sale.transaction_date >= start_of_month).scalar()

        orders_today_count = Sale.query.filter(
            Sale.payment_status == 'COMPLETED',
            Sale.transaction_date >= start_of_today,
            Sale.transaction_date <= end_of_today
        ).count()

        # 5. Month-to-date Profit Calculations
        # Revenue this month
        month_revenue = float(sales_month)

        # COGS this month (sum of unit_cost * quantity for all items sold this month)
        month_cogs = db.session.query(func.coalesce(func.sum(SaleItem.unit_cost * SaleItem.quantity), 0.0))\
                               .join(Sale, SaleItem.sale_id == Sale.id)\
                               .filter(Sale.payment_status == 'COMPLETED')\
                               .filter(Sale.transaction_date >= start_of_month).scalar()
        month_cogs = float(month_cogs)

        # Returns refunded this month
        month_returns = db.session.query(func.coalesce(func.sum(Return.total_refund_amount), 0.0))\
                                  .filter(Return.return_date >= start_of_month).scalar()
        month_returns = float(month_returns)

        # Expenses this month
        month_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0.0))\
                                   .filter(Expense.expense_date >= today.replace(day=1)).scalar()
        month_expenses = float(month_expenses)

        # Wastage cost this month (StockMovements of type DAMAGE_WASTAGE or EXPIRED_WASTAGE)
        # We calculate cost from associated batch unit_cost
        month_wastage = db.session.query(func.coalesce(func.sum(func.abs(StockMovement.quantity_change) * InventoryBatch.unit_cost), 0.0))\
                                  .select_from(StockMovement)\
                                  .join(InventoryBatch, StockMovement.batch_id == InventoryBatch.id)\
                                  .filter(StockMovement.movement_type.in_(['DAMAGE_WASTAGE', 'EXPIRED_WASTAGE']))\
                                  .filter(StockMovement.created_at >= start_of_month).scalar()
        month_wastage = float(month_wastage)

        # Gross Profit = Revenue - COGS - Returns
        month_gross_profit = round(month_revenue - month_cogs - month_returns, 2)
        # Net Profit = Gross Profit - Expenses - Wastage
        month_net_profit = round(month_gross_profit - month_expenses - month_wastage, 2)

        # 6. Recent Sales
        recent_sales = Sale.query.order_by(Sale.transaction_date.desc()).limit(7).all()

        return {
            'total_products': total_products,
            'total_stock_qty': total_stock_qty,
            'low_stock_count': low_stock_count,
            'out_of_stock_count': out_of_stock_count,
            'nearing_expiry_count': nearing_expiry_count,
            'expired_batches_count': expired_batches_count,
            'total_suppliers': total_suppliers,
            'sales_today': float(sales_today),
            'sales_month': float(sales_month),
            'orders_today_count': orders_today_count,
            'month_gross_profit': month_gross_profit,
            'month_net_profit': month_net_profit,
            'month_expenses': month_expenses,
            'month_wastage': month_wastage,
            'recent_sales': recent_sales
        }

    @staticmethod
    def get_sales_chart_data(period='daily'):
        """
        Generates structured data points for Chart.js:
        - daily: past 7 days sales and gross profit
        - weekly: past 8 weeks
        - monthly: past 6 months
        """
        today = date.today()
        labels = []
        sales_data = []
        profit_data = []

        if period == 'daily':
            # Past 7 days
            for i in range(6, -1, -1):
                day = today - timedelta(days=i)
                day_start = datetime.combine(day, datetime.min.time())
                day_end = datetime.combine(day, datetime.max.time())
                labels.append(day.strftime('%b %d'))

                day_sales = db.session.query(func.coalesce(func.sum(Sale.final_amount), 0.0))\
                                      .filter(Sale.payment_status == 'COMPLETED')\
                                      .filter(Sale.transaction_date >= day_start)\
                                      .filter(Sale.transaction_date <= day_end).scalar()

                day_cogs = db.session.query(func.coalesce(func.sum(SaleItem.unit_cost * SaleItem.quantity), 0.0))\
                                     .join(Sale, SaleItem.sale_id == Sale.id)\
                                     .filter(Sale.payment_status == 'COMPLETED')\
                                     .filter(Sale.transaction_date >= day_start)\
                                     .filter(Sale.transaction_date <= day_end).scalar()

                sales_val = round(float(day_sales), 2)
                profit_val = round(sales_val - float(day_cogs), 2)
                sales_data.append(sales_val)
                profit_data.append(profit_val)

        elif period == 'monthly':
            # Past 6 months
            for i in range(5, -1, -1):
                # Calculate month date
                m_date = today.replace(day=1) - timedelta(days=i*30)
                m_start = datetime(m_date.year, m_date.month, 1)
                # Next month start
                if m_date.month == 12:
                    m_end = datetime(m_date.year + 1, 1, 1)
                else:
                    m_end = datetime(m_date.year, m_date.month + 1, 1)

                labels.append(m_date.strftime('%B %Y'))

                m_sales = db.session.query(func.coalesce(func.sum(Sale.final_amount), 0.0))\
                                    .filter(Sale.payment_status == 'COMPLETED')\
                                    .filter(Sale.transaction_date >= m_start)\
                                    .filter(Sale.transaction_date < m_end).scalar()

                m_cogs = db.session.query(func.coalesce(func.sum(SaleItem.unit_cost * SaleItem.quantity), 0.0))\
                                   .join(Sale, SaleItem.sale_id == Sale.id)\
                                   .filter(Sale.payment_status == 'COMPLETED')\
                                   .filter(Sale.transaction_date >= m_start)\
                                   .filter(Sale.transaction_date < m_end).scalar()

                sales_val = round(float(m_sales), 2)
                profit_val = round(sales_val - float(m_cogs), 2)
                sales_data.append(sales_val)
                profit_data.append(profit_val)

        return {
            'labels': labels,
            'sales': sales_data,
            'profit': profit_data
        }

    @staticmethod
    def get_category_sales_chart_data():
        """
        Category-wise distribution of sales revenue for donut / pie charts.
        """
        results = db.session.query(
            Product.category_id,
            func.coalesce(func.sum(SaleItem.subtotal), 0.0).label('total_revenue')
        ).join(SaleItem, Product.id == SaleItem.product_id)\
         .join(Sale, SaleItem.sale_id == Sale.id)\
         .filter(Sale.payment_status == 'COMPLETED')\
         .group_by(Product.category_id)\
         .all()

        from app.models import Category
        labels = []
        data = []
        for cat_id, rev in results:
            cat = Category.query.get(cat_id)
            labels.append(cat.name if cat else 'Uncategorized')
            data.append(round(float(rev), 2))

        if not labels:
            labels = ['No Sales Yet']
            data = [0]

        return {'labels': labels, 'data': data}

    @staticmethod
    def get_product_performance(timeframe='all'):
        """
        Returns categorized product rankings:
        - Best-selling products (by quantity)
        - Highest revenue products
        - Highest gross profit products
        - Slow-moving / least-selling products
        """
        query = db.session.query(
            Product.id,
            Product.name,
            Product.barcode,
            Product.current_stock,
            func.coalesce(func.sum(SaleItem.quantity), 0).label('total_sold'),
            func.coalesce(func.sum(SaleItem.subtotal), 0.0).label('total_revenue'),
            func.coalesce(func.sum((SaleItem.unit_price - SaleItem.unit_cost) * SaleItem.quantity), 0.0).label('total_gross_profit')
        ).outerjoin(SaleItem, Product.id == SaleItem.product_id)\
         .filter(Product.is_active == True)

        if timeframe == 'today':
            today_start = datetime.combine(date.today(), datetime.min.time())
            query = query.outerjoin(Sale, SaleItem.sale_id == Sale.id)\
                         .filter(db.or_(Sale.transaction_date >= today_start, SaleItem.id == None))
        elif timeframe == 'month':
            month_start = datetime(date.today().year, date.today().month, 1)
            query = query.outerjoin(Sale, SaleItem.sale_id == Sale.id)\
                         .filter(db.or_(Sale.transaction_date >= month_start, SaleItem.id == None))

        query = query.group_by(Product.id, Product.name, Product.barcode, Product.current_stock)
        all_results = query.all()

        # Format rows
        products_list = []
        for r in all_results:
            products_list.append({
                'id': r.id,
                'name': r.name,
                'barcode': r.barcode,
                'current_stock': r.current_stock,
                'total_sold': int(r.total_sold),
                'total_revenue': round(float(r.total_revenue), 2),
                'total_gross_profit': round(float(r.total_gross_profit), 2)
            })

        # Sort variants
        by_quantity = sorted(products_list, key=lambda x: x['total_sold'], reverse=True)
        by_revenue = sorted(products_list, key=lambda x: x['total_revenue'], reverse=True)
        by_profit = sorted(products_list, key=lambda x: x['total_gross_profit'], reverse=True)
        slow_moving = sorted([p for p in products_list if p['current_stock'] > 0], key=lambda x: (x['total_sold'], -x['current_stock']))

        return {
            'best_sellers': by_quantity[:10],
            'highest_revenue': by_revenue[:10],
            'highest_profit': by_profit[:10],
            'slow_moving': slow_moving[:10]
        }

    @staticmethod
    def get_profit_and_loss_statement(start_date=None, end_date=None):
        """
        Computes formal financial Profit and Loss Statement with:
        - Gross Revenue
        - Sales Returns
        - Net Revenue
        - Cost of Goods Sold (COGS from actual batch costs)
        - Gross Profit
        - Wastage Loss (Damaged & Expired stock costs)
        - Operating Expenses itemized (Rent, Salaries, Electricity, etc.)
        - Total Operating Expenses
        - Net Profit / Loss
        - Product-wise profit breakdown
        """
        if not start_date:
            start_date = date.today().replace(day=1)
        if not end_date:
            end_date = date.today()

        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        # 1. Gross Revenue
        gross_revenue = db.session.query(func.coalesce(func.sum(Sale.final_amount), 0.0))\
                                  .filter(Sale.payment_status == 'COMPLETED')\
                                  .filter(Sale.transaction_date >= start_dt)\
                                  .filter(Sale.transaction_date <= end_dt).scalar()
        gross_revenue = float(gross_revenue)

        # 2. Sales Returns
        sales_returns = db.session.query(func.coalesce(func.sum(Return.total_refund_amount), 0.0))\
                                  .filter(Return.return_date >= start_dt)\
                                  .filter(Return.return_date <= end_dt).scalar()
        sales_returns = float(sales_returns)

        # Net Revenue
        net_revenue = round(gross_revenue - sales_returns, 2)

        # 3. Cost of Goods Sold (COGS)
        cogs = db.session.query(func.coalesce(func.sum(SaleItem.unit_cost * SaleItem.quantity), 0.0))\
                         .join(Sale, SaleItem.sale_id == Sale.id)\
                         .filter(Sale.payment_status == 'COMPLETED')\
                         .filter(Sale.transaction_date >= start_dt)\
                         .filter(Sale.transaction_date <= end_dt).scalar()
        cogs = float(cogs)

        # Gross Profit
        gross_profit = round(net_revenue - cogs, 2)

        # 4. Wastage & Spoilage Loss
        wastage_loss = db.session.query(func.coalesce(func.sum(func.abs(StockMovement.quantity_change) * InventoryBatch.unit_cost), 0.0))\
                                 .select_from(StockMovement)\
                                 .join(InventoryBatch, StockMovement.batch_id == InventoryBatch.id)\
                                 .filter(StockMovement.movement_type.in_(['DAMAGE_WASTAGE', 'EXPIRED_WASTAGE']))\
                                 .filter(StockMovement.created_at >= start_dt)\
                                 .filter(StockMovement.created_at <= end_dt).scalar()
        wastage_loss = float(wastage_loss)

        # 5. Itemized Operating Expenses
        expenses_records = db.session.query(
            Expense.category,
            func.coalesce(func.sum(Expense.amount), 0.0).label('category_total')
        ).filter(Expense.expense_date >= start_date)\
         .filter(Expense.expense_date <= end_date)\
         .group_by(Expense.category).all()

        expenses_by_cat = {cat: float(tot) for cat, tot in expenses_records}
        total_operating_expenses = sum(expenses_by_cat.values())

        # Net Profit
        net_profit = round(gross_profit - wastage_loss - total_operating_expenses, 2)

        # 6. Product-wise Profit Breakdown
        product_profits = db.session.query(
            Product.id,
            Product.name,
            Product.barcode,
            func.coalesce(func.sum(SaleItem.quantity), 0).label('quantity_sold'),
            func.coalesce(func.sum(SaleItem.subtotal), 0.0).label('revenue'),
            func.coalesce(func.sum(SaleItem.unit_cost * SaleItem.quantity), 0.0).label('cogs'),
            func.coalesce(func.sum((SaleItem.unit_price - SaleItem.unit_cost) * SaleItem.quantity), 0.0).label('profit')
        ).join(SaleItem, Product.id == SaleItem.product_id)\
         .join(Sale, SaleItem.sale_id == Sale.id)\
         .filter(Sale.payment_status == 'COMPLETED')\
         .filter(Sale.transaction_date >= start_dt)\
         .filter(Sale.transaction_date <= end_dt)\
         .group_by(Product.id, Product.name, Product.barcode)\
         .order_by(desc('profit'))\
         .all()

        itemized_products = []
        for p in product_profits:
            rev = float(p.revenue)
            prof = float(p.profit)
            margin = round((prof / rev * 100), 2) if rev > 0 else 0.0
            itemized_products.append({
                'id': p.id,
                'name': p.name,
                'barcode': p.barcode,
                'quantity_sold': int(p.quantity_sold),
                'revenue': round(rev, 2),
                'cogs': round(float(p.cogs), 2),
                'profit': round(prof, 2),
                'margin': margin
            })

        return {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'gross_revenue': round(gross_revenue, 2),
            'sales_returns': round(sales_returns, 2),
            'net_revenue': round(net_revenue, 2),
            'cogs': round(cogs, 2),
            'gross_profit': round(gross_profit, 2),
            'wastage_loss': round(wastage_loss, 2),
            'expenses_by_category': expenses_by_cat,
            'total_expenses': round(total_operating_expenses, 2),
            'net_profit': round(net_profit, 2),
            'product_profits': itemized_products
        }
