import os
from app import create_app
from app.models import db, User
from seed_data import seed_database

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Automatically initialize tables and seed data if fresh database
        db.create_all()
        if not User.query.filter_by(username='owner').first():
            print("[INFO] Fresh database detected. Running automatic initial setup & seed...")
            seed_database()

    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'true').lower() in ('true', '1')

    print("=" * 60)
    print(" SMART SUPERMARKET MANAGEMENT SYSTEM")
    print(f" Server running at: http://localhost:{port}")
    print(" Default Login Accounts:")
    print("   OWNER   -> Username: owner    | Password: owner123")
    print("   CASHIER -> Username: cashier1 | Password: cashier123")
    print("=" * 60)

    app.run(host=host, port=port, debug=debug)
