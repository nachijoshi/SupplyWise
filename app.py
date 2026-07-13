from flask import Flask, render_template, request, flash, redirect, session, url_for
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from flask import send_file, flash, redirect, url_for
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from pymongo import MongoClient
import datetime
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file relative to this script
dotenv_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=dotenv_path)


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your_secret_key")

mongo_client = MongoClient(os.environ.get("MONGO_URI", "mongodb://localhost:27017/"))
mongo_db = mongo_client['wms_db']
notifications_collection = mongo_db['notifications']

db_config = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'your_mysql_password_here'),
    'database': os.environ.get('DB_NAME', 'wms')
}


def get_db_connection():
    return mysql.connector.connect(**db_config)

def log_admin_activity(event_name, affected_table, affected_user):
    try:
        print(f"Logging: {event_name} | {affected_table} | {affected_user}")   
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO admin(event_name, affected_table, affected_user)
            VALUES (%s, %s, %s)
        """, (event_name, affected_table, affected_user))
        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"Admin Activity Log Error: {err}")

@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('index.html', products=products)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash("Login successful!", "success")

            log_admin_activity('login', 'users', user['id'])

            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'supplier':
                return redirect(url_for('supplier_dashboard'))
            elif user['role'] == 'customer':
                return redirect(url_for('customer_dashboard'))
            elif user['role'] == 'transporter':
                return redirect(url_for('transporter_dashboard'))
            elif user['role'] == 'retailer':
                return redirect(url_for('retailer_dashboard'))
            else:
                flash("Invalid role", "danger")
        else:
            flash("Invalid username or password", "danger")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        role = request.form['role']
        name = request.form['name']
        phone = request.form['phone']
        gstin = request.form.get('gstin', None)
        address = request.form.get('address', None)
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (username, role, name, phone, gstin, address, email, password)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (username, role, name, phone, gstin, address, email, password))
            conn.commit()
            user_id = cursor.lastrowid

            if role == 'customer':
                cursor.execute("INSERT INTO customer (user_id) VALUES (%s)", (user_id,))
            elif role == 'supplier':
                cursor.execute("INSERT INTO supplier (user_id) VALUES (%s)", (user_id,))
            elif role == 'retailer':
                cursor.execute("INSERT INTO retailer (user_id) VALUES (%s)", (user_id,))
            elif role == 'transporter':
                cursor.execute("INSERT INTO transporter (user_id) VALUES (%s)", (user_id,))
            conn.commit()

            log_admin_activity('register', 'users', user_id)

            cursor.close()
            conn.close()
            flash("User registered successfully!", "success")

        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")

        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/admin')
def admin_dashboard():
    if 'role' in session and session['role'] == 'admin':
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()

        cursor.execute("""
            SELECT customer.customer_id, users.username, users.email, users.phone 
            FROM customer JOIN users ON customer.user_id = users.id
        """)
        customers = cursor.fetchall()

        cursor.execute("""
            SELECT supplier.supplier_id, users.username, users.email, users.phone 
            FROM supplier JOIN users ON supplier.user_id = users.id
        """)
        suppliers = cursor.fetchall()

        cursor.execute("""
            SELECT transporter.transporter_id, users.username, users.email, users.phone 
            FROM transporter JOIN users ON transporter.user_id = users.id
        """)
        transporters = cursor.fetchall()

        cursor.execute("""
            SELECT retailer.retailer_id, users.username, users.email, users.phone 
            FROM retailer JOIN users ON retailer.user_id = users.id
        """)
        retailers = cursor.fetchall()

        cursor.execute("""
            SELECT a.timestamp, a.event_name, a.affected_table, u.username, u.role
            FROM admin a
            JOIN users u ON a.affected_user = u.id
            WHERE a.event_name IN ('login', 'register')
            ORDER BY a.timestamp DESC
        """)
        login_logs = cursor.fetchall()

        cursor.execute("""
            SELECT inventory.inventory_id, products.name AS product_name, products.company, 
                   products.category, inventory.stock_qty, inventory.sell_price,
                   users.username AS owner, inventory.owner_role 
            FROM inventory 
            JOIN products ON inventory.product_id = products.product_id 
            JOIN users ON inventory.owner_id = users.id;
        """)
        inventory = cursor.fetchall()

        cursor.execute("""
            SELECT product_id, name, company, category, description 
            FROM products;
        """)
        products = cursor.fetchall()

        cursor.execute("""
            SELECT r.rc_transaction_id AS transaction_id, 
                   cu.username AS customer_name, 
                   p.name AS product_name, 
                   r.quantity, 
                   r.total_price AS total_amount, 
                   r.transaction_date AS timestamp
            FROM retailer_customer_transactions r
            JOIN users cu ON r.customer_id = cu.id
            JOIN products p ON r.product_id = p.product_id
            ORDER BY r.transaction_date DESC;
        """)
        customer_transactions = cursor.fetchall()

        cursor.execute("""
            SELECT s.sr_transaction_id AS transaction_id, 
                   su.username AS supplier_name, 
                   ru.username AS retailer_name, 
                   p.name AS product_name, 
                   s.quantity, 
                   s.total_price AS total_amount, 
                   s.transaction_date AS timestamp
            FROM supplier_retailer_transactions s
            JOIN users su ON s.supplier_id = su.id
            JOIN users ru ON s.retailer_id = ru.id
            JOIN products p ON s.product_id = p.product_id
            ORDER BY s.transaction_date DESC;
        """)
        retailer_transactions = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('admin_dashboard.html',
                               users=users,
                               customers=customers,
                               suppliers=suppliers,
                               transporters=transporters,
                               retailers=retailers,
                               logs=login_logs,
                               inventory=inventory,
                               products=products,
                               customer_transactions=customer_transactions,
                               retailer_transactions=retailer_transactions)

    return redirect(url_for('login'))

@app.route('/supplier')
def supplier_dashboard():
    if 'user_id' not in session or session.get('role') != 'supplier':
        return redirect(url_for('login'))

    supplier_id = session['user_id']

    # Get date filter parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Notifications from MongoDB
    notifications = list(notifications_collection.find({
        "receiver_id": supplier_id,
        "receiver_role": "supplier"
    }).sort("timestamp", -1))

    # Connect to DB
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch products for dropdown/filter if needed
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    # Sales Report Query like Retailer
    sales_query = """
        SELECT 
            p.name AS product_name,
            SUM(srt.quantity) AS total_quantity,
            SUM(srt.total_price) AS total_sales,
            COUNT(DISTINCT srt.sr_transaction_id) AS transaction_count
        FROM supplier_retailer_transactions srt
        JOIN products p ON srt.product_id = p.product_id
        WHERE srt.supplier_id = %s
    """
    sales_params = [supplier_id]

    if start_date:
        sales_query += " AND srt.transaction_date >= %s"
        sales_params.append(start_date)
    if end_date:
        sales_query += " AND srt.transaction_date <= %s"
        sales_params.append(end_date + " 23:59:59")

    sales_query += """
        GROUP BY p.product_id, p.name
        ORDER BY total_sales DESC
    """

    cursor.execute(sales_query, tuple(sales_params))
    sales_data = cursor.fetchall()

    total_sales = sum(item['total_sales'] for item in sales_data) if sales_data else 0
    total_items_sold = sum(item['total_quantity'] for item in sales_data) if sales_data else 0

    cursor.close()
    conn.close()

    return render_template("supplier_dashboard.html",
                           notifications=notifications,
                           products=products,
                           sales_data=sales_data,
                           total_sales=total_sales,
                           total_items_sold=total_items_sold,
                           start_date=start_date,
                           end_date=end_date,
                           has_date_filter=bool(start_date or end_date))

@app.route('/download_supplier_report')
def download_supplier_report():
    if 'user_id' not in session or session.get('role') != 'supplier':
        return redirect(url_for('login'))

    supplier_id = session['user_id']
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Query for sales data with the same filtering
    sales_query = """
        SELECT 
            p.name AS product_name,
            SUM(srt.quantity) AS total_quantity,
            SUM(srt.total_price) AS total_sales,
            COUNT(DISTINCT srt.sr_transaction_id) AS transaction_count
        FROM supplier_retailer_transactions srt
        JOIN products p ON srt.product_id = p.product_id
        WHERE srt.supplier_id = %s
    """
    sales_params = [supplier_id]

    if start_date:
        sales_query += " AND srt.transaction_date >= %s"
        sales_params.append(start_date)
    if end_date:
        sales_query += " AND srt.transaction_date <= %s"
        sales_params.append(end_date + " 23:59:59")

    sales_query += """
        GROUP BY p.product_id, p.name
        ORDER BY total_sales DESC
    """

    cursor.execute(sales_query, tuple(sales_params))
    sales_data = cursor.fetchall()

    # Calculate totals
    total_sales = sum(item['total_sales'] for item in sales_data) if sales_data else 0
    total_items_sold = sum(item['total_quantity'] for item in sales_data) if sales_data else 0

    cursor.close()
    conn.close()

    # Generate PDF report
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    # Header
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(width / 2, y - 10, "SUPPLIER SALES REPORT")
    pdf.setFont("Helvetica", 12)

    # Supplier info
    pdf.drawString(60, y - 30, f"Supplier ID: {supplier_id}")
    pdf.drawRightString(width - 60, y - 30, f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # Date range
    date_range = ""
    if start_date and end_date:
        date_range = f"From {start_date} to {end_date}"
    elif start_date:
        date_range = f"From {start_date}"
    elif end_date:
        date_range = f"Until {end_date}"

    if date_range:
        pdf.drawCentredString(width / 2, y - 50, date_range)

    y -= 80

    # Summary
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(60, y, "Summary:")
    y -= 20
    pdf.setFont("Helvetica", 12)
    pdf.drawString(60, y, f"Total Sales: ₹{total_sales:.2f}")
    y -= 20
    pdf.drawString(60, y, f"Total Items Sold: {total_items_sold}")
    y -= 30

    # Table headers
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(60, y, "Product")
    pdf.drawString(200, y, "Qty Sold")
    pdf.drawString(280, y, "Revenue (₹)")
    pdf.drawString(380, y, "Transactions")
    pdf.line(50, y - 5, width - 50, y - 5)
    y -= 20

    # Table rows
    pdf.setFont("Helvetica", 12)
    for item in sales_data:
        pdf.drawString(60, y, item['product_name'])
        pdf.drawString(200, y, str(item['total_quantity']))
        pdf.drawString(280, y, f"{item['total_sales']:.2f}")
        pdf.drawString(380, y, str(item['transaction_count']))
        y -= 20
        if y < 100:
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica", 12)

    pdf.save()
    buffer.seek(0)

    filename = f"supplier_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

@app.route('/customer')
def customer_dashboard():
    if 'role' in session and session['role'] == 'customer':
        user_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Fetch product listings
        cursor.execute("""
            SELECT inventory.*, products.name AS product_name, users.name AS owner_name
            FROM inventory 
            JOIN products ON inventory.product_id = products.product_id
            JOIN users ON inventory.owner_id = users.id
            WHERE inventory.owner_role = 'retailer'
        """)
        products = cursor.fetchall()

        # Fetch customer invoices
        # Fetch customer invoices (one row per invoice)
        cursor.execute("""
    SELECT 
        i.invoice_id,
        u.name AS retailer_name,
        SUM(rct.quantity) AS quantity,
        SUM(rct.total_price) AS total_price,
        i.address,
        i.created_at
    FROM invoice i
    JOIN retailer_customer_transactions rct 
        ON rct.retailer_id = i.retailer_id AND rct.transaction_date = i.created_at
    JOIN users u ON rct.retailer_id = u.id
    WHERE rct.customer_id = %s
    GROUP BY i.invoice_id, u.name, i.address, i.created_at
    ORDER BY i.created_at DESC
""", (user_id,))
        customer_invoices = cursor.fetchall()


        # Fetch feedback and calculate average ratings
        feedback_data = fetch_feedback_from_database()

        # Prepare product display with feedback
        product_map = {product['inventory_id']: product for product in products}
        combined_products = list(product_map.values())

        for product_item in combined_products:
            inventory_id = product_item['inventory_id']
            product_feedback = [fb for fb in feedback_data if fb['inventory_id'] == inventory_id]
            avg_rating = sum(fb['rating'] for fb in product_feedback) / len(product_feedback) if product_feedback else 0
            product_item['avg_rating'] = avg_rating
            product_item['feedback_count'] = len(product_feedback)

        # ✅ Fetch confirmation-style notifications directly from transaction table
        cursor.execute("""
            SELECT 
                rct.transaction_date AS timestamp,
                p.name AS product_name
            FROM retailer_customer_transactions rct
            JOIN products p ON rct.product_id = p.product_id
            WHERE rct.customer_id = %s
            ORDER BY rct.transaction_date DESC
            LIMIT 10
        """, (user_id,))
        raw_notifications = cursor.fetchall()

        # Build notification messages
        notifications = [{
            'message': f"Your order is confirmed for {row['product_name']}.",
            'timestamp': row['timestamp']
        } for row in raw_notifications]

        return render_template(
            'customer_dashboard.html',
            products=combined_products,
            invoices=customer_invoices,
            feedback=feedback_data,
            notifications=notifications
        )

    return redirect(url_for('login'))

@app.route('/transporter')
def transporter_dashboard():
    if 'role' in session and session['role'] == 'transporter':
        user_id = session['user_id']
        conn = get_db_connection()  # get your DB connection
        cur = conn.cursor()

        # Get transporter's ID from the transporter table
        cur.execute("SELECT transporter_id FROM transporter WHERE user_id = %s", (user_id,))
        result = cur.fetchone()

        if result:
            transporter_id = result[0]

            # Supplier to Retailer Orders (add ORDER BY to fetch latest)
            cur.execute("""
                SELECT srt.sr_transaction_id, u1.name AS supplier_name, u2.name AS retailer_name, 
                       srt.product_id, srt.quantity, srt.total_price, srt.status, srt.transaction_date
                FROM supplier_retailer_transactions srt
                JOIN users u1 ON srt.supplier_id = u1.id
                JOIN users u2 ON srt.retailer_id = u2.id
                WHERE srt.transporter_id = %s AND srt.status != 'delivered'
                ORDER BY srt.transaction_date
            """, (transporter_id,))
            sr_orders = cur.fetchall()

            # Retailer to Customer Orders (add ORDER BY to fetch latest)
            cur.execute("""
                SELECT rct.rc_transaction_id, u1.name AS retailer_name, u2.name AS customer_name, 
                       rct.product_id, rct.quantity, rct.total_price, rct.status, rct.transaction_date
                FROM retailer_customer_transactions rct
                JOIN users u1 ON rct.retailer_id = u1.id
                JOIN users u2 ON rct.customer_id = u2.id
                WHERE rct.transporter_id = %s AND rct.status != 'delivered'
                ORDER BY rct.transaction_date
            """, (transporter_id,))
            rc_orders = cur.fetchall()

            cur.close()
            conn.close()

            return render_template('transporter_dashboard.html', sr_orders=sr_orders, rc_orders=rc_orders)

    return redirect(url_for('login'))

@app.route('/retailer')
def retailer_dashboard():
    if 'role' in session and session['role'] == 'retailer':
        retailer_id = session['user_id']

        # Get date filter parameters from request
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # MongoDB notifications
        notifications = list(notifications_collection.find(
            {"receiver_role": "retailer", "receiver_id": retailer_id}
        ).sort("timestamp", -1))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Supplier inventory
        cursor.execute("""
            SELECT 
                inventory.*, 
                products.name AS product_name,
                users.name AS owner_name
            FROM inventory 
            JOIN products ON inventory.product_id = products.product_id
            JOIN users ON inventory.owner_id = users.id
            WHERE inventory.owner_role = 'supplier'
        """)
        supplier_inventory = cursor.fetchall()

        # Retailer's own inventory
        cursor.execute("""
            SELECT 
                inventory.*, 
                products.name AS product_name
            FROM inventory 
            JOIN products ON inventory.product_id = products.product_id
            WHERE inventory.owner_id = %s AND inventory.owner_role = 'retailer'
        """, (retailer_id,))
        retailer_inventory = cursor.fetchall()

        # Build invoice query with optional date filtering
        # Replace your invoice query section with:
        invoice_query = """
    SELECT 
        i.invoice_id,
        i.created_at,
        i.address,
        SUM(sr.quantity) AS quantity,
        SUM(sr.total_price) AS total_price
    FROM invoice i
    JOIN supplier_retailer_transactions sr 
        ON sr.retailer_id = i.retailer_id
        AND sr.transaction_date = i.created_at
    WHERE i.retailer_id = %s
"""

        invoice_params = [retailer_id]

        if start_date:
            invoice_query += " AND i.created_at >= %s"
            invoice_params.append(start_date)
        if end_date:
            invoice_query += " AND i.created_at <= %s"
            invoice_params.append(end_date + " 23:59:59")

        invoice_query += """
    GROUP BY i.invoice_id, i.created_at, i.address
    ORDER BY i.created_at DESC
"""

        cursor.execute(invoice_query, tuple(invoice_params))
        invoices = cursor.fetchall()


        # Corrected Sales data query from customers to retailer
        sales_query = """
    SELECT 
        p.name AS product_name,
        SUM(rc.quantity) AS total_quantity,
        SUM(rc.total_price) AS total_sales,
        COUNT(DISTINCT rc.rc_transaction_id) AS transaction_count
    FROM retailer_customer_transactions rc
    JOIN products p ON rc.product_id = p.product_id
    WHERE rc.retailer_id = %s 
"""

        sales_params = [retailer_id]

        if start_date:
            sales_query += " AND rc.transaction_date >= %s"
            sales_params.append(start_date)
        if end_date:
            sales_query += " AND rc.transaction_date <= %s"
            sales_params.append(end_date + " 23:59:59")

        sales_query += """
    GROUP BY p.product_id, p.name
    ORDER BY total_sales DESC
"""

        cursor.execute(sales_query, tuple(sales_params))
        sales_data = cursor.fetchall()

        # Calculate total sales for the period
        total_sales = sum(item['total_sales'] for item in sales_data) if sales_data else 0
        total_items_sold = sum(item['total_quantity'] for item in sales_data) if sales_data else 0

        cursor.close()
        conn.close()

        # Feedback data
        feedback_data = fetch_feedback_from_database()
        for item in supplier_inventory + retailer_inventory:
            item_feedback = [f for f in feedback_data if f.get('inventory_id') == item['inventory_id']]
            item['avg_rating'] = sum(f['rating'] for f in item_feedback) / len(item_feedback) if item_feedback else 0
            item['feedback_count'] = len(item_feedback)

        return render_template(
            'retailer_dashboard.html',
            inventory=supplier_inventory,
            retailer_inventory=retailer_inventory,
            invoices=invoices,
            notifications=notifications,
            feedback=feedback_data,
            sales_data=sales_data,
            total_sales=total_sales,
            total_items_sold=total_items_sold,
            start_date=start_date,
            end_date=end_date,
            has_date_filter=bool(start_date or end_date)
        )
    return redirect(url_for('login'))

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        flash("Please log in to view your cart.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT c.cart_id, c.product_id, c.inventory_id, c.quantity,
                   p.name AS product_name,
                   i.sell_price AS price,
                   i.stock_qty
            FROM cart c
            JOIN products p ON c.product_id = p.product_id
            JOIN inventory i ON c.inventory_id = i.inventory_id
            WHERE c.user_id = %s
        """, (user_id,))

        cart_items = cursor.fetchall()
        grand_total = sum(item['price'] * item['quantity'] for item in cart_items)
        session['grand_total'] = grand_total

    except mysql.connector.Error as err:
        flash(f"Database Error: {err}", "danger")
        cart_items = []
        session['grand_total'] = 0

    finally:
        cursor.close()
        conn.close()

    return render_template('cart.html', cart_items=cart_items, grand_total=grand_total)

@app.route('/add_product', methods=['POST'])
def add_product():
    if 'role' in session and session['role'] == 'supplier':
        name = request.form['name']
        company = request.form['company']
        category = request.form['category']
        description = request.form.get('description', '')

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO products (name, company, category, description)
                VALUES (%s, %s, %s, %s)
            """, (name, company, category, description))
            conn.commit()
            cursor.close()
            conn.close()
            flash("Product added successfully!", "success")

            log_admin_activity("Product Added", "products", session['user_id'])

        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")

        return redirect(url_for('supplier_dashboard'))

    return redirect(url_for('login'))

@app.route('/add_inventory', methods=['POST'])
def add_inventory():
    owner_id = session['user_id']
    owner_role = request.form['owner_role']
    product_name = request.form['product']
    stock_qty = request.form['stock_qty']
    sell_price = request.form['sell_price']

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if the product exists in the products table
        cursor.execute("SELECT product_id FROM products WHERE name = %s", (product_name,))
        product = cursor.fetchone()

        if not product:
            flash("Product not found. Please add it first!", "danger")
            return redirect(url_for('supplier_dashboard'))

        product_id = product['product_id']

        # Check if the product already exists in the supplier's inventory with the same price
        cursor.execute("""
            SELECT inventory_id, stock_qty FROM inventory
            WHERE product_id = %s AND owner_id = %s AND sell_price = %s
        """, (product_id, owner_id, sell_price))

        existing_inventory = cursor.fetchone()

        if existing_inventory:
            # If the product already exists, update the stock quantity
            new_stock_qty = existing_inventory['stock_qty'] + int(stock_qty)
            cursor.execute("""
                UPDATE inventory 
                SET stock_qty = %s 
                WHERE inventory_id = %s
            """, (new_stock_qty, existing_inventory['inventory_id']))
            flash("Inventory quantity updated successfully!", "success")
        else:
            # If the product does not exist, insert a new inventory entry
            cursor.execute("""
                INSERT INTO inventory (product_id, owner_id, owner_role, stock_qty, sell_price)
                VALUES (%s, %s, %s, %s, %s)
            """, (product_id, owner_id, owner_role, stock_qty, sell_price))
            flash("Inventory added successfully!", "success")

        conn.commit()

    except mysql.connector.Error as err:
        flash(f"Error: {err}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('supplier_dashboard'))

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        flash("Please log in to add items to cart.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    product_id = request.form['product_id']
    inventory_id = request.form['inventory_id']
    quantity = int(request.form['quantity'])
    price=float(request.form['price'])

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get stock for the selected inventory_id
        cursor.execute("SELECT stock_qty FROM inventory WHERE inventory_id = %s", (inventory_id,))
        inventory_item = cursor.fetchone()

        if not inventory_item:
            flash("Invalid inventory selection.", "danger")
            return redirect(url_for('cart'))

        available_stock = inventory_item[0]

        # Check if item already exists in the cart for that inventory_id
        cursor.execute("SELECT quantity FROM cart WHERE user_id = %s AND inventory_id = %s ", (user_id, inventory_id))
        existing_item = cursor.fetchone()

        if existing_item:
            current_quantity = existing_item[0]
            new_quantity = current_quantity + quantity
            if new_quantity > available_stock:
                flash("Cannot add to cart: exceeds available stock!", "danger")
            else:
                cursor.execute("UPDATE cart SET quantity = %s WHERE user_id = %s AND inventory_id = %s",
                               (new_quantity, user_id, inventory_id))
                flash("Quantity updated in cart!", "success")
        else:
            if quantity > available_stock:
                flash("Cannot add to cart: exceeds available stock!", "danger")
            else:
                cursor.execute("INSERT INTO cart (user_id, product_id, inventory_id, quantity) VALUES (%s, %s, %s, %s)",
                               (user_id, product_id, inventory_id, quantity))
                flash("Item added to cart!", "success")

        conn.commit()
    except mysql.connector.Error as err:
        flash(f"Database Error: {err}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('cart'))

@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    if 'user_id' not in session:
        flash("Please log in to modify your cart.", "warning")
        return redirect(url_for('login'))

    cart_id = request.form.get('cart_id')

    if not cart_id:
        flash("Invalid request.", "danger")
        return redirect(url_for('cart'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cart WHERE cart_id = %s", (cart_id,))
        conn.commit()
        flash("Item removed from cart.", "success")
    except mysql.connector.Error as err:
        flash(f"Database Error: {err}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('cart'))

@app.route('/buy_item', methods=['POST'])
def buy_item():
    if 'user_id' not in session:
        flash("Please login to complete the purchase.", "danger")
        return redirect(url_for('login'))

    user_id = session['user_id']
    role = session.get('role')
    address = request.form.get('address')

    if not address:
        flash("Address is required to complete the purchase.", "danger")
        return redirect(url_for('retailer_dashboard') if role == 'retailer' else url_for('customer_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT transporter_id FROM transporter
            ORDER BY del_count ASC, transporter_id ASC LIMIT 1
        """)
        transporter = cursor.fetchone()
        transporter_id = transporter[0] if transporter else None

        cursor.execute("""
            SELECT c.product_id, c.inventory_id, c.quantity, i.stock_qty, i.sell_price, i.owner_id
            FROM cart c
            JOIN inventory i ON c.inventory_id = i.inventory_id
            WHERE c.user_id = %s AND i.owner_role = %s
        """, (user_id, 'supplier' if role == 'retailer' else 'retailer'))
        cart_items = cursor.fetchall()

        if not cart_items:
            flash("Cart is empty.", "warning")
            return redirect(url_for('retailer_dashboard') if role == 'retailer' else url_for('customer_dashboard'))

        cursor.execute("SELECT NOW()")
        transaction_time = cursor.fetchone()[0]

        # Insert invoice once
        invoice_retailer_id = user_id if role == 'retailer' else cart_items[0][5]  # retailer_id
        cursor.execute("""
            INSERT INTO invoice (retailer_id, address, created_at)
            VALUES (%s, %s, %s)
        """, (invoice_retailer_id, address, transaction_time))
        invoice_id = cursor.lastrowid

        for product_id, inventory_id, quantity, stock_qty, price, seller_id in cart_items:
            total_price = float(price) * int(quantity)

            if role == 'retailer':
                cursor.execute("""
                    INSERT INTO supplier_retailer_transactions 
                    (supplier_id, retailer_id, transporter_id, product_id, quantity, total_price, status, transaction_date)
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s)
                """, (seller_id, user_id, transporter_id, product_id, quantity, total_price, transaction_time))

                notifications_collection.insert_one({
                    "receiver_role": "supplier",
                    "receiver_id": seller_id,
                    "message": f"Retailer {user_id} purchased {quantity}x of Product {product_id}.",
                    "timestamp": datetime.datetime.utcnow(),
                    "read": False
                })

                cursor.execute("""
                    SELECT inventory_id, stock_qty FROM inventory 
                    WHERE owner_id = %s AND owner_role = 'retailer' AND product_id = %s AND sell_price = %s
                """, (user_id, product_id, price))
                existing = cursor.fetchone()

                if existing:
                    retailer_inventory_id, existing_qty = existing
                    cursor.execute("""
                        UPDATE inventory SET stock_qty = %s 
                        WHERE inventory_id = %s
                    """, (existing_qty + quantity, retailer_inventory_id))
                else:
                    cursor.execute("""
                        INSERT INTO inventory (product_id, owner_id, owner_role, stock_qty, sell_price)
                        VALUES (%s, %s, 'retailer', %s, %s)
                    """, (product_id, user_id, quantity, price))

            elif role == 'customer':
                cursor.execute("""
                    INSERT INTO retailer_customer_transactions 
                    (retailer_id, customer_id, transporter_id, product_id, quantity, total_price, status, transaction_date)
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s)
                """, (seller_id, user_id, transporter_id, product_id, quantity, total_price, transaction_time))

                notifications_collection.insert_one({
                    "receiver_role": "retailer",
                    "receiver_id": seller_id,
                    "message": f"Customer {user_id} purchased {quantity}x of Product {product_id}.",
                    "timestamp": datetime.datetime.utcnow(),
                    "read": False
                })

            new_stock = stock_qty - quantity
            if new_stock < 0:
                flash(f"Insufficient stock for product ID {product_id}", "danger")
                conn.rollback()
                return redirect(url_for('retailer_dashboard') if role == 'retailer' else url_for('customer_dashboard'))
            elif new_stock > 0:
                cursor.execute("UPDATE inventory SET stock_qty = %s WHERE inventory_id = %s", (new_stock, inventory_id))

        cursor.execute("DELETE FROM cart WHERE user_id = %s", (user_id,))
        for _, inventory_id, quantity, stock_qty, _, _ in cart_items:
            if stock_qty - quantity == 0:
                cursor.execute("DELETE FROM inventory WHERE inventory_id = %s", (inventory_id,))

        if transporter_id:
            cursor.execute("UPDATE transporter SET del_count = del_count + 1 WHERE transporter_id = %s", (transporter_id,))

        conn.commit()
        flash("Transaction successful! Invoice generated and transporter assigned.", "success")

    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Database Error: {err}", "danger")

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('retailer_dashboard') if role == 'retailer' else url_for('customer_dashboard'))

@app.route('/update_price', methods=['POST'])
def update_price():
    if 'role' not in session or session['role'] != 'retailer':
        return redirect(url_for('login'))

    inventory_id = request.form.get('inventory_id')
    new_price = float(request.form.get('new_price'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get current product_id and stock_qty of the item being updated
        cursor.execute("""
            SELECT product_id, stock_qty FROM inventory 
            WHERE inventory_id = %s AND owner_id = %s AND owner_role = 'retailer'
        """, (inventory_id, session['user_id']))
        item = cursor.fetchone()

        if not item:
            flash("Inventory item not found.", "danger")
            return redirect(url_for('retailer_dashboard'))

        product_id, qty = item

        # Check if another inventory entry exists with the same product and new price
        cursor.execute("""
            SELECT inventory_id, stock_qty FROM inventory 
            WHERE product_id = %s AND sell_price = %s AND owner_id = %s AND owner_role = 'retailer' AND inventory_id != %s
        """, (product_id, new_price, session['user_id'], inventory_id))
        existing = cursor.fetchone()

        if existing:
            # Merge quantities
            existing_inventory_id, existing_qty = existing
            new_total_qty = existing_qty + qty

            cursor.execute("""
                UPDATE inventory SET stock_qty = %s 
                WHERE inventory_id = %s
            """, (new_total_qty, existing_inventory_id))

            # Delete the original item since it's merged
            cursor.execute("DELETE FROM inventory WHERE inventory_id = %s", (inventory_id,))
        else:
            # Just update the price
            cursor.execute("""
                UPDATE inventory
                SET sell_price = %s
                WHERE inventory_id = %s
            """, (new_price, inventory_id))

        conn.commit()
        flash("Price updated successfully!", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Error updating price: {e}", "danger")

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('retailer_dashboard'))

@app.route('/download_invoice/<int:invoice_id>')
def download_invoice(invoice_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    cursor.execute("SELECT * FROM invoice WHERE invoice_id = %s", (invoice_id,))
    invoice = cursor.fetchone()

    if not invoice:
        flash("Invoice not found.", "danger")
        return redirect(url_for('retailer_dashboard'))

    created_at = invoice['created_at']
    retailer_id = invoice['retailer_id']
    address = invoice['address']

    cursor.execute("""
        SELECT srt.*, p.name AS product_name
        FROM supplier_retailer_transactions srt
        JOIN products p ON srt.product_id = p.product_id
        WHERE srt.retailer_id = %s AND srt.transaction_date = %s
    """, (retailer_id, created_at))
    items = cursor.fetchall()

    if not items:
        cursor.execute("""
            SELECT rct.*, p.name AS product_name
            FROM retailer_customer_transactions rct
            JOIN products p ON rct.product_id = p.product_id
            WHERE rct.retailer_id = %s AND rct.transaction_date = %s
        """, (retailer_id, created_at))
        items = cursor.fetchall()

    cursor.close()
    conn.close()

    if not items:
        flash("No transactions found for invoice.", "danger")
        return redirect(url_for('retailer_dashboard'))

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    pdf.setStrokeColor(colors.black)
    pdf.setLineWidth(1)
    pdf.rect(50, y - 30, width - 100, 40)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(width / 2, y - 10, "SUPPLY WISE")
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(width / 2, y - 25, f"INVOICE — ID: #{invoice_id}")
    y -= 60

    pdf.drawString(60, y, f"Retailer ID: {retailer_id}")
    pdf.drawRightString(width - 60, y, f"Date: {created_at}")
    y -= 20
    pdf.drawString(60, y, f"Ship To: {address}")
    y -= 30

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(60, y, "Product Name")
    pdf.drawString(230, y, "Qty")
    pdf.drawString(280, y, "Unit ₹")
    pdf.drawString(360, y, "Total ₹")
    pdf.line(50, y - 5, width - 50, y - 5)
    y -= 20
    pdf.setFont("Helvetica", 11)

    grand_total = 0
    for item in items:
        pname = item['product_name']
        qty = item['quantity']
        unit = item['total_price'] / qty
        total = item['total_price']
        grand_total += total

        pdf.drawString(60, y, f"{pname}")
        pdf.drawString(230, y, str(qty))
        pdf.drawString(280, y, f"{unit:.2f}")
        pdf.drawString(360, y, f"{total:.2f}")
        y -= 20
        if y < 100:
            pdf.showPage()
            y = height - 50

    pdf.line(50, y, width - 50, y)
    y -= 20
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawRightString(width - 60, y, f"Total Amount: ₹{grand_total:.2f}")
    y -= 40

    pdf.setFont("Helvetica-Oblique", 10)
    pdf.drawString(60, y, "Thank you for doing business with us.")
    pdf.save()

    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'invoice_{invoice_id}.pdf',
        mimetype='application/pdf'
    )

@app.route('/download_sales_report')
def download_sales_report():
    if 'role' not in session:
        return redirect(url_for('login'))

    role = session['role']
    user_id = session['user_id']
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if role == 'retailer':
        # Retailer Sales Report (Customer buys from this retailer)
        sales_query = """
            SELECT 
                p.name AS product_name,
                SUM(rc.quantity) AS total_quantity,
                SUM(rc.total_price) AS total_sales,
                COUNT(DISTINCT rc.rc_transaction_id) AS transaction_count
            FROM retailer_customer_transactions rc
            JOIN products p ON rc.product_id = p.product_id
            WHERE rc.retailer_id = %s
        """
        sales_params = [user_id]

        if start_date:
            sales_query += " AND rc.transaction_date >= %s"
            sales_params.append(start_date)
        if end_date:
            sales_query += " AND rc.transaction_date <= %s"
            sales_params.append(end_date + " 23:59:59")

        sales_query += """
            GROUP BY p.product_id, p.name
            ORDER BY total_sales DESC
        """

    elif role == 'supplier':
        # Supplier Sales Report (Retailers buy from this supplier)
        sales_query = """
            SELECT 
                p.name AS product_name,
                SUM(sr.quantity) AS total_quantity,
                SUM(sr.total_price) AS total_sales,
                COUNT(DISTINCT sr.sr_transaction_id) AS transaction_count
            FROM supplier_retailer_transactions sr
            JOIN products p ON sr.product_id = p.product_id
            WHERE sr.supplier_id = %s
        """
        sales_params = [user_id]

        if start_date:
            sales_query += " AND sr.transaction_date >= %s"
            sales_params.append(start_date)
        if end_date:
            sales_query += " AND sr.transaction_date <= %s"
            sales_params.append(end_date + " 23:59:59")

        sales_query += """
            GROUP BY p.product_id, p.name
            ORDER BY total_sales DESC
        """
    else:
        return "Unauthorized access", 403

    # Execute query
    cursor.execute(sales_query, tuple(sales_params))
    sales_data = cursor.fetchall()
    total_sales = sum(item['total_sales'] for item in sales_data) if sales_data else 0
    total_items_sold = sum(item['total_quantity'] for item in sales_data) if sales_data else 0
    cursor.close()
    conn.close()

    # PDF generation (same as before)
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    # Header
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(width / 2, y - 10, "SALES REPORT")
    pdf.setFont("Helvetica", 12)

    # Date Range
    date_range = ""
    if start_date and end_date:
        date_range = f"From {start_date} to {end_date}"
    elif start_date:
        date_range = f"From {start_date}"
    elif end_date:
        date_range = f"Until {end_date}"
    if date_range:
        pdf.drawCentredString(width / 2, y - 30, date_range)

    y -= 60

    # Summary
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(60, y, "Summary:")
    y -= 20
    pdf.setFont("Helvetica", 12)
    pdf.drawString(60, y, f"Total Sales: ₹{total_sales:.2f}")
    y -= 20
    pdf.drawString(60, y, f"Total Items Sold: {total_items_sold}")
    y -= 30

    # Table headers
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(60, y, "Product")
    pdf.drawString(200, y, "Qty")
    pdf.drawString(250, y, "Revenue")
    pdf.drawString(350, y, "Transactions")
    pdf.line(50, y - 5, width - 50, y - 5)
    y -= 20

    # Table rows
    pdf.setFont("Helvetica", 12)
    for item in sales_data:
        pdf.drawString(60, y, item['product_name'])
        pdf.drawString(200, y, str(item['total_quantity']))
        pdf.drawString(250, y, f"₹{item['total_sales']:.2f}")
        pdf.drawString(350, y, str(item['transaction_count']))
        y -= 20
        if y < 100:
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica", 12)

    pdf.save()
    buffer.seek(0)

    filename = f"sales_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

@app.route('/payment')
def payment():
    amount = session.get("grand_total")  
    upi_id = os.environ.get("UPI_ID", "your_upi_id_here@bank")  
    qr_data = f"upi://pay?pa={upi_id}&am={amount}&cu=INR"
    return render_template("payment.html", amount=amount, qr_data=qr_data)

@app.route('/update_quantity', methods=['POST'])
def update_quantity():
    if 'role' not in session or session['role'] != 'retailer':
        return redirect(url_for('login'))

    inventory_id = request.form.get('inventory_id')
    new_quantity = request.form.get('new_quantity')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE inventory
            SET stock_qty = %s
            WHERE inventory_id = %s AND owner_id = %s AND owner_role = 'retailer'
        """, (new_quantity, inventory_id, session['user_id']))
        conn.commit()
        flash("Quantity updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating quantity: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('retailer_dashboard'))

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'user_id' not in session:
        flash('You must be logged in to submit feedback.', 'danger')
        return redirect(url_for('login'))  # Redirect to login page if not logged in
    
    inventory_id = request.form['inventory_id']
    user_id = session['user_id']  # Assuming the user is logged in and their user_id is stored in the session
    rating = request.form.get(f'rating_{inventory_id}')
    
    # Connect to MySQL
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Insert feedback into the database, ensuring we're using inventory_id
    cursor.execute("""
        INSERT INTO feedback (inventory_id, user_id, rating)
        VALUES (%s, %s, %s)
    """, (inventory_id, user_id, rating))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash('Thank you for your rating!', 'success')
    
    # Redirect back to the page they came from
    return redirect(request.referrer)

def fetch_feedback_from_database():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Change the query if you were previously grouping by product_id
    query = "SELECT * FROM feedback ORDER BY created_at DESC"
    cursor.execute(query)
    
    feedback_data = cursor.fetchall()
    print("Fetched feedback:", feedback_data)  # Debugging line
    
    cursor.close()
    conn.close()
    
    return feedback_data

@app.route('/update_status', methods=['POST'])
def update_status():
    if 'role' in session and session['role'] == 'transporter':
        transaction_id = request.form['transaction_id']
        status = request.form['status']
        table_type = request.form['table_type']

        conn = get_db_connection()
        cur = conn.cursor()

        if table_type == 'sr':
            cur.execute("UPDATE supplier_retailer_transactions SET status = %s WHERE sr_transaction_id = %s",
                        (status, transaction_id))
        elif table_type == 'rc':
            cur.execute("UPDATE retailer_customer_transactions SET status = %s WHERE rc_transaction_id = %s",
                        (status, transaction_id))

        conn.commit()
        cur.close()
        conn.close()
        flash(f"Status updated to {status}!", "success")
        return redirect(url_for('transporter_dashboard'))

    flash("Unauthorized access.", "danger")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)