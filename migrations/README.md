# Procurement migrations

Back up the database before applying migrations.

SQLite:
- `sqlite/001_procurement_schema.sql`

MySQL:
- `mysql/001_procurement_schema.sql`

The application startup helper also adds missing purchase-order columns safely. New procurement tables are created by SQLAlchemy `db.create_all()` and must not be replaced or recreated.
