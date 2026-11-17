from datetime import datetime
from . import db

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(30), nullable=False) # 'LOW_STOCK', 'OUT_OF_STOCK', 'EXPIRY_NEAR', 'EXPIRED', 'SYSTEM'
    title = db.Column(db.String(100), nullable=False, default='Inventory Alert')
    message = db.Column(db.Text, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    product = db.relationship('Product')

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'title': self.title,
            'message': self.message,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else '',
            'is_read': self.is_read,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
