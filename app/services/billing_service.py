import time
import random
from datetime import datetime
from app.models import db, Product, Sale, SaleItem, InventoryBatch
from app.services.inventory_service import InventoryService

class BillingService:

    @staticmethod
    def generate_invoice_number():
        """
        Generates a unique invoice number formatted like INV-YYYYMMDD-XXXXX
        """
        date_str = datetime.utcnow().strftime('%Y%m%d')
        random_suffix = random.randint(1000, 9999)
        unique_candidate = f"INV-{date_str}-{random_suffix}"
        
        # Verify uniqueness
        while Sale.query.filter_by(invoice_number=unique_candidate).first():
            random_suffix = random.randint(1000, 9999)
            unique_candidate = f"INV-{date_str}-{random_suffix}"

        return unique_candidate

    @staticmethod
    def find_product_by_barcode(barcode):
        """
        Looks up a product by exact barcode match.
        Returns product dictionary with current available sellable stock and category.
        """
        barcode = str(barcode).strip()
        product = Product.query.filter_by(barcode=barcode, is_active=True).first()
        if not product:
            return None
        
        # Calculate active non-expired stock in batches
        from datetime import date
        today = date.today()
        batches = InventoryBatch.query.filter(
            InventoryBatch.product_id == product.id,
            InventoryBatch.quantity_remaining > 0,
            InventoryBatch.is_active == True,
            db.or_(InventoryBatch.expiry_date == None, InventoryBatch.expiry_date >= today)
        ).all()
        
        sellable_batch_stock = sum(b.quantity_remaining for b in batches)

        return {
            'id': product.id,
            'name': product.name,
            'barcode': product.barcode,
            'selling_price': float(product.selling_price),
            'current_stock': product.current_stock,
            'sellable_stock': sellable_batch_stock,
            'unit_of_measure': product.unit_of_measure,
            'category_name': product.category.name if product.category else '',
            'is_low_stock': product.is_low_stock,
            'is_out_of_stock': product.is_out_of_stock or sellable_batch_stock <= 0
        }

    @staticmethod
    def process_checkout(cashier_id, cart_items, customer_name, customer_phone, 
                         payment_method, discount_amount=0.0, tax_rate=0.0):
        """
        Performs atomic checkout transaction:
        1. Validates each cart item and requested quantity.
        2. Allocates stock using FEFO (First-Expired, First-Out).
        3. Deducts batch stock & product stock.
        4. Writes Sale and SaleItem records.
        5. Commits atomically. If any error occurs, rolls back completely!
        """
        if not cart_items or len(cart_items) == 0:
            return False, "Cart is empty. Please scan or add items before checkout."

        invoice_number = BillingService.generate_invoice_number()

        # Step 1: Pre-validate all items before making any modifications
        validated_plan = []
        subtotal = 0.0

        for item in cart_items:
            product_id = int(item.get('product_id'))
            qty = int(item.get('quantity', 1))

            if qty <= 0:
                return False, f"Invalid quantity ({qty}) specified."

            product = Product.query.get(product_id)
            if not product or not product.is_active:
                return False, f"Product ID {product_id} is inactive or does not exist."

            if product.current_stock < qty:
                return False, f"Insufficient stock for '{product.name}'. Available: {product.current_stock}, Requested: {qty}"

            # Check FEFO allocations
            allocations, err = InventoryService.get_fefo_batches_for_sale(product_id, qty)
            if err:
                return False, f"Stock error for '{product.name}': {err}"

            item_subtotal = float(product.selling_price) * qty
            subtotal += item_subtotal

            validated_plan.append({
                'product': product,
                'quantity': qty,
                'unit_price': float(product.selling_price),
                'item_subtotal': item_subtotal,
                'allocations': allocations
            })

        # Calculate taxes and totals
        discount_amount = max(0.0, float(discount_amount))
        discounted_subtotal = max(0.0, subtotal - discount_amount)
        tax_amount = round(discounted_subtotal * (float(tax_rate) / 100.0), 2)
        final_amount = round(discounted_subtotal + tax_amount, 2)

        try:
            # Create Sale header
            sale = Sale(
                invoice_number=invoice_number,
                transaction_date=datetime.utcnow(),
                cashier_id=cashier_id,
                customer_name=customer_name.strip() if customer_name else 'Walk-in Customer',
                customer_phone=customer_phone.strip() if customer_phone else None,
                subtotal=subtotal,
                discount_amount=discount_amount,
                tax_amount=tax_amount,
                final_amount=final_amount,
                payment_method=payment_method.upper(),
                payment_status='COMPLETED'
            )
            db.session.add(sale)
            db.session.flush() # Populate sale.id

            # Create sale items & execute FEFO stock deduction
            for plan in validated_plan:
                product = plan['product']
                allocations = plan['allocations']

                for alloc in allocations:
                    batch = alloc['batch']
                    alloc_qty = alloc['deduct_qty']
                    alloc_cost = alloc['unit_cost']
                    alloc_subtotal = plan['unit_price'] * alloc_qty

                    sale_item = SaleItem(
                        sale_id=sale.id,
                        product_id=product.id,
                        batch_id=batch.id,
                        quantity=alloc_qty,
                        unit_price=plan['unit_price'],
                        unit_cost=alloc_cost,
                        subtotal=alloc_subtotal
                    )
                    db.session.add(sale_item)

                # Deduct inventory and log movements
                InventoryService.deduct_stock_for_sale(
                    product_id=product.id,
                    allocations=allocations,
                    invoice_number=invoice_number,
                    user_id=cashier_id
                )

            # Atomic commit
            db.session.commit()
            return True, sale

        except Exception as e:
            db.session.rollback()
            return False, f"Checkout failed due to transaction error: {str(e)}"
