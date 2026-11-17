from datetime import datetime, date
from . import db

class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    products = db.relationship('Product', backref='category', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_active': self.is_active,
            'product_count': self.products.count()
        }

class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    barcode = db.Column(db.String(50), unique=True, nullable=False, index=True)
    purchase_price = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    selling_price = db.Column(db.Numeric(10, 2), nullable=False)
    current_stock = db.Column(db.Integer, nullable=False, default=0)
    min_stock_level = db.Column(db.Integer, nullable=False, default=5)
    unit_of_measure = db.Column(db.String(20), nullable=False, default='pcs') # pcs, kg, g, ltr, ml, pack, box
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    batches = db.relationship('InventoryBatch', backref='product', lazy='dynamic', cascade='all, delete-orphan')
    stock_movements = db.relationship('StockMovement', backref='product', lazy='dynamic', cascade='all, delete-orphan')
    sale_items = db.relationship('SaleItem', backref='product', lazy='dynamic')
    purchase_items = db.relationship('PurchaseItem', backref='product', lazy='dynamic')

    @property
    def is_low_stock(self):
        return 0 < self.current_stock <= self.min_stock_level

    @property
    def is_out_of_stock(self):
        return self.current_stock <= 0

    @property
    def profit_margin_percent(self):
        if self.selling_price and float(self.selling_price) > 0:
            sp = float(self.selling_price)
            pp = float(self.purchase_price)
            return round(((sp - pp) / sp) * 100, 2)
        return 0.0

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else '',
            'barcode': self.barcode,
            'purchase_price': float(self.purchase_price),
            'selling_price': float(self.selling_price),
            'current_stock': self.current_stock,
            'min_stock_level': self.min_stock_level,
            'unit_of_measure': self.unit_of_measure,
            'description': self.description or '',
            'is_active': self.is_active,
            'is_low_stock': self.is_low_stock,
            'is_out_of_stock': self.is_out_of_stock,
            'profit_margin_percent': self.profit_margin_percent
        }

class InventoryBatch(db.Model):
    __tablename__ = 'inventory_batches'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    purchase_item_id = db.Column(db.Integer, nullable=True)
    batch_number = db.Column(db.String(50), nullable=False)
    purchase_date = db.Column(db.Date, nullable=False, default=date.today)
    expiry_date = db.Column(db.Date, nullable=True, index=True)
    unit_cost = db.Column(db.Numeric(10, 2), nullable=False)
    quantity_received = db.Column(db.Integer, nullable=False)
    quantity_remaining = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    sale_items = db.relationship('SaleItem', backref='batch', lazy='dynamic')
    stock_movements = db.relationship('StockMovement', backref='batch', lazy='dynamic')

    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        return self.expiry_date < date.today()

    @property
    def days_until_expiry(self):
        if not self.expiry_date:
            return None
        delta = self.expiry_date - date.today()
        return delta.days

    @property
    def is_near_expiry(self):
        if not self.expiry_date:
            return False
        days = self.days_until_expiry
        return 0 <= days <= 30

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else '',
            'barcode': self.product.barcode if self.product else '',
            'supplier_id': self.supplier_id,
            'supplier_name': self.supplier.name if self.supplier else 'Direct Receipt',
            'batch_number': self.batch_number,
            'purchase_date': self.purchase_date.strftime('%Y-%m-%d') if self.purchase_date else None,
            'expiry_date': self.expiry_date.strftime('%Y-%m-%d') if self.expiry_date else 'N/A',
            'unit_cost': float(self.unit_cost),
            'quantity_received': self.quantity_received,
            'quantity_remaining': self.quantity_remaining,
            'is_expired': self.is_expired,
            'is_near_expiry': self.is_near_expiry,
            'days_until_expiry': self.days_until_expiry,
            'is_active': self.is_active
        }

class StockMovement(db.Model):
    __tablename__ = 'stock_movements'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('inventory_batches.id'), nullable=True)
    movement_type = db.Column(db.String(30), nullable=False) 
    # 'SALE', 'PURCHASE_RECEIPT', 'CUSTOMER_RETURN', 'DAMAGE_WASTAGE', 'EXPIRED_WASTAGE', 'MANUAL_ADJUSTMENT'
    reference_id = db.Column(db.String(50), nullable=True) # Invoice #, Return #, Purchase #
    quantity_change = db.Column(db.Integer, nullable=False) # positive (added) or negative (deducted)
    quantity_after = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref='stock_movements')

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else '',
            'barcode': self.product.barcode if self.product else '',
            'batch_id': self.batch_id,
            'batch_number': self.batch.batch_number if self.batch else 'N/A',
            'movement_type': self.movement_type,
            'reference_id': self.reference_id or '',
            'quantity_change': self.quantity_change,
            'quantity_after': self.quantity_after,
            'notes': self.notes or '',
            'created_by_name': self.user.full_name if self.user else 'System',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
