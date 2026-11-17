from datetime import datetime
from . import db

class Supplier(db.Model):
    __tablename__ = 'suppliers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    address = db.Column(db.Text, nullable=True)
    payment_details = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    purchases = db.relationship('Purchase', backref='supplier', lazy='dynamic')
    batches = db.relationship('InventoryBatch', backref='supplier', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'company_name': self.company_name,
            'phone': self.phone,
            'email': self.email or '',
            'address': self.address or '',
            'payment_details': self.payment_details or '',
            'is_active': self.is_active,
            'total_purchases': self.purchases.count(),
            'created_at': self.created_at.strftime('%Y-%m-%d')
        }
