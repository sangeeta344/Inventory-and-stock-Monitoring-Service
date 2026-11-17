# Smart Supermarket Management System (AI-Powered & Mobile POS)

A complete, production-grade, responsive web-based **Smart Supermarket Management System** and **Mobile Point-of-Sale (POS)** terminal built with Python Flask, MySQL, Bootstrap 5, Chart.js, ReportLab, and ZXing/HTML5 camera barcode scanning.

The system allows a supermarket owner to manage the entire store through **ONE centralized platform** without purchasing physical barcode scanner guns or thermal billing printers.

---

## 🌟 Key Features

### 1. User Authentication & Role-Based Access Control (RBAC)
- **Two Distinct Roles**: `OWNER` and `CASHIER`.
- Backend route enforcement using the `@role_required` decorator (not just hiding frontend buttons).
- Secure password hashing using Werkzeug `generate_password_hash` and `check_password_hash`.
- Pre-seeded accounts for immediate testing:
  - **Owner**: `owner` / `owner123`
  - **Cashier 1**: `cashier1` / `cashier123`
  - **Cashier 2**: `cashier2` / `cashier123`

### 2. Smartphone & Laptop Camera Barcode Scanning
- **Zero Extra Hardware**: Turns any smartphone camera (rear/environment camera) or laptop webcam into a barcode scanner.
- Powered by `html5-qrcode` & ZXing supporting EAN-13, EAN-8, UPC-A, UPC-E, Code 128, Code 39, and QR codes.
- **Audio Feedback**: Pleasant synth sound synthesized directly via Web Audio API on successful scans.
- Fallback manual barcode input (with Enter-key trigger for standard USB barcode scanner guns) and live typeahead product search.

### 3. POS Billing Terminal & Digital Invoicing
- Fast real-time billing cart with live stock validation.
- Subtotal, customizable discount, and tax calculations.
- Multiple payment methods: `CASH`, `CARD`, `UPI/QR`, `DIGITAL`.
- Unique invoice numbering (`INV-YYYYMMDD-XXXX`).
- Atomic database transactions: stock is deducted only upon confirmed checkout; failed transactions never corrupt stock.
- Instant digital invoice view with browser print layout, thermal receipt formatting, and PDF download.

### 4. Automatic Inventory & FEFO Batch Tracking
- **FEFO (First-Expired, First-Out)**: Automatically fulfills customer sales from the earliest expiring batch first.
- Strict protection: Expired batches are blocked from being sold.
- Never allows negative inventory.
- Complete immutable **Stock Movements Audit Trail** (`SALE`, `PURCHASE_RECEIPT`, `CUSTOMER_RETURN`, `DAMAGE_WASTAGE`, `EXPIRED_WASTAGE`, `MANUAL_ADJUSTMENT`).

### 5. Automated Stock & Expiry Alerts
- Low-stock alerts triggered when inventory &le; minimum stock limit.
- Out-of-stock alerts when inventory reaches zero.
- Shelf-life monitoring: alerts for batches expiring within 30 days and expired batches.
- Notification badges with dismiss and mark-all-read capabilities.

### 6. Customer Return Management
- Invoice lookup to load original purchased items and verify return eligibility.
- Item condition classification:
  - `RESELLABLE`: Automatically restocks sellable inventory batches.
  - `DAMAGED` / `EXPIRED`: Recorded into wastage losses without inflating sellable stock.
- Refund calculations and comprehensive return audit log.

### 7. Supplier & Purchase Management
- Supplier directory with contact info, address, and payment terms.
- Wholesale purchase orders with line items, cost prices, batch numbers, and expiry dates.
- Automatic inventory increments upon marking goods as received.

### 8. Financial Accounting & Profit/Loss Analysis
- **Product-Wise Gross Profit**: Computed from actual inventory batch acquisition costs (`Selling Price - Batch Unit Cost`).
- Itemized operating expenses tracking (Rent, Electricity, Payroll, Maintenance, Supplies).
- Formal Income Statement:
  $$\text{Net Revenue} = \text{Gross Sales} - \text{Customer Returns}$$
  $$\text{Gross Profit} = \text{Net Revenue} - \text{Batch COGS}$$
  $$\text{Net Profit} = \text{Gross Profit} - \text{Wastage Losses} - \text{Operating Expenses}$$

### 9. Business Analytics & Charts
- Interactive Chart.js charts: Daily (past 7 days) and Monthly (past 6 months) sales vs. profit trends.
- Category sales revenue distribution donut chart.
- Product performance rankings: Best-selling, highest revenue drivers, highest profit drivers, and slow-moving items.

### 10. Reports & Exports
- Downloadable formal PDF reports generated via **ReportLab**.
- Downloadable styled Excel spreadsheets generated via **OpenPyXL**.
- Covers Sales, Product Inventory, Low-Stock alerts, Expiry batches, and Profit & Loss.

---

## 🏗️ Technology Stack

- **Backend**: Python 3.13+, Flask, Flask-SQLAlchemy, Flask-Login, PyMySQL, Cryptography
- **Database**: MySQL (with automatic SQLite fallback for instant offline/development runs)
- **Frontend**: HTML5, CSS3, JavaScript (ES6+), Bootstrap 5, Bootstrap Icons, Chart.js
- **Barcode Engine**: HTML5-QRCode / ZXing
- **Reporting**: ReportLab (PDF), OpenPyXL (Excel)

---

## 📁 Directory Structure

```text
D:\Desktop\stockmarket\
├── app/
│   ├── __init__.py          # Flask app factory, config, DB & Login setup
│   ├── config.py            # Environment configurations & URL encoding
│   ├── models/              # SQLAlchemy database models
│   │   ├── __init__.py
│   │   ├── user.py          # User, Employee, AuditLog
│   │   ├── product.py       # Category, Product, InventoryBatch, StockMovement
│   │   ├── supplier.py      # Supplier
│   │   ├── purchase.py      # Purchase, PurchaseItem
│   │   ├── sale.py          # Sale, SaleItem, Return, ReturnItem
│   │   ├── expense.py       # Expense
│   │   └── notification.py  # Notification
│   ├── services/            # Core business logic engines
│   │   ├── __init__.py
│   │   ├── auth_service.py      # RBAC decorator & Audit logger
│   │   ├── inventory_service.py # FEFO stock deduction & batch handling
│   │   ├── billing_service.py   # Atomic POS checkout & invoices
│   │   ├── analytics_service.py # P&L, KPI metrics & sales trends
│   │   └── report_service.py    # ReportLab PDF & OpenPyXL Excel generators
│   ├── routes/              # Modular blueprints
│   │   ├── __init__.py
│   │   ├── auth_routes.py       # Login, logout, profile
│   │   ├── dashboard_routes.py  # Owner dashboard, KPI stats, charts API
│   │   ├── product_routes.py    # Products & Categories CRUD
│   │   ├── billing_routes.py    # POS terminal, barcode lookup, checkout
│   │   ├── inventory_routes.py  # Batches, wastage, movements log
│   │   ├── supplier_routes.py   # Suppliers CRUD
│   │   ├── purchase_routes.py   # Purchases & Receiving
│   │   ├── return_routes.py     # Customer returns
│   │   ├── sales_routes.py      # Completed transactions history
│   │   ├── analytics_routes.py  # Profit & Loss, product performance
│   │   ├── expense_routes.py    # Operating expenses CRUD
│   │   ├── employee_routes.py   # Cashier accounts & audit trail
│   │   └── report_routes.py     # PDF & Excel export hub
│   ├── static/
│   │   ├── css/style.css        # Professional POS styling, dark/light theme
│   │   └── js/
│   │       ├── scanner.js       # Mobile & webcam barcode scanner
│   │       ├── billing.js       # POS cart, calculations, hotkeys
│   │       └── dashboard.js     # Chart.js analytics graphs
│   └── templates/               # Jinja2 responsive templates
│       ├── base.html
│       ├── auth/
│       ├── dashboard/
│       ├── products/
│       ├── billing/
│       ├── inventory/
│       ├── suppliers/
│       ├── purchases/
│       ├── returns/
│       ├── sales/
│       ├── analytics/
│       ├── expenses/
│       ├── employees/
│       └── reports/
├── tests/                       # Automated unit & integration tests
│   ├── test_supermarket.py      # FEFO, POS, P&L, Reports, Auth tests
│   └── test_routes.py           # Route & RBAC restriction tests
├── seed_data.py                 # Initial seed data for supermarket
├── schema.sql                   # Normalized MySQL DDL schema
├── run.py                       # Application entrypoint
├── .env.example                 # Environment configuration template
└── README.md                    # Project documentation
```

---

## 🚀 Installation & Setup Instructions

### 1. Clone or Open the Project
```bash
cd D:\Desktop\stockmarket
```

### 2. Install Required Python Packages
```bash
python -m pip install flask flask-login flask-sqlalchemy pymysql reportlab openpyxl python-dotenv cryptography
```

### 3. Database Configuration (MySQL)
Create a `.env` file in the root directory (or copy from `.env.example`):
```ini
SECRET_KEY=smart-supermarket-secret-key-prod-987654321

# MySQL Database Settings
DB_USER=root
DB_PASSWORD=your_actual_mysql_password
DB_HOST=localhost
DB_PORT=3306
DB_NAME=smart_supermarket

# Set to true to force local SQLite development mode
USE_SQLITE=false

# Store Information
STORE_NAME=Smart Supermarket & HyperMart
STORE_ADDRESS=100 Market Boulevard, Central Commercial District
STORE_PHONE=+1 (555) 987-6543
STORE_EMAIL=billing@smartsupermarket.com
STORE_TAX_NUMBER=GSTIN-98AABCS1234F1Z8
STORE_DEFAULT_TAX_RATE=5.0
```

> **Note**: Passwords with special characters (such as `@`, `#`, `$`, `%`) are automatically URL-encoded by `app/config.py`. The system also auto-creates the `smart_supermarket` database if it does not exist yet.

### 4. Seed Initial Supermarket Data
Run the seeding script to populate users, products with barcodes, inventory batches, and suppliers:
```bash
python seed_data.py
```

### 5. Run the Application
```bash
python run.py
```
Open your browser and navigate to:
👉 **[http://localhost:5000](http://localhost:5000)**

---

## 📱 Testing Mobile Barcode Scanning

Mobile web browsers (Chrome on Android, Safari on iOS) enforce a strict security policy for camera access:
1. **HTTPS or Localhost**: Camera permissions are only granted over `https://` or `http://localhost`.
2. **Local Laptop / Desktop Testing**:
   - Open `http://localhost:5000` in your browser.
   - Go to **POS Terminal (Scan)** (`/billing`).
   - Click **"Scan Product (Camera)"** and allow camera permissions.
   - Hold up a product barcode (e.g. barcode `8901234567890`) to your webcam. The system will beep and immediately add the item to your bill!
3. **Smartphone Testing on Local Wi-Fi**:
   - **Option A (USB Port Forwarding)**: Connect your phone to your PC via USB and use Chrome DevTools port forwarding (`chrome://inspect/#devices`) to forward port `5000` to your smartphone. On your phone, visit `http://localhost:5000`.
   - **Option B (HTTPS Tunnel)**: Expose the Flask development server via an HTTPS tunnel (e.g. `ngrok http 5000` or Cloudflare Tunnel) and open the secure URL on your phone camera.
4. **Barcode Emulation (Without Camera)**:
   - Type or paste any of the pre-seeded barcodes into the barcode input box and press **Enter**:
     - `8901234567890` &rarr; Fresh Whole Milk 1L ($3.49)
     - `8901234567891` &rarr; Farm Fresh Eggs 12-Pack ($4.79)
     - `8901234567892` &rarr; Artisan Sliced Bread 400g ($2.89)
     - `8901234567893` &rarr; Coca-Cola Classic 500ml ($1.99)
     - `8901234567894` &rarr; Lay's Salted Chips 50g ($1.69)
     - `8901234567895` &rarr; Basmati Rice 5kg ($15.99)

---

## 🧪 Running Automated Tests

The project includes a comprehensive 13-test test suite:
```bash
python -m unittest discover tests
```

This verifies:
- User authentication & role checks (`OWNER` vs `CASHIER`)
- Role-Based Access Control (Cashier restricted from `/dashboard`, `/analytics`, `/employees` with HTTP 403)
- FEFO inventory batch allocation priority
- POS checkout & stock deduction atomicity
- Resellable vs damaged customer returns
- Profit & Loss calculations
- ReportLab PDF and OpenPyXL Excel generation

---

## 👥 Default Login Credentials

| Role | Username | Password | Permitted Modules |
| :--- | :--- | :--- | :--- |
| **OWNER** | `owner` | `owner123` | Full access: Dashboard, Products, Inventory, FEFO Batches, Suppliers, Purchases, Sales, P&L, Analytics, Expenses, Staff, Reports |
| **CASHIER** | `cashier1` | `cashier123` | POS Terminal, Barcode Scanning, Billing Cart, Customer Returns, Permitted Sales History |
| **CASHIER** | `cashier2` | `cashier123` | POS Terminal, Barcode Scanning, Billing Cart, Customer Returns, Permitted Sales History |
