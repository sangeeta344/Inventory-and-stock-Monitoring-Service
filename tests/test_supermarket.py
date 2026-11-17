import unittest
import json
from datetime import date, timedelta
from app import create_app
from app.models import (
    db, User, Employee, Category, Product, Supplier, 
    InventoryBatch, Sale, SaleItem, Return, Expense, StockMovement
)
from app.services.inventory_service import InventoryService
from app.services.billing_service import BillingService
from app.services.analytics_service import AnalyticsService
from app.services.report_service import ReportService

class TestConfig:
    TESTING = True
    SECRET_KEY = 'test-supermarket-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    USE_SQLITE = True
    STORE_NAME = 'Test Supermarket'
    STORE_DEFAULT_TAX_RATE = 5.0

class SupermarketSystemTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create Owner & Cashier users
        self.owner = User(
            username='test_owner',
            email='owner@test.com',
            role='OWNER',
            full_name='Owner Tester'
        )
        self.owner.set_password('password123')

        self.cashier = User(
            username='test_cashier',
            email='cashier@test.com',
            role='CASHIER',
            full_name='Cashier Tester'
        )
        self.cashier.set_password('password123')

        db.session.add_all([self.owner, self.cashier])
        db.session.commit()

        # Create Category & Product
        self.category = Category(name='Dairy', description='Fresh dairy')
        db.session.add(self.category)
        db.session.commit()

        self.product = Product(
            name='Test Milk 1L',
            category_id=self.category.id,
            barcode='1112223334445',
            purchase_price=2.00,
            selling_price=3.50,
            current_stock=20,
            min_stock_level=5,
            unit_of_measure='ltr'
        )
        db.session.add(self.product)
        db.session.commit()

        # Create two batches with different expiries to test FEFO
        today = date.today()
        # Batch 1 expires in 5 days (earlier)
        self.batch_near = InventoryBatch(
            product_id=self.product.id,
            batch_number='BATCH-EARLY',
            purchase_date=today - timedelta(days=2),
            expiry_date=today + timedelta(days=5),
            unit_cost=2.00,
            quantity_received=10,
            quantity_remaining=10
        )
        # Batch 2 expires in 30 days (later)
        self.batch_far = InventoryBatch(
            product_id=self.product.id,
            batch_number='BATCH-LATER',
            purchase_date=today - timedelta(days=2),
            expiry_date=today + timedelta(days=30),
            unit_cost=2.20,
            quantity_received=10,
            quantity_remaining=10
        )
        db.session.add_all([self.batch_near, self.batch_far])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_user_authentication(self):
        """Test password verification and role properties"""
        self.assertTrue(self.owner.check_password('password123'))
        self.assertFalse(self.owner.check_password('wrongpassword'))
        self.assertTrue(self.owner.is_owner)
        self.assertFalse(self.owner.is_cashier)
        self.assertTrue(self.cashier.is_cashier)

    def test_barcode_lookup(self):
        """Test barcode lookup service"""
        res = BillingService.find_product_by_barcode('1112223334445')
        self.assertIsNotNone(res)
        self.assertEqual(res['name'], 'Test Milk 1L')
        self.assertEqual(res['selling_price'], 3.50)
        self.assertEqual(res['sellable_stock'], 20)

    def test_fefo_batch_allocation(self):
        """Test FEFO logic: earliest expiring batch must be allocated first"""
        allocations, err = InventoryService.get_fefo_batches_for_sale(self.product.id, 15)
        self.assertIsNone(err)
        self.assertEqual(len(allocations), 2)
        # First allocation should be from batch_near (10 units)
        self.assertEqual(allocations[0]['batch'].batch_number, 'BATCH-EARLY')
        self.assertEqual(allocations[0]['deduct_qty'], 10)
        # Second allocation should be from batch_far (5 units)
        self.assertEqual(allocations[1]['batch'].batch_number, 'BATCH-LATER')
        self.assertEqual(allocations[1]['deduct_qty'], 5)

    def test_checkout_and_automatic_inventory_deduction(self):
        """Test checkout transaction: creates sale, deducts stock, maintains movements"""
        cart = [{
            'product_id': self.product.id,
            'quantity': 12
        }]
        success, sale = BillingService.process_checkout(
            cashier_id=self.cashier.id,
            cart_items=cart,
            customer_name='John Doe',
            customer_phone='555-1234',
            payment_method='CASH',
            discount_amount=2.00,
            tax_rate=5.0
        )
        self.assertTrue(success)
        self.assertIsNotNone(sale.invoice_number)
        
        # Check stock deduction (20 - 12 = 8 remaining)
        refreshed_prod = Product.query.get(self.product.id)
        self.assertEqual(refreshed_prod.current_stock, 8)

        # Check FEFO batch deductions:
        # BATCH-EARLY had 10, now should have 0
        b_near = InventoryBatch.query.filter_by(batch_number='BATCH-EARLY').first()
        self.assertEqual(b_near.quantity_remaining, 0)
        # BATCH-LATER had 10, 2 deducted -> 8 remaining
        b_far = InventoryBatch.query.filter_by(batch_number='BATCH-LATER').first()
        self.assertEqual(b_far.quantity_remaining, 8)

        # Check stock movement log
        movements = StockMovement.query.filter_by(product_id=self.product.id).all()
        self.assertTrue(len(movements) >= 2)
        self.assertEqual(movements[-1].movement_type, 'SALE')

    def test_customer_return_resellable(self):
        """Test customer return of resellable goods increases stock"""
        # First make a sale of 5
        cart = [{'product_id': self.product.id, 'quantity': 5}]
        success, sale = BillingService.process_checkout(
            cashier_id=self.cashier.id,
            cart_items=cart,
            customer_name='Jane',
            customer_phone='',
            payment_method='CARD'
        )
        self.assertTrue(success)
        self.assertEqual(self.product.current_stock, 15)

        # Now return 2 units as RESELLABLE
        sale_item = sale.items.first()
        InventoryService.process_return_item(
            sale_item=sale_item,
            quantity=2,
            condition='RESELLABLE',
            reason='Customer changed mind',
            return_number='RET-TEST-001',
            user_id=self.cashier.id
        )
        db.session.commit()

        # Stock should increase to 17
        self.assertEqual(self.product.current_stock, 17)

    def test_customer_return_damaged_does_not_increase_stock(self):
        """Test customer return of damaged item is logged as wastage and does not increase sellable stock"""
        cart = [{'product_id': self.product.id, 'quantity': 5}]
        success, sale = BillingService.process_checkout(
            cashier_id=self.cashier.id,
            cart_items=cart,
            customer_name='Jane',
            customer_phone='',
            payment_method='CARD'
        )
        self.assertTrue(success)
        self.assertEqual(self.product.current_stock, 15)

        sale_item = sale.items.first()
        InventoryService.process_return_item(
            sale_item=sale_item,
            quantity=2,
            condition='DAMAGED',
            reason='Broken cap',
            return_number='RET-TEST-002',
            user_id=self.cashier.id
        )
        db.session.commit()

        # Stock must remain 15
        self.assertEqual(self.product.current_stock, 15)
        # Check movement recorded
        mv = StockMovement.query.filter_by(reference_id='RET-TEST-002').first()
        self.assertEqual(mv.movement_type, 'DAMAGE_WASTAGE')

    def test_profit_and_loss_calculation(self):
        """Test financial P&L calculation: Revenue - COGS - Expenses = Net Profit"""
        # Add an expense
        expense = Expense(
            title='Store Electric Bill',
            category='ELECTRICITY',
            amount=50.00,
            expense_date=date.today(),
            created_by=self.owner.id
        )
        db.session.add(expense)
        db.session.commit()

        # Make sale: 10 items of Milk at $3.50 = $35.00 revenue
        # Cost: 10 units at $2.00 = $20.00 COGS
        # Gross profit = $15.00
        cart = [{'product_id': self.product.id, 'quantity': 10}]
        BillingService.process_checkout(
            cashier_id=self.cashier.id,
            cart_items=cart,
            customer_name='Cash Customer',
            customer_phone='',
            payment_method='CASH',
            discount_amount=0.0,
            tax_rate=0.0
        )

        pnl = AnalyticsService.get_profit_and_loss_statement()
        self.assertEqual(pnl['gross_revenue'], 35.00)
        self.assertEqual(pnl['cogs'], 20.00)
        self.assertEqual(pnl['gross_profit'], 15.00)
        self.assertEqual(pnl['total_expenses'], 50.00)
        self.assertEqual(pnl['net_profit'], -35.00) # 15 - 50 = -35.00 loss

    def test_report_generation_pdf_and_excel(self):
        """Verify ReportLab PDF and OpenPyXL Excel generate valid non-empty byte streams"""
        headers = ['Barcode', 'Name', 'Stock']
        data = [['12345', 'Sample Item', 20]]
        
        pdf_buf = ReportService.generate_pdf('Test Report', headers, data)
        self.assertGreater(len(pdf_buf.getvalue()), 500)

        excel_buf = ReportService.generate_excel('Test Report', headers, data)
        self.assertGreater(len(excel_buf.getvalue()), 1000)

if __name__ == '__main__':
    unittest.main()
