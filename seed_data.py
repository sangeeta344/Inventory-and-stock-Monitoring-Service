import os
from datetime import date, timedelta, datetime
from app import create_app
from app.models import (
    db, User, Employee, Category, Product, Supplier, 
    InventoryBatch, StockMovement, Expense, Notification
)

def seed_database():
    app = create_app()
    with app.app_context():
        print("[SEEDING] Creating all database tables if not existing...")
        db.create_all()

        # Check if already seeded
        if User.query.filter_by(username='owner').first():
            print("[SEEDING] Database already initialized with users. Skipping seeding.")
            return

        print("[SEEDING] Inserting Users and Employees...")
        # 1. Users
        owner = User(
            username='owner',
            email='owner@smartsupermarket.com',
            role='OWNER',
            full_name='Arthur Vance (Owner)',
            phone='+1 555-019-2831',
            is_active=True
        )
        owner.set_password('owner123')
        db.session.add(owner)
        db.session.flush()

        emp_owner = Employee(
            user_id=owner.id,
            employee_code='EMP-001',
            designation='Supermarket General Manager',
            salary=8500.00,
            hire_date=date(2023, 1, 15)
        )
        db.session.add(emp_owner)

        cashier1 = User(
            username='cashier1',
            email='cashier1@smartsupermarket.com',
            role='CASHIER',
            full_name='Sarah Jenkins',
            phone='+1 555-014-9922',
            is_active=True
        )
        cashier1.set_password('cashier123')
        db.session.add(cashier1)
        db.session.flush()

        emp_c1 = Employee(
            user_id=cashier1.id,
            employee_code='EMP-101',
            designation='Lead Cashier',
            salary=2800.00,
            hire_date=date(2024, 3, 1)
        )
        db.session.add(emp_c1)

        cashier2 = User(
            username='cashier2',
            email='cashier2@smartsupermarket.com',
            role='CASHIER',
            full_name='David Miller',
            phone='+1 555-017-8844',
            is_active=True
        )
        cashier2.set_password('cashier123')
        db.session.add(cashier2)
        db.session.flush()

        emp_c2 = Employee(
            user_id=cashier2.id,
            employee_code='EMP-102',
            designation='Junior Cashier',
            salary=2400.00,
            hire_date=date(2024, 6, 15)
        )
        db.session.add(emp_c2)

        # 2. Categories
        print("[SEEDING] Inserting Categories...")
        categories_data = [
            ('Dairy & Eggs', 'Milk, yogurt, cheese, butter, and farm eggs'),
            ('Bakery & Bread', 'Fresh daily breads, artisan buns, and baked treats'),
            ('Beverages & Drinks', 'Sodas, juices, mineral water, tea, and specialty coffee'),
            ('Snacks & Sweets', 'Chips, biscuits, premium chocolates, and confectionery'),
            ('Pantry & Grains', 'Rice, flour, cooking oils, pasta, and dry condiments'),
            ('Fresh Produce', 'Seasonal fruits and farm vegetables'),
            ('Household & Cleaning', 'Detergents, disinfectants, soaps, and kitchen supplies'),
            ('Personal Care', 'Shampoos, dental care, lotions, and soaps')
        ]
        cat_map = {}
        for name, desc in categories_data:
            cat = Category(name=name, description=desc, is_active=True)
            db.session.add(cat)
            db.session.flush()
            cat_map[name] = cat.id

        # 3. Suppliers
        print("[SEEDING] Inserting Suppliers...")
        suppliers_data = [
            ('Robert Chen', 'Apex FMCG Wholesale Corp.', '+1 (555) 301-4455', 'sales@apexfmcg.com', '742 Industrial Parkway, Port Terminal', 'Net 30, Direct Bank Wire'),
            ('Elena Rostova', 'Fresh Farms Dairy Co.', '+1 (555) 412-8877', 'orders@freshfarmsdairy.com', '120 Valley Green Road, Countryside', 'Weekly ACH Auto-Debit'),
            ('Marcus King', 'Golden Harvest Bakery', '+1 (555) 672-1133', 'deliveries@goldenharvest.com', '54 Millers Lane, West End', 'Cash on Delivery (COD)'),
            ('Priya Patel', 'Global Beverage Distributors', '+1 (555) 890-3344', 'accounts@globalbevdist.com', '88 Logistics Boulevard, Suite 400', 'Net 15 Direct Transfer')
        ]
        sup_map = {}
        for name, comp, phone, email, addr, pay in suppliers_data:
            sup = Supplier(
                name=name,
                company_name=comp,
                phone=phone,
                email=email,
                address=addr,
                payment_details=pay,
                is_active=True
            )
            db.session.add(sup)
            db.session.flush()
            sup_map[comp] = sup.id

        # 4. Products & Batches
        print("[SEEDING] Inserting Products and Inventory Batches with FEFO Expiry Tracking...")
        today = date.today()

        products_data = [
            # Name, Cat, Barcode, PurchasePrice, SellingPrice, Stock, MinStock, Unit, Desc, BatchNo, ExpiryDeltaDays, SupplierKey
            (
                'Fresh Whole Milk 1L',
                'Dairy & Eggs',
                '8901234567890',
                2.10, 3.49, 45, 10, 'ltr',
                'Pasteurized, homogenized whole cow milk, enriched with Vitamin D.',
                'MILK-B24-01', 12, 'Fresh Farms Dairy Co.' # Nearing expiry (12 days) to demo alerts!
            ),
            (
                'Farm Fresh Eggs 12-Pack',
                'Dairy & Eggs',
                '8901234567891',
                2.80, 4.79, 60, 15, 'pack',
                'Grade A large brown eggs from free-roaming hens.',
                'EGG-B24-02', 18, 'Fresh Farms Dairy Co.'
            ),
            (
                'Artisan Sliced Bread 400g',
                'Bakery & Bread',
                '8901234567892',
                1.40, 2.89, 30, 8, 'pack',
                'Freshly baked whole wheat sliced sandwich bread.',
                'BRD-B24-03', 5, 'Golden Harvest Bakery' # Near expiry (5 days)
            ),
            (
                'Coca-Cola Classic 500ml',
                'Beverages & Drinks',
                '8901234567893',
                0.90, 1.99, 120, 20, 'bottle',
                'Original taste carbonated cola beverage in chilled bottle.',
                'COKE-B24-04', 180, 'Global Beverage Distributors'
            ),
            (
                'Lay\'s Classic Salted Potato Chips 50g',
                'Snacks & Sweets',
                '8901234567894',
                0.75, 1.69, 85, 25, 'pack',
                'Crispy golden potato chips cooked in pure sunflower oil.',
                'CHIP-B24-05', 90, 'Apex FMCG Wholesale Corp.'
            ),
            (
                'Basmati Rice Premium 5kg',
                'Pantry & Grains',
                '8901234567895',
                9.50, 15.99, 40, 10, 'bag',
                'Long grain aged royal fragrant basmati rice.',
                'RICE-B24-06', 365, 'Apex FMCG Wholesale Corp.'
            ),
            (
                'Dark Roast Coffee Beans 250g',
                'Beverages & Drinks',
                '8901234567896',
                4.20, 7.99, 25, 6, 'pack',
                '100% Arabica artisanal roasted whole beans with chocolate notes.',
                'COFF-B24-07', 120, 'Global Beverage Distributors'
            ),
            (
                'Organic Extra Virgin Olive Oil 500ml',
                'Pantry & Grains',
                '8901234567897',
                5.80, 10.49, 18, 5, 'bottle',
                'Cold-pressed Mediterranean organic olive oil.',
                'OIL-B24-08', 300, 'Apex FMCG Wholesale Corp.'
            ),
            (
                'Antibacterial Dishwashing Liquid 750ml',
                'Household & Cleaning',
                '8901234567898',
                1.95, 3.89, 50, 12, 'bottle',
                'Tough on grease lemon scented dishwashing gel with skin moisturizer.',
                'DISH-B24-09', None, 'Apex FMCG Wholesale Corp.'
            ),
            (
                'Pure Spring Mineral Water 1L',
                'Beverages & Drinks',
                '8901234567899',
                0.40, 0.99, 150, 30, 'bottle',
                'Naturally filtered highland volcanic mineral spring water.',
                'WTR-B24-10', 365, 'Global Beverage Distributors'
            ),
            (
                'Sweet Red Apples 1kg',
                'Fresh Produce',
                '8901234567801',
                1.80, 3.29, 35, 10, 'kg',
                'Crisp and juicy sweet gala red apples.',
                'APP-B24-11', 14, 'Fresh Farms Dairy Co.'
            ),
            (
                'Cheddar Cheese Block 200g',
                'Dairy & Eggs',
                '8901234567802',
                2.50, 4.69, 4, 10, 'pcs', # Low stock demo (4 remaining, min 10)
                'Aged sharp cheddar cheese crafted from pure pasteurized milk.',
                'CHS-B24-12', 45, 'Fresh Farms Dairy Co.'
            ),
            (
                'Corn Flakes Breakfast Cereal 500g',
                'Pantry & Grains',
                '8901234567803',
                2.20, 4.19, 0, 10, 'pack', # Out of stock demo (0 remaining)
                'Crispy toasted golden corn flakes with vitamins and minerals.',
                'CORN-B24-13', 180, 'Apex FMCG Wholesale Corp.'
            ),
            (
                'Toilet Paper 4-Ply Pack of 6',
                'Household & Cleaning',
                '8901234567804',
                3.10, 5.99, 40, 10, 'pack',
                'Ultra-soft embossed 4-ply bamboo fiber bathroom rolls.',
                'TP-B24-14', None, 'Apex FMCG Wholesale Corp.'
            ),
            (
                'Dark Chocolate 70% Bar 100g',
                'Snacks & Sweets',
                '8901234567805',
                1.50, 2.99, 65, 15, 'pcs',
                'Single-origin Belgian rich dark chocolate confectionery bar.',
                'CHOC-B24-15', 200, 'Apex FMCG Wholesale Corp.'
            )
        ]

        for p_data in products_data:
            (p_name, c_name, barcode, p_price, s_price, stock, min_lvl, 
             uom, desc, b_num, exp_days, sup_comp) = p_data

            prod = Product(
                name=p_name,
                category_id=cat_map[c_name],
                barcode=barcode,
                purchase_price=p_price,
                selling_price=s_price,
                current_stock=stock,
                min_stock_level=min_lvl,
                unit_of_measure=uom,
                description=desc,
                is_active=True
            )
            db.session.add(prod)
            db.session.flush()

            # Create batch if stock > 0
            if stock > 0:
                expiry = today + timedelta(days=exp_days) if exp_days else None
                sup_id = sup_map.get(sup_comp)

                batch = InventoryBatch(
                    product_id=prod.id,
                    supplier_id=sup_id,
                    batch_number=b_num,
                    purchase_date=today - timedelta(days=5),
                    expiry_date=expiry,
                    unit_cost=p_price,
                    quantity_received=stock + 10, # assume 10 were sold earlier
                    quantity_remaining=stock,
                    is_active=True
                )
                db.session.add(batch)
                db.session.flush()

                # Stock movement
                sm = StockMovement(
                    product_id=prod.id,
                    batch_id=batch.id,
                    movement_type='PURCHASE_RECEIPT',
                    reference_id=f"SEED-{b_num}",
                    quantity_change=stock,
                    quantity_after=stock,
                    notes='Initial store inventory setup (Sample Demonstration Stock)',
                    created_by=owner.id
                )
                db.session.add(sm)

        # 5. Operating Expenses
        print("[SEEDING] Inserting Initial Store Operating Expenses...")
        expenses_data = [
            ('Store Commercial Rent (Current Month)', 'RENT', 2800.00, today.replace(day=1), 'Monthly supermarket storefront lease'),
            ('Commercial Electricity & Refrigeration Power', 'ELECTRICITY', 740.50, today - timedelta(days=10), 'High-voltage refrigeration cold storage power bill'),
            ('Store Cashiers Bi-weekly Payroll', 'SALARY', 2600.00, today - timedelta(days=7), 'Staff wages and cashier compensation'),
            ('Deep Sanitization & Pest Control Service', 'MAINTENANCE', 350.00, today - timedelta(days=12), 'Monthly health compliance deep sanitize')
        ]
        for title, cat, amt, exp_dt, notes in expenses_data:
            exp = Expense(
                title=title,
                category=cat,
                amount=amt,
                expense_date=exp_dt,
                notes=notes,
                created_by=owner.id
            )
            db.session.add(exp)

        # 6. Commit all seed data
        db.session.commit()
        print("[SEEDING] Database seeded successfully!")
        print("--------------------------------------------------")
        print("Default Logins:")
        print("  OWNER   -> Username: owner    | Password: owner123")
        print("  CASHIER -> Username: cashier1 | Password: cashier123")
        print("  CASHIER -> Username: cashier2 | Password: cashier123")
        print("--------------------------------------------------")

if __name__ == '__main__':
    seed_database()
