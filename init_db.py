from app import create_app
from app.models import db, User
from seed_data import seed_database

app = create_app()

with app.app_context():
    print("[INIT] Creating database tables...")
    db.create_all()

    if not User.query.filter_by(username='owner').first():
        print("[INIT] Fresh database detected. Seeding demo data...")
        seed_database()
    else:
        print("[INIT] Existing demo database detected. Skipping seed.")

print("[INIT] Database initialization completed.")
