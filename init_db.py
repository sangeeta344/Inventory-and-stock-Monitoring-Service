import os
import sys
from app import create_app
from app.models import db, User
from seed_data import seed_database

def init_database():
    app = create_app()
    with app.app_context():
        print("[INIT_DB] Verifying database schema...")
        db.create_all()

        existing_owner = User.query.filter_by(username='owner').first()
        if existing_owner:
            print("[INIT_DB] Existing database data detected. Skipping seed data insertion.")
        else:
            print("[INIT_DB] Fresh database detected. Seeding initial records...")
            seed_database()
        print("[INIT_DB] Database initialization completed successfully.")

if __name__ == '__main__':
    try:
        init_database()
    except Exception as e:
        print(f"[INIT_DB ERROR] Failed to initialize database: {e}", file=sys.stderr)
        sys.exit(1)
