import unittest
import json
from datetime import date
from app import create_app
from app.models import (
    db, User, Category, Product, InventoryBatch, Supplier, Purchase, PurchaseItem,
    StockRequirement, StockRequirementItem, GoodsReceivingReport, GoodsReceivingItem,
    SupplierPayment
)

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
            '/reports'
        ]
        for route in routes:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Route {route} failed with status {res.status_code}")
        # Owner cannot perform cashier-only billing
        self.assertEqual(self.client.get('/billing').status_code, 403)

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

    def test_cashier_product_and_pending_stock_workflow(self):
        self.login_as('cashier_user')

        res = self.client.post('/products/add', data={
            'name': 'New Approved Product',
            'category_id': Category.query.first().id,
            'barcode': '1234567890123',
            'purchase_price': '2.50',
            'selling_price': '4.00',
            'min_stock_level': '5',
            'unit_of_measure': 'pcs',
            'description': 'Test product'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        product = Product.query.filter_by(barcode='1234567890123').first()
        self.assertIsNotNone(product)
        self.assertEqual(product.current_stock, 0)

        res = self.client.post('/requirements/new', data={
            'product_id[]': product.id,
            'quantity[]': '50',
            'notes': 'Replenishment test'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        from app.models import StockRequirement
        requirement = StockRequirement.query.filter_by(requested_by=self.cashier.id).first()
        self.assertIsNotNone(requirement)
        self.assertEqual(requirement.status, 'PENDING')
        db.session.refresh(product)
        self.assertEqual(product.current_stock, 0)

    def test_requirement_purchase_order_and_receiving_workflow(self):
        self.login_as('cashier_user')
        res = self.client.post('/requirements/new', data={
            'product_id[]': str(self.prod_id),
            'quantity[]': '50',
            'notes': 'Weekly replenishment'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        requirement = StockRequirement.query.filter_by(requested_by=self.cashier.id).first()
        item = requirement.items.first()

        self.logout()
        self.login_as('owner_user')
        res = self.client.post(f'/requirements/{requirement.id}/approve', data={
            f'approved_quantity_{item.id}': '45',
            f'adjustment_reason_{item.id}': 'Storage capacity'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        db.session.refresh(requirement)
        db.session.refresh(item)
        self.assertEqual(requirement.status, 'APPROVED')
        self.assertEqual(item.approved_quantity, 45)

        supplier = Supplier(name='Procurement Supplier', company_name='Procurement Co', phone='555-2222', is_active=True)
        db.session.add(supplier)
        db.session.commit()
        res = self.client.post('/purchase-orders/new', data={
            'stock_requirement_id': str(requirement.id),
            'supplier_id': str(supplier.id),
            'invoice_number': 'SUP-100',
            'purchase_date': date.today().isoformat(),
            'product_id[]': str(self.prod_id),
            'quantity[]': '45',
            'unit_price[]': '1.25'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        purchase = Purchase.query.filter_by(invoice_number='SUP-100').first()
        self.assertIsNotNone(purchase)
        self.assertEqual(purchase.stock_requirement_id, requirement.id)
        purchase_item = purchase.items.first()

        self.logout()
        self.login_as('cashier_user')
        initial_stock = Product.query.get(self.prod_id).current_stock
        res = self.client.post(f'/purchase-orders/{purchase.id}/receive', data={
            'delivery_date': date.today().isoformat(),
            'invoice_number': 'SUP-100',
            'delivery_reference': 'TRUCK-1',
            'notes': 'Partial delivery',
            'purchase_item_id[]': str(purchase_item.id),
            'delivered[]': '30',
            'accepted[]': '27',
            'damaged[]': '2',
            'rejected[]': '1',
            'batch_number[]': 'BATCH-PARTIAL-1',
            'expiry_date[]': '',
            'reason[]': 'One damaged case'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        product = Product.query.get(self.prod_id)
        self.assertEqual(product.current_stock, initial_stock + 27)
        report = GoodsReceivingReport.query.filter_by(purchase_id=purchase.id).first()
        self.assertIsNotNone(report)
        receiving_item = report.items.first()
        self.assertTrue(report.inventory_applied)
        self.assertEqual(receiving_item.delivered_quantity, receiving_item.accepted_quantity + receiving_item.damaged_quantity + receiving_item.rejected_quantity)
        self.assertEqual(receiving_item.outstanding_quantity, 15)

        stock_after_first = product.current_stock
        res = self.client.post(f'/purchase-orders/{purchase.id}/receive', data={
            'delivery_date': date.today().isoformat(),
            'invoice_number': 'SUP-100',
            'purchase_item_id[]': str(purchase_item.id),
            'delivered[]': '15',
            'accepted[]': '15',
            'damaged[]': '0',
            'rejected[]': '0',
            'batch_number[]': 'BATCH-PARTIAL-2',
            'expiry_date[]': '',
            'reason[]': ''
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        product = Product.query.get(self.prod_id)
        self.assertEqual(product.current_stock, stock_after_first + 15)

        first_report = GoodsReceivingReport.query.filter_by(purchase_id=purchase.id).order_by(GoodsReceivingReport.id.asc()).first()
        first_item = first_report.items.first()
        self.logout()
        self.login_as('owner_user')
        stock_before_review = Product.query.get(self.prod_id).current_stock
        res = self.client.post(f'/receiving-reports/{first_report.id}/review', data={
            'action': 'APPROVED',
            'reason': 'Delivery confirmed'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Product.query.get(self.prod_id).current_stock, stock_before_review)

        res = self.client.post(f'/receiving-reports/{first_report.id}/correct', data={
            f'accepted_{first_item.id}': '26',
            f'damaged_{first_item.id}': '3',
            f'rejected_{first_item.id}': '1',
            'correction_reason': 'One accepted unit was damaged'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        db.session.refresh(first_item)
        db.session.refresh(Product.query.get(self.prod_id))
        self.assertEqual(first_item.accepted_quantity, 26)
        self.assertEqual(first_item.damaged_quantity, 3)

    def test_supplier_partial_payment_and_owner_only_access(self):
        supplier = Supplier(name='Payment Supplier', company_name='Payment Co', phone='555-3333', is_active=True)
        db.session.add(supplier)
        db.session.flush()
        purchase = Purchase(
            supplier_id=supplier.id,
            invoice_number='PAY-INV-1',
            purchase_date=date.today(),
            total_amount=1000,
            payment_status='PENDING',
            status='RECEIVED',
            order_status='RECEIVED',
            created_by=self.owner.id
        )
        db.session.add(purchase)
        db.session.commit()

        self.login_as('cashier_user')
        res = self.client.post(f'/suppliers/{supplier.id}/payments', data={'purchase_id': purchase.id, 'amount': '400'})
        self.assertEqual(res.status_code, 403)

        self.logout()
        self.login_as('owner_user')
        self.client.post(f'/suppliers/{supplier.id}/payments', data={
            'purchase_id': str(purchase.id),
            'payment_date': date.today().isoformat(),
            'amount': '400',
            'payment_method': 'BANK',
            'reference_number': 'PAY-400'
        }, follow_redirects=True)
        self.client.post(f'/suppliers/{supplier.id}/payments', data={
            'purchase_id': str(purchase.id),
            'payment_date': date.today().isoformat(),
            'amount': '350',
            'payment_method': 'BANK',
            'reference_number': 'PAY-350'
        }, follow_redirects=True)
        payments = SupplierPayment.query.filter_by(purchase_id=purchase.id).all()
        self.assertEqual(len(payments), 2)
        paid = sum(float(p.amount) for p in payments)
        self.assertEqual(float(purchase.total_amount) - paid, 250)

    def test_owner_adjusted_approval_and_duplicate_protection(self):
        supplier = Supplier(name='Supplier Contact', company_name='Test Supplier', phone='555-0000', is_active=True)
        db.session.add(supplier)
        db.session.flush()
        purchase = Purchase(
            supplier_id=supplier.id,
            invoice_number='INV-APPROVE-1',
            purchase_date=date.today(),
            total_amount=50.0,
            status='PENDING_APPROVAL',
            created_by=self.cashier.id
        )
        db.session.add(purchase)
        db.session.flush()
        item = PurchaseItem(
            purchase_id=purchase.id,
            product_id=self.prod_id,
            batch_number='BATCH-APPROVE-1',
            quantity=50,
            unit_price=1.0,
            subtotal=50.0
        )
        db.session.add(item)
        db.session.commit()

        self.login_as('owner_user')
        res = self.client.post(f'/purchases/{purchase.id}/approve', data={
            f'approved_quantity_{item.id}': '45',
            'quantity_adjustment_reason': 'Five units damaged during delivery'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        db.session.refresh(purchase)
        db.session.refresh(item)
        db.session.refresh(Product.query.get(self.prod_id))
        self.assertEqual(purchase.status, 'APPROVED')
        self.assertEqual(item.quantity, 50)
        self.assertEqual(item.approved_quantity, 45)
        self.assertEqual(Product.query.get(self.prod_id).current_stock, 55)

        res = self.client.post(f'/purchases/{purchase.id}/approve', data={
            f'approved_quantity_{item.id}': '45'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(InventoryBatch.query.filter_by(purchase_item_id=item.id).count(), 1)
        self.assertEqual(Product.query.get(self.prod_id).current_stock, 55)

    def test_cashier_cannot_approve_and_rejection_needs_reason(self):
        supplier = Supplier(name='Supplier Contact', company_name='Reject Supplier', phone='555-1111', is_active=True)
        db.session.add(supplier)
        db.session.flush()
        purchase = Purchase(
            supplier_id=supplier.id,
            invoice_number='INV-REJECT-1',
            purchase_date=date.today(),
            total_amount=10.0,
            status='PENDING_APPROVAL',
            created_by=self.cashier.id
        )
        db.session.add(purchase)
        db.session.flush()
        item = PurchaseItem(
            purchase_id=purchase.id,
            product_id=self.prod_id,
            batch_number='BATCH-REJECT-1',
            quantity=10,
            unit_price=1.0,
            subtotal=10.0
        )
        db.session.add(item)
        db.session.commit()

        self.login_as('cashier_user')
        res = self.client.post(f'/purchases/{purchase.id}/approve', data={f'approved_quantity_{item.id}': '10'})
        self.assertEqual(res.status_code, 403)

        self.logout()
        self.login_as('owner_user')
        res = self.client.post(f'/purchases/{purchase.id}/reject', data={'rejection_reason': ''}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        db.session.refresh(purchase)
        self.assertEqual(purchase.status, 'PENDING_APPROVAL')

        res = self.client.post(f'/purchases/{purchase.id}/reject', data={'rejection_reason': 'Delivery invoice did not match'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        db.session.refresh(purchase)
        self.assertEqual(purchase.status, 'REJECTED')
        self.assertEqual(InventoryBatch.query.filter_by(batch_number='BATCH-REJECT-1').count(), 0)

if __name__ == '__main__':
    unittest.main()
