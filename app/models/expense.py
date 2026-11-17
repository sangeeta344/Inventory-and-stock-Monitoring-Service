from datetime import datetime, date
from . import db

class Expense(db.Model):
    __tablename__ = 'expenses'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False) # 'RENT', 'ELECTRICITY', 'SALARY', 'MAINTENANCE', 'SUPPLIES', 'OTHER'
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    expense_date = db.Column(db.Date, nullable=False, default=date.today)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref='expenses')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'category': self.category,
            'amount': float(self.amount),
            'expense_date': self.expense_date.strftime('%Y-%m-%d'),
            'notes': self.notes or '',
            'created_by': self.user.full_name if self.user else 'System',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
