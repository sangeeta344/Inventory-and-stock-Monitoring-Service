import os
from flask import Flask
from flask_login import LoginManager
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from app.config import Config
from app.models import db, User, Notification

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this system.'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized_callback():
    from flask import request, jsonify, redirect, url_for, flash
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': 'Session expired or not authenticated. Please log in again.'}), 401
    flash('Please log in to access this page.', 'warning')
    return redirect(url_for('auth.login', next=request.url))

def create_app(config_class=Config):
    app = Flask(__name__)
    if isinstance(config_class, dict):
        app.config.from_mapping(config_class)
    else:
        app.config.from_object(config_class)

    # Test database connectivity
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    if not app.config.get('USE_SQLITE', False):
        try:
            # Check if MySQL server is reachable and ensure database exists
            import pymysql
            raw_conn = pymysql.connect(
                host=app.config['DB_HOST'],
                port=int(app.config['DB_PORT']),
                user=app.config['DB_USER'],
                password=app.config['DB_PASSWORD'],
                connect_timeout=3
            )
            with raw_conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{app.config['DB_NAME']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            raw_conn.commit()
            raw_conn.close()

            # Verify SQLAlchemy connection
            test_engine = create_engine(db_uri, connect_args={'connect_timeout': 3})
            with test_engine.connect():
                pass
            print(f"[DATABASE] Connected to MySQL successfully at {app.config['DB_HOST']}:{app.config['DB_PORT']}/{app.config['DB_NAME']}")
        except Exception as e:
            print(f"[DATABASE WARNING] MySQL connection to {app.config['DB_HOST']} failed: {e}")
            print(f"[DATABASE] Switching to local SQLite fallback database for seamless execution: {app.config['SQLITE_FALLBACK_URI']}")
            app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLITE_FALLBACK_URI']
    else:
        print(f"[DATABASE] Configured to use SQLite: {app.config['SQLALCHEMY_DATABASE_URI']}")

    db.init_app(app)
    login_manager.init_app(app)

    # Register Blueprints
    from app.routes.auth_routes import auth_bp
    from app.routes.dashboard_routes import dashboard_bp
    from app.routes.product_routes import product_bp
    from app.routes.billing_routes import billing_bp
    from app.routes.inventory_routes import inventory_bp
    from app.routes.supplier_routes import supplier_bp
    from app.routes.purchase_routes import purchase_bp
    from app.routes.return_routes import return_bp
    from app.routes.sales_routes import sales_bp
    from app.routes.analytics_routes import analytics_bp
    from app.routes.expense_routes import expense_bp
    from app.routes.employee_routes import employee_bp
    from app.routes.report_routes import report_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(product_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(supplier_bp)
    app.register_blueprint(purchase_bp)
    app.register_blueprint(return_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(expense_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(report_bp)

    # Context processors
    @app.context_processor
    def inject_global_data():
        unread_notifications = 0
        latest_notifications = []
        try:
            unread_notifications = Notification.query.filter_by(is_read=False).count()
            latest_notifications = Notification.query.filter_by(is_read=False)\
                                                    .order_by(Notification.created_at.desc())\
                                                    .limit(5).all()
        except Exception:
            pass

        return {
            'store_name': app.config.get('STORE_NAME', 'Smart Supermarket'),
            'store_phone': app.config.get('STORE_PHONE', ''),
            'store_email': app.config.get('STORE_EMAIL', ''),
            'store_address': app.config.get('STORE_ADDRESS', ''),
            'unread_notifications_count': unread_notifications,
            'latest_notifications': latest_notifications
        }

    return app
