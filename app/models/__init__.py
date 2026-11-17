from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .user import User, Employee, AuditLog
from .product import Category, Product, InventoryBatch, StockMovement
from .supplier import Supplier
from .purchase import Purchase, PurchaseItem
from .sale import Sale, SaleItem, Return, ReturnItem
from .expense import Expense
from .notification import Notification

__all__ = [
    'db',
    'User',
    'Employee',
    'AuditLog',
    'Category',
    'Product',
    'InventoryBatch',
    'StockMovement',
    'Supplier',
    'Purchase',
    'PurchaseItem',
    'Sale',
    'SaleItem',
    'Return',
    'ReturnItem',
    'Expense',
    'Notification'
]
