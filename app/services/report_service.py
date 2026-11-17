import io
from datetime import datetime, date
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from app.models import Product, InventoryBatch, Sale, Purchase, Supplier, Return, Expense

class ReportService:

    # -------------------------------------------------------------
    # PDF Report Generator (ReportLab)
    # -------------------------------------------------------------
    @staticmethod
    def generate_pdf(title, headers, data, landscape_mode=False, summary_text=None):
        """
        Builds a clean, professional PDF document using ReportLab SimpleDocTemplate.
        """
        buffer = io.BytesIO()
        page_size = landscape(A4) if landscape_mode else A4
        doc = SimpleDocTemplate(
            buffer,
            pagesize=page_size,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )

        elements = []
        styles = getSampleStyleSheet()

        # Custom header styling
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=16,
            leading=20,
            textColor=colors.HexColor('#0f172a'),
            spaceAfter=6
        )
        
        meta_style = ParagraphStyle(
            'ReportMeta',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=15
        )

        cell_style = ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#1e293b')
        )

        cell_header_style = ParagraphStyle(
            'TableHeaderCell',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=colors.white
        )

        # Header section
        elements.append(Paragraph(f"Smart Supermarket - {title}", title_style))
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        meta_str = f"Generated on: {now_str}"
        if summary_text:
            meta_str += f" | {summary_text}"
        elements.append(Paragraph(meta_str, meta_style))
        elements.append(Spacer(1, 10))

        # Table data preparation
        table_rows = []
        # Header row
        table_rows.append([Paragraph(str(h), cell_header_style) for h in headers])

        # Data rows
        for row in data:
            formatted_row = []
            for item in row:
                formatted_row.append(Paragraph(str(item if item is not None else ''), cell_style))
            table_rows.append(formatted_row)

        if not data:
            empty_row = [Paragraph("No records found for the selected period.", cell_style)] + [Paragraph("", cell_style)] * (len(headers) - 1)
            table_rows.append(empty_row)

        t = Table(table_rows, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#f8fafc')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ]))
        elements.append(t)

        doc.build(elements)
        buffer.seek(0)
        return buffer

    # -------------------------------------------------------------
    # Excel Report Generator (OpenPyXL)
    # -------------------------------------------------------------
    @staticmethod
    def generate_excel(title, headers, data, summary_stats=None):
        """
        Builds a styled Microsoft Excel (.xlsx) workbook using OpenPyXL.
        """
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = title[:30]

        # Styling
        header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        title_font = Font(name="Calibri", size=14, bold=True, color="0F172A")
        subtitle_font = Font(name="Calibri", size=9, italic=True, color="64748B")
        regular_font = Font(name="Calibri", size=10)
        border_thin = Border(
            left=Side(style='thin', color='E2E8F0'),
            right=Side(style='thin', color='E2E8F0'),
            top=Side(style='thin', color='E2E8F0'),
            bottom=Side(style='thin', color='E2E8F0')
        )

        # Title Block
        ws.merge_cells("A1:E1")
        ws["A1"] = f"Smart Supermarket - {title}"
        ws["A1"].font = title_font

        ws.merge_cells("A2:E2")
        ws["A2"] = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ws["A2"].font = subtitle_font

        start_row = 4

        # Add headers
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=start_row, column=col_idx, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Add rows
        current_row = start_row + 1
        for row_data in data:
            for col_idx, val in enumerate(row_data, start=1):
                cell = ws.cell(row=current_row, column=col_idx, value=val)
                cell.font = regular_font
                cell.border = border_thin
                if isinstance(val, (int, float)):
                    cell.alignment = Alignment(horizontal="right")
                else:
                    cell.alignment = Alignment(horizontal="left")
            current_row += 1

        # Adjust column widths automatically
        for col in ws.columns:
            max_len = 0
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or '')
                if len(val) > max_len:
                    max_len = len(val)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 40)

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

    # -------------------------------------------------------------
    # Specific Report Queries & Formatters
    # -------------------------------------------------------------
    @staticmethod
    def get_sales_report_data(start_date=None, end_date=None):
        query = Sale.query.filter(Sale.payment_status == 'COMPLETED')
        if start_date:
            start_dt = datetime.combine(start_date, datetime.min.time())
            query = query.filter(Sale.transaction_date >= start_dt)
        if end_date:
            end_dt = datetime.combine(end_date, datetime.max.time())
            query = query.filter(Sale.transaction_date <= end_dt)

        sales = query.order_by(Sale.transaction_date.desc()).all()
        headers = ['Invoice #', 'Date & Time', 'Cashier', 'Customer', 'Items', 'Subtotal ($)', 'Discount ($)', 'Tax ($)', 'Final ($)', 'Method']
        data = []
        for s in sales:
            data.append([
                s.invoice_number,
                s.transaction_date.strftime('%Y-%m-%d %H:%M'),
                s.cashier.full_name if s.cashier else 'Staff',
                s.customer_name or 'Walk-in',
                s.items.count(),
                f"{float(s.subtotal):.2f}",
                f"{float(s.discount_amount):.2f}",
                f"{float(s.tax_amount):.2f}",
                f"{float(s.final_amount):.2f}",
                s.payment_method
            ])
        return headers, data

    @staticmethod
    def get_inventory_report_data():
        products = Product.query.filter_by(is_active=True).order_by(Product.name.asc()).all()
        headers = ['Barcode', 'Product Name', 'Category', 'Unit', 'Purchase Price ($)', 'Selling Price ($)', 'Stock Qty', 'Min Level', 'Stock Status']
        data = []
        for p in products:
            status = 'Normal'
            if p.is_out_of_stock:
                status = 'OUT OF STOCK'
            elif p.is_low_stock:
                status = 'LOW STOCK'
            data.append([
                p.barcode,
                p.name,
                p.category.name if p.category else 'N/A',
                p.unit_of_measure,
                f"{float(p.purchase_price):.2f}",
                f"{float(p.selling_price):.2f}",
                p.current_stock,
                p.min_stock_level,
                status
            ])
        return headers, data

    @staticmethod
    def get_low_stock_report_data():
        products = Product.query.filter(
            Product.is_active == True,
            Product.current_stock <= Product.min_stock_level
        ).order_by(Product.current_stock.asc()).all()

        headers = ['Barcode', 'Product Name', 'Category', 'Current Stock', 'Min Stock Level', 'Shortage', 'Selling Price ($)']
        data = []
        for p in products:
            shortage = max(0, p.min_stock_level - p.current_stock)
            data.append([
                p.barcode,
                p.name,
                p.category.name if p.category else 'N/A',
                p.current_stock,
                p.min_stock_level,
                shortage,
                f"{float(p.selling_price):.2f}"
            ])
        return headers, data

    @staticmethod
    def get_expiry_report_data():
        today = date.today()
        batches = InventoryBatch.query.filter(
            InventoryBatch.is_active == True,
            InventoryBatch.quantity_remaining > 0,
            InventoryBatch.expiry_date != None
        ).order_by(InventoryBatch.expiry_date.asc()).all()

        headers = ['Product Name', 'Barcode', 'Batch #', 'Supplier', 'Remaining Qty', 'Expiry Date', 'Days Left / Status']
        data = []
        for b in batches:
            delta = (b.expiry_date - today).days
            if delta < 0:
                status = f"EXPIRED ({abs(delta)} days ago)"
            elif delta <= 30:
                status = f"EXPIRING SOON ({delta} days)"
            else:
                status = f"Valid ({delta} days)"
            
            data.append([
                b.product.name if b.product else 'N/A',
                b.product.barcode if b.product else 'N/A',
                b.batch_number,
                b.supplier.name if b.supplier else 'Direct',
                b.quantity_remaining,
                b.expiry_date.strftime('%Y-%m-%d'),
                status
            ])
        return headers, data
