from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, Product, Category, InventoryBatch, StockMovement
from app.services.auth_service import role_required, log_audit
from datetime import date

product_bp = Blueprint('products', __name__)

@product_bp.route('/products')
@login_required
@role_required('OWNER')
def list_products():
    category_id = request.args.get('category_id', type=int)
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'all') # 'all', 'low_stock', 'out_of_stock', 'active', 'inactive'

    query = Product.query

    if category_id:
        query = query.filter(Product.category_id == category_id)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            db.or_(
                Product.name.ilike(search_pattern),
                Product.barcode.ilike(search_pattern),
                Product.description.ilike(search_pattern)
            )
        )

    if status_filter == 'low_stock':
        query = query.filter(Product.current_stock > 0, Product.current_stock <= Product.min_stock_level)
    elif status_filter == 'out_of_stock':
        query = query.filter(Product.current_stock <= 0)
    elif status_filter == 'active':
        query = query.filter(Product.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(Product.is_active == False)

    products = query.order_by(Product.name.asc()).all()
    categories = Category.query.filter_by(is_active=True).order_by(Category.name.asc()).all()

    return render_template(
        'products/list.html',
        products=products,
        categories=categories,
        current_category=category_id,
        current_search=search,
        current_status=status_filter
    )

@product_bp.route('/products/add', methods=['GET', 'POST'])
@login_required
@role_required('OWNER')
def add_product():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id', type=int)
        barcode = request.form.get('barcode', '').strip()
        purchase_price = request.form.get('purchase_price', type=float, default=0.0)
        selling_price = request.form.get('selling_price', type=float, default=0.0)
        initial_stock = request.form.get('initial_stock', type=int, default=0)
        min_stock_level = request.form.get('min_stock_level', type=int, default=5)
        unit_of_measure = request.form.get('unit_of_measure', 'pcs').strip()
        description = request.form.get('description', '').strip()
        is_active = bool(request.form.get('is_active', True))
        
        # Initial batch details if initial stock > 0
        batch_number = request.form.get('batch_number', '').strip() or f"INIT-{barcode[-6:]}"
        expiry_date_str = request.form.get('expiry_date', '').strip()
        expiry_date = None
        if expiry_date_str:
            try:
                expiry_date = date.fromisoformat(expiry_date_str)
            except ValueError:
                pass

        # Validation
        if not name or not barcode or not category_id:
            flash('Product name, barcode, and category are required.', 'danger')
            return redirect(url_for('products.list_products'))

        if Product.query.filter_by(barcode=barcode).first():
            flash(f"Error: A product with barcode '{barcode}' already exists. Barcodes must be unique.", 'danger')
            return redirect(url_for('products.list_products'))

        try:
            product = Product(
                name=name,
                category_id=category_id,
                barcode=barcode,
                purchase_price=purchase_price,
                selling_price=selling_price,
                current_stock=initial_stock,
                min_stock_level=min_stock_level,
                unit_of_measure=unit_of_measure,
                description=description,
                is_active=is_active
            )
            db.session.add(product)
            db.session.flush()

            # If opening stock > 0, create initial inventory batch
            if initial_stock > 0:
                init_batch = InventoryBatch(
                    product_id=product.id,
                    batch_number=batch_number,
                    purchase_date=date.today(),
                    expiry_date=expiry_date,
                    unit_cost=purchase_price,
                    quantity_received=initial_stock,
                    quantity_remaining=initial_stock,
                    is_active=True
                )
                db.session.add(init_batch)
                db.session.flush()

                # Record movement
                movement = StockMovement(
                    product_id=product.id,
                    batch_id=init_batch.id,
                    movement_type='MANUAL_ADJUSTMENT',
                    reference_id='INITIAL-STOCK',
                    quantity_change=initial_stock,
                    quantity_after=initial_stock,
                    notes='Initial opening stock on product creation',
                    created_by=current_user.id
                )
                db.session.add(movement)

            db.session.commit()
            log_audit(current_user.id, 'ADD_PRODUCT', 'PRODUCT_CATALOG', f"Created product {name} (Barcode: {barcode})")
            flash(f"Product '{name}' added successfully!", 'success')

        except Exception as e:
            db.session.rollback()
            flash(f"Failed to add product: {str(e)}", 'danger')

        return redirect(url_for('products.list_products'))

    categories = Category.query.filter_by(is_active=True).order_by(Category.name.asc()).all()
    return render_template('products/form.html', product=None, categories=categories)

@product_bp.route('/products/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('OWNER')
def edit_product(id):
    product = Product.query.get_or_404(id)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id', type=int)
        barcode = request.form.get('barcode', '').strip()
        purchase_price = request.form.get('purchase_price', type=float, default=0.0)
        selling_price = request.form.get('selling_price', type=float, default=0.0)
        min_stock_level = request.form.get('min_stock_level', type=int, default=5)
        unit_of_measure = request.form.get('unit_of_measure', 'pcs').strip()
        description = request.form.get('description', '').strip()
        is_active = bool(request.form.get('is_active'))

        # Check unique barcode conflict
        existing = Product.query.filter(Product.barcode == barcode, Product.id != id).first()
        if existing:
            flash(f"Cannot update: Barcode '{barcode}' is already in use by product '{existing.name}'.", 'danger')
            return redirect(url_for('products.list_products'))

        try:
            product.name = name
            product.category_id = category_id
            product.barcode = barcode
            product.purchase_price = purchase_price
            product.selling_price = selling_price
            product.min_stock_level = min_stock_level
            product.unit_of_measure = unit_of_measure
            product.description = description
            product.is_active = is_active

            db.session.commit()
            log_audit(current_user.id, 'EDIT_PRODUCT', 'PRODUCT_CATALOG', f"Updated product {name} (ID: {id})")
            flash(f"Product '{name}' updated successfully!", 'success')
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating product: {str(e)}", 'danger')

        return redirect(url_for('products.list_products'))

    categories = Category.query.filter_by(is_active=True).order_by(Category.name.asc()).all()
    return render_template('products/form.html', product=product, categories=categories)

@product_bp.route('/products/toggle-status/<int:id>', methods=['POST'])
@login_required
@role_required('OWNER')
def toggle_status(id):
    product = Product.query.get_or_404(id)
    product.is_active = not product.is_active
    db.session.commit()
    status_label = 'Activated' if product.is_active else 'Deactivated'
    log_audit(current_user.id, 'TOGGLE_PRODUCT_STATUS', 'PRODUCT_CATALOG', f"{status_label} product {product.name}")
    flash(f"Product '{product.name}' has been {status_label.lower()}.", 'info')
    return redirect(url_for('products.list_products'))

@product_bp.route('/products/delete/<int:id>', methods=['POST'])
@login_required
@role_required('OWNER')
def delete_product(id):
    product = Product.query.get_or_404(id)
    # Check if sale items or purchase items reference this product
    if product.sale_items.count() > 0 or product.purchase_items.count() > 0:
        # Deactivate instead of hard delete to preserve financial & audit history integrity
        product.is_active = False
        db.session.commit()
        flash(f"Product '{product.name}' has existing sales or purchase records and cannot be deleted. It has been deactivated instead.", 'warning')
    else:
        name = product.name
        db.session.delete(product)
        db.session.commit()
        log_audit(current_user.id, 'DELETE_PRODUCT', 'PRODUCT_CATALOG', f"Deleted product {name}")
        flash(f"Product '{name}' was permanently deleted.", 'success')

    return redirect(url_for('products.list_products'))

# Categories Management
@product_bp.route('/categories', methods=['GET', 'POST'])
@login_required
@role_required('OWNER')
def categories():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()

        if not name:
            flash('Category name is required.', 'danger')
            return redirect(url_for('products.categories'))

        if Category.query.filter_by(name=name).first():
            flash(f"Category '{name}' already exists.", 'danger')
            return redirect(url_for('products.categories'))

        cat = Category(name=name, description=description)
        db.session.add(cat)
        db.session.commit()
        log_audit(current_user.id, 'ADD_CATEGORY', 'CATEGORY_MANAGEMENT', f"Added category {name}")
        flash(f"Category '{name}' created successfully.", 'success')
        return redirect(url_for('products.categories'))

    all_categories = Category.query.order_by(Category.name.asc()).all()
    return render_template('products/categories.html', categories=all_categories)
