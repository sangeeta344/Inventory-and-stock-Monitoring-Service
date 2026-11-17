from datetime import datetime
from . import db

class Sale(db.Model):
    __tablename__ = 'sales'

    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    cashier_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    customer_name = db.Column(db.String(100), nullable=True, default='Walk-in Customer')
    customer_phone = db.Column(db.String(20), nullable=True)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    tax_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    final_amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(20), nullable=False, default='CASH') # CASH, CARD, UPI, DIGITAL
    payment_status = db.Column(db.String(20), nullable=False, default='COMPLETED') # COMPLETED, CANCELLED, REFUNDED
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    items = db.relationship('SaleItem', backref='sale', lazy='dynamic', cascade='all, delete-orphan')
    returns = db.relationship('Return', backref='sale', lazy='dynamic')

    @property
    def total_cost(self):
        # Sum of (unit_cost * quantity) for all items in the sale
        return sum(float(item.unit_cost) * item.quantity for item in self.items)

    @property
    def gross_profit(self):
        # Final amount - total cost
        return float(self.final_amount) - self.total_cost

    def to_dict(self):
        return {
            'id': self.id,
            'invoice_number': self.invoice_number,
            'transaction_date': self.transaction_date.strftime('%Y-%m-%d %H:%M:%S'),
            'cashier_id': self.cashier_id,
            'cashier_name': self.cashier.full_name if self.cashier else 'Unknown',
            'customer_name': self.customer_name or 'Walk-in Customer',
            'customer_phone': self.customer_phone or '',
            'subtotal': float(self.subtotal),
            'discount_amount': float(self.discount_amount),
            'tax_amount': float(self.tax_amount),
            'final_amount': float(self.final_amount),
            'total_cost': round(self.total_cost, 2),
            'gross_profit': round(self.gross_profit, 2),
            'payment_method': self.payment_method,
            'payment_status': self.payment_status,
            'item_count': self.items.count(),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class SaleItem(db.Model):
    __tablename__ = 'sale_items'

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('inventory_batches.id'), nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False) # Selling price per unit
    unit_cost = db.Column(db.Numeric(10, 2), nullable=False)  # Batch purchase cost per unit
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)

    return_items = db.relationship('ReturnItem', backref='sale_item', lazy='dynamic')

    @property
    def gross_profit(self):
        return float((self.unit_price - self.unit_cost) * self.quantity)

    def to_dict(self):
        return {
            'id': self.id,
            'sale_id': self.sale_id,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else '',
            'barcode': self.product.barcode if self.product else '',
            'unit_of_measure': self.product.unit_of_measure if self.product else 'pcs',
            'batch_id': self.batch_id,
            'batch_number': self.batch.batch_number if self.batch else 'N/A',
            'quantity': self.quantity,
            'unit_price': float(self.unit_price),
            'unit_cost': float(self.unit_cost),
            'subtotal': float(self.subtotal),
            'gross_profit': round(self.gross_profit, 2)
        }

class Return(db.Model):
    __tablename__ = 'returns'

    id = db.Column(db.Integer, primary_key=True)
    return_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    cashier_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    return_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    total_refund_amount = db.Column(db.Numeric(10, 2), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    cashier = db.relationship('User', backref='processed_returns')
    items = db.relationship('ReturnItem', backref='return_record', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'return_number': self.return_number,
            'sale_id': self.sale_id,
            'invoice_number': self.sale.invoice_number if self.sale else '',
            'cashier_id': self.cashier_id,
            'cashier_name': self.cashier.full_name if self.cashier else 'Staff',
            'return_date': self.return_date.strftime('%Y-%m-%d %H:%M:%S'),
            'total_refund_amount': float(self.total_refund_amount),
            'notes': self.notes or '',
            'item_count': self.items.count()
        }

class ReturnItem(db.Model):
    __tablename__ = 'return_items'

    id = db.Column(db.Integer, primary_key=True)
    return_id = db.Column(db.Integer, db.ForeignKey('returns.id', ondelete='CASCADE'), nullable=False)
    sale_item_id = db.Column(db.Integer, db.ForeignKey('sale_items.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    refund_amount = db.Column(db.Numeric(10, 2), nullable=False)
    condition = db.Column(db.String(20), nullable=False) # 'RESELLABLE', 'DAMAGED', 'EXPIRED'
    reason = db.Column(db.String(255), nullable=True)

    product = db.relationship('Product')

    def to_dict(self):
        return {
            'id': self.id,
            'return_id': self.return_id,
            'sale_item_id': self.sale_item_id,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else '',
            'barcode': self.product.barcode if self.product else '',
            'quantity': self.quantity,
            'refund_amount': float(self.refund_amount),
            'condition': self.condition,
            'reason': self.reason or ''
        }
