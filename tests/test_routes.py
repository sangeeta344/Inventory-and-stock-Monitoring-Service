import unittest
import json
from datetime import date
from app import create_app
from app.models import db, User, Category, Product, InventoryBatch

class RouteAccessTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app({
            'TESTING': True,
            'SECRET_KEY': 'test-secret',
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'USE_SQLITE': True,
            'WTF_CSRF_ENABLED': False
        })
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create Owner
        self.owner = User(username='owner_user', email='owner@test.com', role='OWNER', full_name='Owner User')
        self.owner.set_password('pass123')

        # Create Cashier
        self.cashier = User(username='cashier_user', email='cashier@test.com', role='CASHIER', full_name='Cashier User')
        self.cashier.set_password('pass123')

        db.session.add_all([self.owner, self.cashier])
        db.session.commit()

        # Category and Product
        cat = Category(name='Snacks')
        db.session.add(cat)
        db.session.flush()

        prod = Product(
            name='Chips 50g',
            category_id=cat.id,
            barcode='7778889990001',
            purchase_price=1.00,
            selling_price=2.00,
            current_stock=10,
            min_stock_level=3
        )
        db.session.add(prod)
        db.session.flush()

        batch = InventoryBatch(
            product_id=prod.id,
            batch_number='CHIP-01',
            purchase_date=date.today(),
            unit_cost=1.00,
            quantity_received=10,
            quantity_remaining=10
        )
        db.session.add(batch)
        db.session.commit()

        self.prod_id = prod.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login_as(self, username, password='pass123'):
        return self.client.post('/login', data={'username': username, 'password': password}, follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_unauthenticated_redirect(self):
        """Unauthenticated user accessing protected page is redirected to login"""
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res.headers['Location'])

    def test_cashier_rbac_restrictions(self):
        """Cashier attempting to access Owner-only routes receives HTTP 403 Forbidden"""
        self.login_as('cashier_user')

        # Cashier accessing dashboard -> 403
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 403)

        # Cashier accessing profit & loss -> 403
        res = self.client.get('/analytics/profit-loss')
        self.assertEqual(res.status_code, 403)

        # Cashier accessing employee management -> 403
        res = self.client.get('/employees')
        self.assertEqual(res.status_code, 403)

        # Cashier CAN access POS billing terminal -> 200
        res = self.client.get('/billing')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'POS Terminal', res.data)

    def test_owner_access_all_modules(self):
        """Owner can access all management routes"""
        self.login_as('owner_user')

        routes = [
            '/dashboard',
            '/products',
            '/inventory',
            '/suppliers',
            '/purchases',
            '/returns',
            '/sales',
            '/analytics/profit-loss',
            '/analytics/products',
            '/expenses',
            '/employees',
            '/reports',
            '/billing'
        ]
        for route in routes:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Route {route} failed with status {res.status_code}")

    def test_api_product_lookup_and_checkout_flow(self):
        """Test API barcode lookup and JSON checkout endpoint"""
        self.login_as('cashier_user')

        # 1. Barcode lookup API
        res = self.client.get('/api/billing/product-lookup/7778889990001')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['product']['name'], 'Chips 50g')

        # 2. Checkout API
        payload = {
            'cart': [{'product_id': self.prod_id, 'quantity': 2}],
            'customer_name': 'Alice Smith',
            'customer_phone': '555-9876',
            'payment_method': 'CASH',
            'discount_amount': 0.0,
            'tax_rate': 5.0
        }
        res = self.client.post('/api/billing/checkout', json=payload)
        self.assertEqual(res.status_code, 200)
        resp_json = res.get_json()
        self.assertTrue(resp_json['success'])
        self.assertIn('INV-', resp_json['invoice_number'])
        self.assertEqual(resp_json['final_amount'], 4.20) # (2 * 2.00) * 1.05 = 4.20

    def test_report_downloads_response(self):
        """Test report download endpoints return valid file attachments"""
        self.login_as('owner_user')

        # PDF download
        res_pdf = self.client.get('/reports/export/pdf/inventory')
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf.headers['Content-Type'], 'application/pdf')

        # Excel download
        res_excel = self.client.get('/reports/export/excel/inventory')
        self.assertEqual(res_excel.status_code, 200)
        self.assertIn('spreadsheetml', res_excel.headers['Content-Type'])

if __name__ == '__main__':
    unittest.main()
