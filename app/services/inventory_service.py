from datetime import date, datetime, timedelta
from app.models import db, Product, InventoryBatch, StockMovement, Notification

class InventoryService:

    @staticmethod
    def get_fefo_batches_for_sale(product_id, required_qty):
        """
        Retrieves active, non-expired batches for a product ordered by FEFO:
        Earliest expiry date first (batches with expiry dates take priority over non-expiring items).
        Expired batches are strictly excluded.
        Returns a list of dicts: [{'batch': batch_obj, 'deduct_qty': int, 'unit_cost': float}]
        """
        today = date.today()
        # Find active batches with quantity > 0 and (expiry_date is NULL OR expiry_date >= today)
        batches = InventoryBatch.query.filter(
            InventoryBatch.product_id == product_id,
            InventoryBatch.quantity_remaining > 0,
            InventoryBatch.is_active == True,
            db.or_(InventoryBatch.expiry_date == None, InventoryBatch.expiry_date >= today)
        ).order_by(
            db.case((InventoryBatch.expiry_date.is_(None), 1), else_=0),
            InventoryBatch.expiry_date.asc(),
            InventoryBatch.purchase_date.asc()
        ).all()

        total_available = sum(b.quantity_remaining for b in batches)
        if total_available < required_qty:
            return None, f"Insufficient sellable stock (Required: {required_qty}, Available in non-expired batches: {total_available})"

        allocations = []
        remaining_needed = required_qty

        for batch in batches:
            if remaining_needed <= 0:
                break
            
            take = min(batch.quantity_remaining, remaining_needed)
            allocations.append({
                'batch': batch,
                'deduct_qty': take,
                'unit_cost': float(batch.unit_cost)
            })
            remaining_needed -= take

        return allocations, None

    @staticmethod
    def deduct_stock_for_sale(product_id, allocations, invoice_number, user_id=None):
        """
        Applies batch deductions, updates product current stock, and creates stock movements.
        Must be executed within a database transaction.
        """
        product = Product.query.get(product_id)
        if not product:
            raise ValueError(f"Product ID {product_id} not found")

        total_deducted = 0
        for alloc in allocations:
            batch = alloc['batch']
            qty = alloc['deduct_qty']

            if batch.quantity_remaining < qty:
                raise ValueError(f"Batch {batch.batch_number} does not have {qty} units remaining.")

            batch.quantity_remaining -= qty
            total_deducted += qty

            # Record stock movement for this batch
            product.current_stock -= qty
            if product.current_stock < 0:
                raise ValueError(f"Sale would cause negative stock for product '{product.name}'!")

            movement = StockMovement(
                product_id=product.id,
                batch_id=batch.id,
                movement_type='SALE',
                reference_id=invoice_number,
                quantity_change=-qty,
                quantity_after=product.current_stock,
                notes=f"Sold via Invoice {invoice_number} (Batch: {batch.batch_number})",
                created_by=user_id
            )
            db.session.add(movement)

        # Check stock alerts
        InventoryService.check_and_create_stock_alert(product)

    @staticmethod
    def receive_purchase_batch(product_id, supplier_id, purchase_item_id, batch_number, 
                               purchase_date, expiry_date, unit_cost, quantity, invoice_number, user_id=None):
        """
        Creates an inventory batch and increments product stock upon purchase receipt.
        """
        product = Product.query.get(product_id)
        if not product:
            raise ValueError(f"Product ID {product_id} not found")

        batch = InventoryBatch(
            product_id=product_id,
            supplier_id=supplier_id,
            purchase_item_id=purchase_item_id,
            batch_number=batch_number,
            purchase_date=purchase_date or date.today(),
            expiry_date=expiry_date,
            unit_cost=unit_cost,
            quantity_received=quantity,
            quantity_remaining=quantity,
            is_active=True
        )
        db.session.add(batch)
        db.session.flush() # get batch id

        # Update product current stock
        product.current_stock += quantity
        
        # Log movement
        movement = StockMovement(
            product_id=product.id,
            batch_id=batch.id,
            movement_type='PURCHASE_RECEIPT',
            reference_id=invoice_number,
            quantity_change=quantity,
            quantity_after=product.current_stock,
            notes=f"Received via Purchase Invoice {invoice_number} (Batch {batch_number})",
            created_by=user_id
        )
        db.session.add(movement)
        return batch

    @staticmethod
    def process_return_item(sale_item, quantity, condition, reason, return_number, user_id=None):
        """
        Processes a returned item:
        - If RESELLABLE: increases stock and logs CUSTOMER_RETURN.
        - If DAMAGED / EXPIRED: does NOT increase sellable stock, logs DAMAGE_WASTAGE / EXPIRED_WASTAGE.
        """
        product = sale_item.product
        
        if condition == 'RESELLABLE':
            # Increase batch quantity if batch exists, or create a return restock
            batch = sale_item.batch
            if batch and batch.is_active and (not batch.expiry_date or batch.expiry_date >= date.today()):
                batch.quantity_remaining += quantity
                batch_id = batch.id
            else:
                # Create a restocked batch
                new_batch = InventoryBatch(
                    product_id=product.id,
                    batch_number=f"RET-{return_number[-6:]}",
                    purchase_date=date.today(),
                    expiry_date=batch.expiry_date if batch else None,
                    unit_cost=sale_item.unit_cost,
                    quantity_received=quantity,
                    quantity_remaining=quantity,
                    is_active=True
                )
                db.session.add(new_batch)
                db.session.flush()
                batch_id = new_batch.id

            product.current_stock += quantity
            movement = StockMovement(
                product_id=product.id,
                batch_id=batch_id,
                movement_type='CUSTOMER_RETURN',
                reference_id=return_number,
                quantity_change=quantity,
                quantity_after=product.current_stock,
                notes=f"Customer return (Resellable): {reason}",
                created_by=user_id
            )
            db.session.add(movement)
        else:
            # Damaged or Expired return
            move_type = 'DAMAGE_WASTAGE' if condition == 'DAMAGED' else 'EXPIRED_WASTAGE'
            movement = StockMovement(
                product_id=product.id,
                batch_id=sale_item.batch_id,
                movement_type=move_type,
                reference_id=return_number,
                quantity_change=0,
                quantity_after=product.current_stock,
                notes=f"Customer return ({condition}): {reason} - discarded into wastage",
                created_by=user_id
            )
            db.session.add(movement)

    @staticmethod
    def record_batch_wastage(batch_id, quantity, wastage_type, reason, user_id=None):
        """
        Discards damaged or expired inventory from a batch and deducts from product stock.
        """
        batch = InventoryBatch.query.get(batch_id)
        if not batch:
            raise ValueError("Batch not found")

        if quantity > batch.quantity_remaining:
            raise ValueError(f"Cannot discard {quantity} items. Only {batch.quantity_remaining} items in batch.")

        product = batch.product
        batch.quantity_remaining -= quantity
        product.current_stock -= quantity
        if product.current_stock < 0:
            product.current_stock = 0

        movement_type = 'EXPIRED_WASTAGE' if wastage_type == 'EXPIRED' else 'DAMAGE_WASTAGE'
        movement = StockMovement(
            product_id=product.id,
            batch_id=batch.id,
            movement_type=movement_type,
            reference_id=f"WASTE-{batch.batch_number}",
            quantity_change=-quantity,
            quantity_after=product.current_stock,
            notes=f"Wastage recorded ({wastage_type}): {reason}",
            created_by=user_id
        )
        db.session.add(movement)
        db.session.commit()
        return True

    @staticmethod
    def check_and_create_stock_alert(product):
        """
        Generates alerts for low stock or out-of-stock products if not already open.
        """
        if product.current_stock <= 0:
            existing = Notification.query.filter_by(
                product_id=product.id,
                type='OUT_OF_STOCK',
                is_read=False
            ).first()
            if not existing:
                notif = Notification(
                    type='OUT_OF_STOCK',
                    title=f"Out of Stock: {product.name}",
                    message=f"Product '{product.name}' (Barcode: {product.barcode}) is completely out of stock!",
                    product_id=product.id
                )
                db.session.add(notif)
        elif product.current_stock <= product.min_stock_level:
            existing = Notification.query.filter_by(
                product_id=product.id,
                type='LOW_STOCK',
                is_read=False
            ).first()
            if not existing:
                notif = Notification(
                    type='LOW_STOCK',
                    title=f"Low Stock Alert: {product.name}",
                    message=f"Product '{product.name}' has reached low stock ({product.current_stock} {product.unit_of_measure} remaining, Min limit: {product.min_stock_level})",
                    product_id=product.id
                )
                db.session.add(notif)

    @staticmethod
    def scan_for_system_alerts():
        """
        System-wide scan for low stock, out of stock, near expiry (within 30 days), and expired batches.
        """
        today = date.today()
        near_expiry_threshold = today + timedelta(days=30)

        # 1. Low and Out of Stock
        products = Product.query.filter_by(is_active=True).all()
        for prod in products:
            InventoryService.check_and_create_stock_alert(prod)

        # 2. Expired batches with stock
        expired_batches = InventoryBatch.query.filter(
            InventoryBatch.is_active == True,
            InventoryBatch.quantity_remaining > 0,
            InventoryBatch.expiry_date != None,
            InventoryBatch.expiry_date < today
        ).all()

        for b in expired_batches:
            existing = Notification.query.filter_by(
                product_id=b.product_id,
                type='EXPIRED',
                is_read=False
            ).first()
            if not existing:
                notif = Notification(
                    type='EXPIRED',
                    title=f"Expired Inventory Batch: {b.product.name}",
                    message=f"Batch {b.batch_number} of '{b.product.name}' expired on {b.expiry_date}. Remaining stock ({b.quantity_remaining}) must be removed from sale.",
                    product_id=b.product_id
                )
                db.session.add(notif)

        # 3. Near expiry batches
        near_expired = InventoryBatch.query.filter(
            InventoryBatch.is_active == True,
            InventoryBatch.quantity_remaining > 0,
            InventoryBatch.expiry_date >= today,
            InventoryBatch.expiry_date <= near_expiry_threshold
        ).all()

        for b in near_expired:
            existing = Notification.query.filter_by(
                product_id=b.product_id,
                type='EXPIRY_NEAR',
                is_read=False
            ).first()
            if not existing:
                days_left = (b.expiry_date - today).days
                notif = Notification(
                    type='EXPIRY_NEAR',
                    title=f"Nearing Expiry: {b.product.name}",
                    message=f"Batch {b.batch_number} of '{b.product.name}' expires in {days_left} days ({b.expiry_date}). Remaining: {b.quantity_remaining}.",
                    product_id=b.product_id
                )
                db.session.add(notif)

        db.session.commit()
