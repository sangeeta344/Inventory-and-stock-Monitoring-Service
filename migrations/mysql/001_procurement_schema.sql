ALTER TABLE purchases ADD COLUMN stock_requirement_id INT NULL;
ALTER TABLE purchases ADD COLUMN order_status VARCHAR(30) NULL;
ALTER TABLE purchases ADD COLUMN ordered_by INT NULL;
ALTER TABLE purchases ADD COLUMN ordered_at DATETIME NULL;
