from datetime import datetime, date
from . import db

class Purchase(db.Model):
    __tablename__ = 'purchases'

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    invoice_number = db.Column(db.String(50), nullable=False, index=True)
    purchase_date = db.Column(db.Date, nullable=False, default=date.today)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    payment_status = db.Column(db.String(20), nullable=False, default='PAID') # PAID, PENDING, PARTIAL
    status = db.Column(db.String(20), nullable=False, default='RECEIVED')     # RECEIVED, ORDERED, CANCELLED
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    stock_requirement_id = db.Column(db.Integer, db.ForeignKey('stock_requirements.id'), nullable=True)
    order_status = db.Column(db.String(30), nullable=True)
    ordered_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    ordered_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    items = db.relationship('PurchaseItem', backref='purchase', lazy='dynamic', cascade='all, delete-orphan')
    approved_by_user = db.relationship('User', foreign_keys=[approved_by])
    stock_requirement = db.relationship('StockRequirement', foreign_keys=[stock_requirement_id], backref='purchases')
    order_creator = db.relationship('User', foreign_keys=[ordered_by])

    def to_dict(self):
        return {
            'id': self.id,
            'supplier_id': self.supplier_id,
            'supplier_name': self.supplier.company_name if self.supplier else '',
            'invoice_number': self.invoice_number,
            'purchase_date': self.purchase_date.strftime('%Y-%m-%d') if self.purchase_date else None,
            'total_amount': float(self.total_amount),
            'payment_status': self.payment_status,
            'status': self.status,
            'approved_by': self.approved_by_user.full_name if self.approved_by_user else None,
            'approved_at': self.approved_at.strftime('%Y-%m-%d %H:%M:%S') if self.approved_at else None,
            'rejection_reason': self.rejection_reason or '',
            'notes': self.notes or '',
            'item_count': self.items.count(),
            'created_by': self.created_by_user.full_name if self.created_by_user else 'System',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class PurchaseItem(db.Model):
    __tablename__ = 'purchase_items'

    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    batch_number = db.Column(db.String(50), nullable=False)
    expiry_date = db.Column(db.Date, nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    approved_quantity = db.Column(db.Integer, nullable=True)
    quantity_adjustment_reason = db.Column(db.Text, nullable=True)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False) # purchase cost per unit
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'purchase_id': self.purchase_id,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else '',
            'barcode': self.product.barcode if self.product else '',
            'batch_number': self.batch_number,
            'expiry_date': self.expiry_date.strftime('%Y-%m-%d') if self.expiry_date else 'N/A',
            'quantity': self.quantity,
            'approved_quantity': self.approved_quantity,
            'quantity_adjustment_reason': self.quantity_adjustment_reason or '',
            'unit_price': float(self.unit_price),
            'subtotal': float(self.subtotal)
        }
