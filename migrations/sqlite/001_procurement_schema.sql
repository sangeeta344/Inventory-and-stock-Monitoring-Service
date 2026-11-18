ALTER TABLE purchases ADD COLUMN stock_requirement_id INTEGER;
ALTER TABLE purchases ADD COLUMN order_status VARCHAR(30);
ALTER TABLE purchases ADD COLUMN ordered_by INTEGER;
ALTER TABLE purchases ADD COLUMN ordered_at DATETIME;
