from flask import Flask, render_template, redirect, url_for, request, session, abort, flash,jsonify,json
import difflib
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import random
from flask_mail import Mail, Message
from functools import wraps
import re # Import re for slugify
import os # Import os for file path manipulation
from werkzeug.utils import secure_filename
# Add this at the top of app3.py
import razorpay
from flask_mail import Message
import string

# Razorpay Client Initialization (replace with your real keys)
razorpay_client = razorpay.Client(auth=("rzp_test_yourkey", "your_secret"))

app = Flask(__name__)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = '20h41f0013@gmail.com'
app.config['MAIL_PASSWORD'] = 'fizh wvzd ezuo gaky'
app.config['MAIL_DEFAULT_SENDER'] = '20h41f0013@gmail.com'
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
mail = Mail(app)

app.secret_key = 'your_secret_key_here'


UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Database Connection ---
def get_db_connection():
    """Establishes a connection to the MySQL database."""
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="naveen99",
            database="spy-d" # !!! IMPORTANT: Changed to 'spy-d' for consistency with your app3.py
        )
        print("✅ Connecting to database: spy-d")
        return conn
    except mysql.connector.Error as err:
        print(f"❌ Database connection error: {err}")
        # You might want to render an error page or flash a message here in a real app
        abort(500, "Database connection failed.")


# --- Database Initialization ---
def init_db():
    """Initializes the database by creating necessary tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- users ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) NOT NULL UNIQUE,
        mobile VARCHAR(15),
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(50) DEFAULT 'customer',
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)

    # --- products ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id VARCHAR(255) PRIMARY KEY,
            seller_id INT NULL,
            title VARCHAR(255) NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            discount DECIMAL(5, 2) NOT NULL DEFAULT 0,
            discounted_price DECIMAL(10, 2) GENERATED ALWAYS AS (price * (1 - discount/100)) STORED,
            compare_price DECIMAL(10, 2),
            image VARCHAR(255),
            tags TEXT,
            description TEXT,
            benefits TEXT,
            category VARCHAR(255),
            sub_category VARCHAR(255),
            status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (seller_id) REFERENCES users(id)
        )
    """)

    # --- cart_items ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cart_items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            product_id VARCHAR(255) NOT NULL,
            title VARCHAR(255) NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            image VARCHAR(255),
            quantity INT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        )
    """)

    # --- orders ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            total_amount DECIMAL(10, 2) NOT NULL,
            status VARCHAR(50) DEFAULT 'pending',
            payment_method VARCHAR(50),
            shipping_address TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # --- order_items ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            product_id VARCHAR(255) NOT NULL,
            seller_id INT NOT NULL,
            quantity INT NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (seller_id) REFERENCES users(id)
        )
    """)

    # --- inventory ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            product_id VARCHAR(255) PRIMARY KEY,
            stock_quantity INT NOT NULL DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        )
    """)

    # --- seller_profiles ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS seller_profiles (
            user_id INT PRIMARY KEY,
            company_name VARCHAR(255) NOT NULL,
            mobile VARCHAR(15),  # Optional secondary mobile for sellers
            pan_number VARCHAR(20) NOT NULL,
            gst_number VARCHAR(20),
            address TEXT NOT NULL,
            bank_account VARCHAR(30) NOT NULL,
            ifsc_code VARCHAR(20) NOT NULL,
            is_approved BOOLEAN DEFAULT FALSE,
            approval_status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
            rejection_reason TEXT,
            approved_by INT,
            approved_at DATETIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (approved_by) REFERENCES users(id)
        )
    """)

    # --- product_approvals ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_approvals (
            product_id VARCHAR(255) PRIMARY KEY,
            status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
            rejection_reason TEXT,
            reviewed_by INT,
            reviewed_at DATETIME,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (reviewed_by) REFERENCES users(id)
        )
    """)

    # --- product_categories ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_categories (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            parent_id INT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES product_categories(id)
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()

    
def update_db_schema():
    """Updates the database schema with new tables and columns"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # --- 1. Modify seller_id in products table to be nullable ---
        cursor.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'products' 
            AND COLUMN_NAME = 'seller_id'
        """)
        if cursor.fetchone()[0] > 0:
            cursor.execute("ALTER TABLE products MODIFY seller_id INT NULL")

        # --- 2. Add columns to seller_profiles if not exist ---
        for column_def in [
            ("is_active", "BOOLEAN DEFAULT TRUE"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            ("approval_notes", "TEXT")
        ]:
            col_name, col_type = column_def
            cursor.execute(f"""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'seller_profiles' 
                AND COLUMN_NAME = '{col_name}'
            """)
            if cursor.fetchone()[0] == 0:
                cursor.execute(f"""
                    ALTER TABLE seller_profiles 
                    ADD COLUMN {col_name} {col_type}
                """)

        # --- 3. Create seller_activity table if not exists ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seller_activity (
                id INT AUTO_INCREMENT PRIMARY KEY,
                seller_id INT NOT NULL,
                action VARCHAR(50) NOT NULL,
                product_id VARCHAR(255),
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (seller_id) REFERENCES users(id)
            )
        """)

        # --- 4. Add discounted_price column if missing ---
        cursor.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'products' 
            AND COLUMN_NAME = 'discounted_price'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE products
                ADD COLUMN discounted_price DECIMAL(10, 2) GENERATED ALWAYS AS (price * (1 - discount/100)) STORED
            """)
            
        cursor.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'users' 
            AND COLUMN_NAME = 'created_at'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE users
                ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            """)
          
        

        # --- 5. Add foreign key for product_approvals if not exists ---
        cursor.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
            WHERE CONSTRAINT_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'products' 
            AND CONSTRAINT_NAME = 'fk_product_approval'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO product_approvals (product_id, status)
                SELECT p.id, 'pending'
                FROM products p
                LEFT JOIN product_approvals pa ON p.id = pa.product_id
                WHERE pa.product_id IS NULL
            """)
            cursor.execute("""ALTER TABLE products ADD CONSTRAINT fk_product_approval 
                    FOREIGN KEY (id) REFERENCES product_approvals(product_id) ON DELETE CASCADE
                """)

        # --- 6. Add foreign key fk_seller if not exists ---
        cursor.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
            WHERE CONSTRAINT_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'products' 
            AND CONSTRAINT_NAME = 'fk_seller'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE products ADD CONSTRAINT fk_seller 
                FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE SET NULL
            """)
        cursor.execute("ALTER TABLE orders AUTO_INCREMENT = 1001")


        conn.commit()
        print("✅ Database schema updated successfully")
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"❌ Error updating database schema: {err}")
    finally:
        cursor.close()
        conn.close()


def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower().strip()).strip('-')

# --- Product Data Migration (Run once to populate DB from old ALL_PRODUCTS) ---
# IMPORTANT: This function is for initial migration.
# After the first successful run, comment out the call to this function in if __name__ == '__main__':
# to prevent re-running and potential issues.
def migrate_products_to_db():
    # Only import ALL_PRODUCTS if this function is called, to avoid dependency if not needed
    try:
        from all_products import ALL_PRODUCTS
    except ImportError:
        print("❌ all_products.py not found. Skipping product migration.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if products table is empty
    cursor.execute("SELECT COUNT(*) FROM products")
    count = cursor.fetchone()[0]

    if count == 0:
        print("Migrating products from all_products.py to database...")

        # Ensure admin user with ID 1 exists for product assignment
        admin_user_id = 1
        cursor.execute("SELECT id FROM users WHERE id = %s", (admin_user_id,))
        if not cursor.fetchone():
            from werkzeug.security import generate_password_hash
            # Create a default admin user if ID 1 doesn't exist
            hashed_password = generate_password_hash("admin123") # Default password for admin
            cursor.execute("""
                INSERT INTO users (id, name, email, password_hash, role)
                VALUES (%s, %s, %s, %s, %s)
            """, (admin_user_id, 'Admin', 'admin@example.com', hashed_password, 'admin'))
            conn.commit() # Commit the new admin user
            print("✅ Created default admin user with ID 1 (admin@example.com / admin123)")
        else:
            print("Admin user with ID 1 already exists.")

        # Now migrate products
        for product in ALL_PRODUCTS:
            try:
                # Insert product
                cursor.execute(
                    """INSERT INTO products (id, seller_id, title, price, compare_price, image, tags, description, benefits, category, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved')""",
                    (product['id'],
                     admin_user_id, # Assign to default admin
                     product['title'],
                     product['price'],
                     product.get('compare_price'),
                     product.get('image'),
                     ','.join(product.get('tags', [])),
                     product.get('description'),
                     ','.join(product.get('benefits', [])),
                     product.get('category'))
                )
                
                # Create inventory record with 0 stock - sellers will add stock themselves
                cursor.execute("""
                    INSERT INTO inventory (product_id, stock_quantity)
                    VALUES (%s, %s)
                """, (product['id'], 0))  # Start with 0 stock
                
                # Insert product approval record
                cursor.execute("""
                    INSERT INTO product_approvals (product_id, status, reviewed_by, reviewed_at)
                    VALUES (%s, 'approved', %s, NOW())
                """, (product['id'], admin_user_id))
                
            except mysql.connector.Error as err:
                if err.errno == 1062: # Duplicate entry for primary key 'id'
                    print(f"Product '{product['id']}' already exists. Skipping.")
                else:
                    print(f"Error migrating product {product['id']}: {err}")
        
        conn.commit()
        print(f"✅ Migrated {len(ALL_PRODUCTS)} products to the database. Stock quantities set to 0 - sellers can update them.")
    else:
        print("Products table is not empty. Skipping migration.")

    cursor.close()
    conn.close()
    

    
def add_missing_inventory_records():
    """Adds inventory records for products that don't have them"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Find products without inventory records
        cursor.execute("""
            SELECT p.id 
            FROM products p 
            LEFT JOIN inventory i ON p.id = i.product_id 
            WHERE i.product_id IS NULL
        """)
        products_without_inventory = cursor.fetchall()
        
        if products_without_inventory:
            print(f"Found {len(products_without_inventory)} products without inventory records.")
            
            # Add inventory records with default stock of 100
            default_stock = 100
            for (product_id,) in products_without_inventory:
                cursor.execute("""
                    INSERT INTO inventory (product_id, stock_quantity)
                    VALUES (%s, %s)
                """, (product_id, default_stock))
                print(f"Added inventory for product: {product_id}")
            
            conn.commit()
            print(f"✅ Added inventory records for {len(products_without_inventory)} products.")
        else:
            print("All products already have inventory records.")
            
    except Exception as e:
        print(f"Error adding inventory records: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


# --- Helper Functions for Database Operations (Products) ---
def get_all_products_from_db():
    """Fetches all products from the database, including stock quantity."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.*, COALESCE(i.stock_quantity, 0) AS stock_quantity 
        FROM products p
        LEFT JOIN inventory i ON p.id = i.product_id
    """)
    products = cursor.fetchall()
    conn.close()

    for product in products:
        if product.get('tags'):
            product['tags'] = [tag.strip() for tag in product['tags'].split(',')]
        else:
            product['tags'] = []
        
        if product.get('benefits'):
            product['benefits'] = [benefit.strip() for benefit in product['benefits'].split(',')]
        else:
            product['benefits'] = []
        
        if 'price' in product and product['price'] is not None:
            product['price'] = float(product['price'])
        if 'compare_price' in product and product['compare_price'] is not None:
            product['compare_price'] = float(product['compare_price'])
    
    return products

def get_product_by_id_from_db(product_id):
    """Fetches a single product by its ID from the database, including stock quantity."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.*, COALESCE(i.stock_quantity, 0) AS stock_quantity 
        FROM products p
        LEFT JOIN inventory i ON p.id = i.product_id
        WHERE p.id = %s
    """, (product_id,))
    product = cursor.fetchone()
    conn.close()

    if product:
        # Convert comma-separated strings to lists
        if product.get('tags'):
            product['tags'] = [tag.strip() for tag in product['tags'].split(',')]
        else:
            product['tags'] = []
        
        if product.get('benefits'):
            product['benefits'] = [benefit.strip() for benefit in product['benefits'].split(',')]
        else:
            product['benefits'] = []

        # Ensure numeric fields are floats
        if 'price' in product and product['price'] is not None:
            product['price'] = float(product['price'])
        if 'compare_price' in product and product['compare_price'] is not None:
            product['compare_price'] = float(product['compare_price'])
    
    return product

def add_product_to_db(product_data):
    """Adds a new product to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        price = float(product_data['price'])
        compare_price = float(product_data['compare_price']) if product_data.get('compare_price') is not None else None

        cursor.execute(
            """INSERT INTO products (id, seller_id, title, price, compare_price, image, tags, description, benefits, category,sub_category)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s)""",
            (product_data['id'],
             product_data['seller_id'],
             product_data['title'],
             price,
             compare_price,
             product_data.get('image'),
             ','.join(product_data.get('tags', [])),
             product_data.get('description'),
             ','.join(product_data.get('benefits', [])),
             product_data.get('category'),
             product_data.get('sub_category'))
        )
        cursor.execute("""
            INSERT INTO inventory (product_id, stock_quantity)
            VALUES (%s, %s)
        """, (product_data['id'], product_data['stock_quantity']))
        conn.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Error adding product: {err}")
        return False
    finally:
        cursor.close()
        conn.close()

def update_product_in_db(product_id, product_data):
    """Updates an existing product in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        price = float(product_data['price'])
        compare_price = float(product_data['compare_price']) if product_data.get('compare_price') is not None else None

        cursor.execute(
            """UPDATE products SET title = %s, price = %s, compare_price = %s, image = %s,
               tags = %s, description = %s, benefits = %s, category = %s
               WHERE id = %s AND seller_id = %s""",
            (product_data['title'],
             price,
             compare_price,
             product_data.get('image'),
             ','.join(product_data.get('tags', [])),
             product_data.get('description'),
             ','.join(product_data.get('benefits', [])),
             product_data.get('category'),
             product_id,
             product_data['seller_id'])
        )
        cursor.execute("""
            UPDATE inventory SET stock_quantity = %s
            WHERE product_id = %s
        """, (product_data['stock_quantity'], product_id))
        conn.commit()
        return cursor.rowcount > 0
    except mysql.connector.Error as err:
        print(f"Error updating product: {err}")
        return False
    finally:
        cursor.close()
        conn.close()

def delete_product_from_db(product_id, seller_id):
    """Deletes a product from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM products WHERE id = %s AND seller_id = %s", (product_id, seller_id))
        conn.commit()
        return cursor.rowcount > 0
    except mysql.connector.Error as err:
        print(f"Error deleting product: {err}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_products_by_seller_id(seller_id):
    """Fetches all products for a specific seller, including stock quantity."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Modified SQL query to include stock_quantity from the inventory table
    cursor.execute("""
        SELECT p.*, COALESCE(i.stock_quantity, 0) AS stock_quantity
        FROM products p
        LEFT JOIN inventory i ON p.id = i.product_id
        WHERE p.seller_id = %s
    """, (seller_id,))
    products = cursor.fetchall()
    conn.close()

    for product in products:
        if product.get('tags'):
            product['tags'] = [tag.strip() for tag in product['tags'].split(',')]
        else:
            product['tags'] = []
        if product.get('benefits'):
            product['benefits'] = [benefit.strip() for benefit in product['benefits'].split(',')]
        else:
            product['benefits'] = []
        if 'price' in product and product['price'] is not None:
            product['price'] = float(product['price'])
        if 'compare_price' in product and product['compare_price'] is not None:
            product['compare_price'] = float(product['compare_price'])
    return products

def get_products_by_category_from_db(category_name):
    """Fetches products for a given category from the database, including stock quantity."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.*, COALESCE(i.stock_quantity, 0) AS stock_quantity 
        FROM products p
        LEFT JOIN inventory i ON p.id = i.product_id
        WHERE p.category = %s OR p.sub_category = %s
    """, (category_name,category_name))
    products = cursor.fetchall()
    conn.close()
    
    for product in products:
        if product.get('tags'):
            product['tags'] = [tag.strip() for tag in product['tags'].split(',')]
        else:
            product['tags'] = []
        if product.get('benefits'):
            product['benefits'] = [benefit.strip() for benefit in product['benefits'].split(',')]
        else:
            product['benefits'] = []
        if 'price' in product and product['price'] is not None:
            product['price'] = float(product['price'])
        if 'compare_price' in product and product['compare_price'] is not None:
            product['compare_price'] = float(product['compare_price'])
    
    return products


# --- Helper Functions for Database Operations (Users) ---
def get_user_by_id(user_id):
    """Fetches a user by ID."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_user_by_email(email):
    """Fetches a user by email."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_all_users_from_db():
    """Fetches all users from the database."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, email, role FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

def update_user_role_in_db(user_id, new_role):
    """Updates the role of a user in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
        conn.commit()
        return cursor.rowcount > 0
    except mysql.connector.Error as err:
        print(f"Error updating user role: {err}")
        return False
    finally:
        cursor.close()
        conn.close()

# --- Authorization Decorators ---
def role_required(role):
    """
    Decorator to restrict access to routes based on user role.
    Usage: @role_required('admin') or @role_required('seller')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in to access this page.", "warning")
                return redirect(url_for('login'))
            
            user = get_user_by_id(session['user_id'])
            if not user or user['role'] != role:
                flash(f"You do not have the required '{role}' role to access this page.", "danger")
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Flask Routes ---

@app.route('/')
def home():
    cart_length = get_cart_length()
    all_products_data = get_all_products_from_db()

    unique_products = []
    seen_titles = set()
    for product_item in all_products_data:
        if product_item['title'] not in seen_titles:
            unique_products.append(product_item)
            seen_titles.add(product_item['title'])

    return render_template("base.html", 
                           collection={'products': unique_products},
                           current_collection='all-products',
                           cart_length=cart_length)


@app.route('/collections/<collection_id>')
def collection(collection_id):
    products_in_category = get_products_by_category_from_db(collection_id)

    collection_data = {
        'title': collection_id.replace('-', ' ').title(),
        'description': f'Products in the {collection_id.replace("-", " ")} category',
        'products': products_in_category
    }

    if not products_in_category:
        abort(404)

    return render_template('collection.html',
                           collection=collection_data,
                           current_collection=collection_id)


@app.route('/all-products')
def all_products_page():
    all_products_data = get_all_products_from_db()
    unique_products = []
    seen_titles = set()
    for product_item in all_products_data:
        if product_item['title'] not in seen_titles:
            unique_products.append(product_item)
            seen_titles.add(product_item['title'])

    return render_template('collection.html',
                           collection={'title': 'All Products', 'products': unique_products},
                           current_collection='all-products')

# --- Explicit Routes for Each Category ---
@app.route('/milk-malts')
def milk_malts_collection():
    products = get_products_by_category_from_db('milk-malts')
    return render_template('collection.html',
                           collection={'title': 'Milk Malts', 'products': products},
                           current_collection='milk-malts')

@app.route('/healthy-snacks')
def healthy_snacks_collection():
    products = get_products_by_category_from_db('healthy-snacks')
    return render_template('collection.html',
                           collection={'title': 'Healthy Snacks', 'products': products},
                           current_collection='healthy-snacks')

@app.route('/amla-human-sanjeevani')
def amla_human_sanjeevani_collection():
    products = get_products_by_category_from_db('amla-human-sanjeevani')
    return render_template('collection.html',
                           collection={'title': 'Amla-Human Sanjeevani', 'products': products},
                           current_collection='amla-human-sanjeevani')

@app.route('/sprouted-flours')
def sprouted_flours_collection():
    products = get_products_by_category_from_db('sprouted-flours')
    return render_template('collection.html',
                           collection={'title': 'Sprouted Flours', 'products': products},
                           current_collection='sprouted-flours')

@app.route('/cooking-essentials')
def cooking_essentials_collection():
    products = get_products_by_category_from_db('cooking-essentials')
    return render_template('collection.html',
                           collection={'title': 'Cooking Essentials', 'products': products},
                           current_collection='cooking-essentials')

@app.route('/kaaram-podis')
def kaaram_podis_collection():
    products = get_products_by_category_from_db('kaaram-podis')
    return render_template('collection.html',
                           collection={'title': 'Kaaram Podi\'s', 'products': products},
                           current_collection='kaaram-podis')

@app.route('/basic-health')
def basic_health_collection():
    products = get_products_by_category_from_db('basic-health')
    return render_template('collection.html',
                           collection={'title': 'Basic Health', 'products': products},
                           current_collection='basic-health')

@app.route('/kids-special')
def kids_special_collection():
    products = get_products_by_category_from_db('kids-special')
    return render_template('collection.html',
                           collection={'title': 'Kids Special', 'products': products},
                           current_collection='kids-special')

@app.route('/skin-care')
def skin_care_collection():
    products = get_products_by_category_from_db('skin-care')
    return render_template('collection.html',
                           collection={'title': 'Skin Care', 'products': products},
                           current_collection='skin-care')

@app.route('/hair-care')
def hair_care_collection():
    products = get_products_by_category_from_db('hair-care')
    return render_template('collection.html',
                           collection={'title': 'Hair Care', 'products': products},
                           current_collection='hair-care')

@app.route('/tea-blends')
def tea_blends_collection():
    products = get_products_by_category_from_db('tea-blends')
    return render_template('collection.html',
                           collection={'title': 'Tea Blends', 'products': products},
                           current_collection='tea-blends')

@app.route('/weight-management')
def weight_management_collection():
    products = get_products_by_category_from_db('weight-management')
    return render_template('collection.html',
                           collection={'title': 'Weight Management', 'products': products},
                           current_collection='weight-management')

@app.route('/iron-deficiency')
def iron_deficiency_collection():
    products = get_products_by_category_from_db('iron-deficiency')
    return render_template('collection.html',
                           collection={'title': 'Iron Deficiency', 'products': products},
                           current_collection='iron-deficiency')

@app.route('/b-complex-deficiency')
def b_complex_deficiency_collection():
    products = get_products_by_category_from_db('b-complex-deficiency')
    return render_template('collection.html',
                           collection={'title': 'B-Complex Deficiency', 'products': products},
                           current_collection='b-complex-deficiency')

@app.route('/irregular-periods')
def irregular_periods_collection():
    products = get_products_by_category_from_db('irregular-periods')
    return render_template('collection.html',
                           collection={'title': 'Irregular Periods', 'products': products},
                           current_collection='irregular-periods')

@app.route('/constipation')
def constipation_collection():
    products = get_products_by_category_from_db('constipation')
    return render_template('collection.html',
                           collection={'title': 'Constipation', 'products': products},
                           current_collection='constipation')

@app.route('/bones-strength')
def bones_strength_collection():
    products = get_products_by_category_from_db('bones-strength')
    return render_template('collection.html',
                           collection={'title': 'Bones Strength', 'products': products},
                           current_collection='bones-strength')

@app.route('/immunity-booster')
def immunity_booster_collection():
    products = get_products_by_category_from_db('immunity-booster')
    return render_template('collection.html',
                           collection={'title': 'Immunity Booster', 'products': products},
                           current_collection='immunity-booster')

@app.route('/cold-and-cough')
def cold_and_cough_collection():
    products = get_products_by_category_from_db('cold-and-cough')
    return render_template('collection.html',
                           collection={'title': 'Cold and Cough', 'products': products},
                           current_collection='cold-and-cough')

@app.route('/pregnancy-care')
def pregnancy_care_collection():
    products = get_products_by_category_from_db('pregnancy-care')
    return render_template('collection.html',
                           collection={'title': 'Pregnancy Care', 'products': products},
                           current_collection='pregnancy-care')

@app.route('/diabetic-care')
def diabetic_care_collection():
    products = get_products_by_category_from_db('diabetic-care')
    return render_template('collection.html',
                           collection={'title': 'Diabetic Care', 'products': products},
                           current_collection='diabetic-care')

@app.route('/baby-care')
def baby_care_collection():
    products = get_products_by_category_from_db('baby-care')
    return render_template('collection.html',
                           collection={'title': 'Baby Care', 'products': products},
                           current_collection='baby-care')


@app.route('/products/<product_id>')
def product(product_id):
    product_item = get_product_by_id_from_db(product_id)
    
    if not product_item:
        abort(404)
    
    collection_title = product_item.get('category', 'Products').replace('-', ' ').title()
    
    return render_template('product.html',
                           product=product_item,
                           collection_title=collection_title)

@app.route('/cart')
def cart():
    user_id = session.get('user_id')
    cart_items = []

    if user_id:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                ci.product_id as id, 
                ci.title, 
                ci.price, 
                ci.image, 
                ci.quantity,
                COALESCE(i.stock_quantity, 0) > 0 AS in_stock
            FROM cart_items ci
            LEFT JOIN inventory i ON ci.product_id = i.product_id
            WHERE ci.user_id = %s
        """, (user_id,))
        cart_items = cursor.fetchall()
        conn.close()
    else:
        cart_items = session.get('cart', [])
        for item in cart_items:
            product = get_product_by_id_from_db(item['id'])
            item['in_stock'] = product['stock_quantity'] > 0 if product else False

    total_price = sum(item['price'] * item['quantity'] for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total_price=total_price)


@app.route('/terms')
def terms():
    return render_template("terms.html")

@app.route('/shipping')
def shipping():
    return render_template("shipping_policy.html")

@app.route('/refund')
def refund():
    return render_template("refund_policy.html")

@app.route('/privacy')
def privacy():
    return render_template("privacy_policy.html")

@app.route('/contact')
def contact():
    return render_template("contact.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        login_type = request.form.get('login_type', 'customer')  # Default to customer if not specified

        print(f"Attempting login for email: {email}")  # Debug print
        user = get_user_by_email(email)

        if user:
            print(f"User found: {user['email']}, Role: {user['role']}")  # Debug print
            print(f"Stored hash: {user['password_hash']}")  # Debug print
            password_matches = check_password_hash(user['password_hash'], password)
            print(f"Password check result: {password_matches}")  # Debug print

            if password_matches:
                # Check if user is trying to access the correct login type
                if (login_type == 'admin' and user['role'] != 'admin') or \
                   (login_type == 'seller' and user['role'] != 'seller'):
                    flash(f"This account is not registered as a {login_type}", "danger")
                    return redirect(url_for('login' if login_type == 'customer' else f'{login_type}_login'))
                
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['user_role'] = user['role']

                temp_cart = session.pop('cart', [])
                if temp_cart:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    for item in temp_cart:
                        item_price = float(item['price'])
                        cursor.execute("SELECT quantity FROM cart_items WHERE user_id = %s AND product_id = %s", (user['id'], item['id']))
                        existing_db_item = cursor.fetchone()
                        if existing_db_item:
                            new_quantity = existing_db_item[0] + item['quantity']
                            cursor.execute("UPDATE cart_items SET quantity = %s WHERE user_id = %s AND product_id = %s", (new_quantity, user['id'], item['id']))
                        else:
                            cursor.execute(
                                "INSERT INTO cart_items (user_id, product_id, title, price, image, quantity) VALUES (%s, %s, %s, %s, %s, %s)",
                                (user['id'], item['id'], item['title'], item_price, item['image'], item['quantity'])
                            )
                    conn.commit()
                    conn.close()

                flash("Login successful", "success")
                if user['role'] == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif user['role'] == 'seller':
                    return redirect(url_for('seller_dashboard'))
                else:
                    return redirect(url_for('home'))
            else:
                flash("Invalid email or password", "danger")
        else:
            print(f"User with email {email} not found.")  # Debug print
            flash("Invalid email or password", "danger")

    return render_template('login.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        print(f"Attempting admin login for email: {email}")  # Debug print
        user = get_user_by_email(email)

        if user:
            print(f"User found: {user['email']}, Role: {user['role']}")  # Debug print
            password_matches = check_password_hash(user['password_hash'], password)
            print(f"Password check result: {password_matches}")  # Debug print

            if password_matches:
                if user['role'] != 'admin':
                    flash("This account is not registered as an admin", "danger")
                    return redirect(url_for('admin_login'))
                
                # Clear any existing session cart for admin users
                if 'cart' in session:
                    session.pop('cart')

                # Set admin session variables
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['user_role'] = 'admin'  # Explicitly set to admin

                flash("Admin login successful", "success")
                return redirect(url_for('admin_dashboard'))
            else:
                flash("Invalid email or password", "danger")
        else:
            print(f"User with email {email} not found.")  # Debug print
            flash("Invalid email or password", "danger")

    return render_template('admin_login.html')

def get_all_customers_from_db():
    """Fetches all users with role 'customer'."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id , name, email, mobile, created_at FROM users WHERE role = 'customer'")
    customers = cursor.fetchall()
    conn.close()
    return customers

def get_customer_orders(customer_id):
    """Fetches all orders for a specific customer, including order items."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch orders for the customer
    cursor.execute("""
        SELECT id, order_date, total_amount, status, payment_method, shipping_address
        FROM orders
        WHERE user_id = %s
        ORDER BY order_date DESC
    """, (customer_id,))
    orders = cursor.fetchall()

    # For each order, fetch its items
    for order in orders:
        cursor.execute("""
            SELECT oi.product_id, oi.quantity, oi.price, p.title AS product_title, p.image AS product_image
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = %s
        """, (order['id'],))
        order['items'] = cursor.fetchall()
    
    conn.close()
    return orders

def get_all_sellers_from_db():
    """Fetches all users with role 'seller' and their basic profile info."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT u.id as user_id, u.name, u.email, u.mobile, sp.company_name, sp.approval_status
        FROM users u
        LEFT JOIN seller_profiles sp ON u.id = sp.user_id
        WHERE u.role = 'seller'
    """)
    sellers = cursor.fetchall()
    conn.close()
    return sellers

def get_seller_profile_by_user_id(user_id):
    """Fetches a seller's user details and their seller profile."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            u.id, 
            u.name, 
            u.email, 
            u.mobile, 
            u.is_active,
            u.created_at AS user_created_at,
            sp.company_name, 
            sp.pan_number, 
            sp.gst_number, 
            sp.address,
            sp.bank_account, 
            sp.ifsc_code, 
            sp.approval_status,
            sp.rejection_reason, 
            sp.approved_by, 
            sp.approved_at,
            sp.created_at AS profile_created_at, 
            sp.updated_at AS profile_updated_at,
            ua.name as approved_by_name
        FROM users u
        LEFT JOIN seller_profiles sp ON u.id = sp.user_id
        LEFT JOIN users ua ON sp.approved_by = ua.id
        WHERE u.id = %s AND u.role = 'seller'
    """, (user_id,))
    seller_data = cursor.fetchone()
    conn.close()
    return seller_data


@app.route('/admin/customers')
@role_required('admin')
def admin_view_customers():
    """Admin view to list all customers."""
    customers = get_all_customers_from_db()
    return render_template('admin_customers.html', customers=customers)

@app.route('/admin/customer/<int:customer_id>')
@role_required('admin')
def admin_view_customer(customer_id):
    customer = get_user_by_id(customer_id)

    if not customer or customer['role'] != 'customer':
        flash("Customer not found or invalid user role.", "danger")
        return redirect(url_for('admin_customers'))

    orders = get_customer_orders(customer_id)

    # Calculate order stats
    order_count = len(orders)
    total_spent = sum(order['total_amount'] for order in orders)
    last_order_date = max((order['order_date'] for order in orders), default=None)

    order_stats = {
        'order_count': order_count,
        'total_spent': total_spent,
        'last_order_date': last_order_date
    }

    return render_template(
        'admin_customer_profile.html',
        customer=customer,
        orders=orders,
        order_stats=order_stats
    )
    



@app.route('/admin/customer/<int:customer_id>/deactivate', methods=['POST'])
@role_required('admin')
def admin_deactivate_customer(customer_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Set is_active = 0 (False)
        cursor.execute("UPDATE users SET is_active = 0 WHERE id = %s AND role = 'customer'", (customer_id,))
        conn.commit()
        flash("Customer account deactivated successfully.", "warning")
    except Exception as e:
        conn.rollback()
        flash("Error deactivating customer: " + str(e), "danger")
    finally:
        conn.close()
    return redirect(url_for('admin_view_customer', customer_id=customer_id))
@app.route('/admin/customer/<int:customer_id>/activate', methods=['POST'])
@role_required('admin')
def admin_activate_customer(customer_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Set is_active = 1 (True)
        cursor.execute("UPDATE users SET is_active = 1 WHERE id = %s AND role = 'customer'", (customer_id,))
        conn.commit()
        flash("Customer account activated successfully.", "success")
    except Exception as e:
        conn.rollback()
        flash("Error activating customer: " + str(e), "danger")
    finally:
        conn.close()
    return redirect(url_for('admin_view_customer', customer_id=customer_id))


@app.route('/admin/seller/<int:seller_id>/deactivate', methods=['POST'])
@role_required('admin')
def admin_deactivate_seller(seller_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Set is_active = 0 (False)
        cursor.execute("UPDATE users SET is_active = 0 WHERE id = %s AND role = 'seller'", (seller_id,))
        conn.commit()
        flash("Seller account deactivated successfully.", "warning")
    except Exception as e:
        conn.rollback()
        flash("Error deactivating seller: " + str(e), "danger")
    finally:
        conn.close()
    return redirect(url_for('admin_view_seller', seller_id=seller_id))

@app.route('/admin/seller/<int:seller_id>/activate', methods=['POST'])
@role_required('admin')
def admin_activate_seller(seller_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Set is_active = 1 (True)
        cursor.execute("UPDATE users SET is_active = 1 WHERE id = %s AND role = 'seller'", (seller_id,))
        conn.commit()
        flash("Seller account activated successfully.", "success")
    except Exception as e:
        conn.rollback()
        flash("Error activating seller: " + str(e), "danger")
    finally:
        conn.close()
    return redirect(url_for('admin_view_seller', seller_id=seller_id))




@app.route('/admin/customer/<int:customer_id>/orders')
@role_required('admin')
def admin_view_customer_orders(customer_id):
    """Admin view to see a specific customer's orders."""
    customer = get_user_by_id(customer_id)
    if not customer or customer['role'] != 'customer':
        flash("Customer not found or invalid user role.", "danger")
        abort(404)

    orders = get_customer_orders(customer_id)
    
    return render_template('admin_customer_orders.html', customer=customer, orders=orders)

# --- Admin Seller Management ---

@app.route('/admin/sellers')
@role_required('admin')
def admin_view_sellers():
    """Admin view to list all sellers."""
    sellers = get_all_sellers_from_db()
    return render_template('admin_sellers.html', sellers=sellers)

@app.route('/admin/seller/<int:seller_id>')
@role_required('admin')
def admin_view_seller(seller_id):
    """Admin view to see a specific seller's profile."""
    seller = get_seller_profile_by_user_id(seller_id)
    if not seller:
        flash("Seller not found.", "danger")
        abort(404)

    # You might want to fetch their products, approval history, etc. here
    seller_products = get_products_by_seller_id(seller_id)

    return render_template('admin_seller_profile.html', seller=seller, products=seller_products)


@app.route('/admin/seller/<int:seller_id>/products')
@role_required('admin')
def admin_view_seller_products(seller_id):
    """Admin view to see products uploaded by a specific seller."""
    seller = get_user_by_id(seller_id) # Get basic seller user info
    if not seller or seller['role'] != 'seller':
        flash("Seller not found or invalid user role.", "danger")
        abort(404)

    products = get_products_by_seller_id(seller_id)
    
    return render_template('admin_seller_products.html', seller=seller, products=products)




@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('user_role', None)
    return redirect(url_for('home'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        session['name'] = request.form['name']
        session['email'] = request.form['email']
        session['password'] = request.form['password']

        if get_user_by_email(session['email']):
            flash("Email already registered. Please login or use a different email.", "danger")
            return redirect(url_for('register'))

        otp = str(random.randint(100000, 999999))
        session['otp'] = otp

        msg = Message('Registration OTP', recipients=[session['email']])
        msg.body = f"Your registration OTP is {otp}"
        mail.send(msg)

        return redirect(url_for('verify_otp'))

    return render_template('register.html')


@app.route('/seller/register', methods=['GET', 'POST'])
def seller_register():
    if request.method == 'POST':
        # Basic user registration
        name = request.form['name']
        email = request.form['email']
        mobile = request.form['mobile']
        password = request.form['password']
        
        # Check if email exists
        if get_user_by_email(email):
            flash("Email already registered", "danger")
            return redirect(url_for('seller_register'))
        
        # Create user with seller role
        hashed_password = generate_password_hash(password)
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            conn.start_transaction()
            cursor.execute("""
                INSERT INTO users (name, email, mobile, password_hash, role)
                VALUES (%s, %s, %s, %s, 'seller')
            """, (name, email, mobile, hashed_password))
            user_id = cursor.lastrowid
            
            # Create seller profile
            cursor.execute("""
                INSERT INTO seller_profiles (
                    user_id, company_name, mobile, pan_number, 
                    gst_number, address, bank_account, ifsc_code
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                request.form['company_name'],
                request.form['mobile'],
                request.form['pan_number'],
                request.form['gst_number'],
                request.form['address'],
                request.form['bank_account'],
                request.form['ifsc_code']
            ))
            
            conn.commit()
            flash("Seller registration successful! Please login.", "success")
            
        except Exception as e:
            conn.rollback()
            print(e)
            flash(f"Registration failed: {str(e)}", "danger")
        finally:
            conn.close()
        return redirect(url_for('seller_login'))
    
    return render_template('seller_register.html')

@app.route('/seller/login', methods=['GET', 'POST'])
def seller_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = get_user_by_email(email)
        if user and check_password_hash(user['password_hash'], password):
            if user['role'] != 'seller':
                
                flash("This account is not registered as a seller", "danger")
                return redirect(url_for('seller_login'))
                
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            flash("Login successful", "success")
            return redirect(url_for('seller_dashboard'))
        
        flash("Invalid email or password", "danger")
    
    return render_template('seller_login.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        user_otp = request.form['otp']
        if user_otp == session.get('otp'):
            hashed_password = generate_password_hash(session['password'])

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
                (session['name'], session['email'], hashed_password, 'customer')
            )
            conn.commit()
            conn.close()

            session.pop('name', None)
            session.pop('email', None)
            session.pop('password', None)
            session.pop('otp', None)

            flash("Registration successful. You can now log in.", "success")
            return redirect(url_for('login'))
        else:
            flash("Invalid OTP. Please try again.", "danger")

    return render_template('verify_otp.html')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']

        user = get_user_by_email(email)

        if user:
            otp = str(random.randint(100000, 999999))
            session['reset_email'] = email
            session['reset_otp'] = otp

            msg = Message("Password Reset OTP", recipients=[email])
            msg.body = f"Your OTP is {otp}"
            mail.send(msg)

            return redirect(url_for('verify_reset_otp_password'))

        flash("Email not found", "danger")

    return render_template('forgot_password.html')

@app.route('/verify-reset-otp-password', methods=['GET', 'POST'])
def verify_reset_otp_password():
    if request.method == 'POST':
        entered_otp = request.form['otp']
        new_password = request.form['new_password']
        email = session.get('reset_email')

        if entered_otp == session.get('reset_otp') and email:
            hashed_password = generate_password_hash(new_password)

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password_hash = %s WHERE email = %s", (hashed_password, email))
            conn.commit()
            conn.close()

            session.pop('reset_email', None)
            session.pop('reset_otp', None)

            flash("Password reset successfully.", "success")
            return redirect(url_for('login'))
        else:
            flash("Invalid OTP or session expired.", "danger")

    return render_template('verify_reset_otp_password.html')


@app.route('/search', methods=['GET', 'POST'])
def search():
    query = request.args.get('query', '').lower()
    search_results = []
    found_product_ids = set()

    if query:
        all_products_data = get_all_products_from_db()
        for product_item in all_products_data:
            product_title = product_item.get('title')

            if product_item['id'] in found_product_ids:
                continue

            search_strings = [
                product_title.lower(),
                product_item['description'].lower() if product_item['description'] else ''
            ]
            if product_item['tags'] and isinstance(product_item['tags'], list):
                search_strings.extend([tag.lower() for tag in product_item['tags']])
            
            is_match = False
            for s_str in search_strings:
                if query in s_str:
                    is_match = True
                    break
                if difflib.get_close_matches(query, [s_str], n=1, cutoff=0.6):
                    is_match = True
                    break
            
            if is_match:
                search_results.append(product_item)
                found_product_ids.add(product_item['id'])
    
    return render_template('search_results.html', query=query, search_results=search_results)


@app.route('/add-to-cart', methods=['POST'])
def add_to_cart():
    product_id = request.form.get('product_id')
    product = get_product_by_id_from_db(product_id)  # Now includes stock_quantity

    if not product or product.get('stock_quantity', 0) < 1:
        flash("This product is currently out of stock", "danger")
        return redirect(url_for('product', product_id=product_id))

    title = product['title']
    price = float(product['price'])
    image = product['image']
    user_id = session.get('user_id')

    if user_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT quantity FROM cart_items WHERE user_id = %s AND product_id = %s", (user_id, product_id))
        existing_item = cursor.fetchone()

        if existing_item:
            new_quantity = existing_item[0] + 1
            cursor.execute("UPDATE cart_items SET quantity = %s WHERE user_id = %s AND product_id = %s", (new_quantity, user_id, product_id))
        else:
            cursor.execute(
                "INSERT INTO cart_items (user_id, product_id, title, price, image, quantity) VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, product_id, title, price, image, 1)
            )
        conn.commit()
        conn.close()
    else:
        cart = session.get('cart', [])
        for item in cart:
            if item['id'] == product_id:
                item['quantity'] += 1
                break
        else:
            cart.append({'id': product_id, 'title': title, 'price': price, 'image': image, 'quantity': 1})
        session['cart'] = cart
    
    flash(f"{title} added to cart!", "success")
    return redirect(url_for('cart'))


def check_stock_availability(product_id, quantity=1):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT stock_quantity FROM inventory WHERE product_id = %s", (product_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] >= quantity

def update_stock(product_id, quantity_change):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE inventory 
            SET stock_quantity = GREATEST(0, stock_quantity + %s)
            WHERE product_id = %s
        """, (quantity_change, product_id))
        conn.commit()
    finally:
        conn.close()


@app.route('/update-cart', methods=['POST'])
def update_cart():
    data = request.get_json()
    product_id = data.get('id')
    new_quantity = int(data.get('quantity', 1))
    user_id = session.get('user_id')

    if user_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE cart_items SET quantity = %s WHERE user_id = %s AND product_id = %s", (max(1, new_quantity), user_id, product_id))
        conn.commit()
        conn.close()
    else:
        cart = session.get('cart', [])
        for item in cart:
            if item['id'] == product_id:
                item['quantity'] = max(1, new_quantity)
                break
        session['cart'] = cart
    return {'status': 'success'}

@app.route('/clear-cart', methods=['POST'])
def clear_cart():
    user_id = session.get('user_id')
    if user_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cart_items WHERE user_id = %s", (user_id,))
        conn.commit()
        conn.close()
    else:
        session['cart'] = []
    flash("Cart cleared successfully!", "info")
    return redirect(url_for('cart'))


def get_cart_length():
    user_id = session.get('user_id')
    cart_length = 0
    if user_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(quantity) FROM cart_items WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        conn.close()
        if result and result[0] is not None:
            cart_length = int(result[0])
    else:
        cart = session.get('cart', [])
        cart_length = sum(item['quantity'] for item in cart)
    return cart_length


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404



@app.route('/admin/users/set_role/<int:user_id>', methods=['POST'])
@role_required('admin')
def admin_set_user_role(user_id):
    new_role = request.form.get('role')
    if new_role not in ['customer', 'seller', 'admin']:
        flash("Invalid role specified.", "danger")
        return redirect(url_for('admin_dashboard'))
    
    if user_id == session['user_id'] and new_role != 'admin':
        flash("You cannot change your own role from admin.", "danger")
        return redirect(url_for('admin_dashboard'))

    if update_user_role_in_db(user_id, new_role):
        flash(f"User role updated to {new_role} successfully.", "success")
        if user_id == session['user_id']:
            session['user_role'] = new_role
    else:
        flash("Failed to update user role.", "danger")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/approve_product', methods=['POST'])
@role_required('admin')
def admin_approve_product():
    conn = None
    cursor = None
    try:
        product_id = request.form.get('product_id')
        if not product_id:
            return jsonify({'success': False, 'message': 'Product ID is required'}), 400
            
        print(f"DEBUG: Approving product {product_id}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Start transaction
        conn.start_transaction()
        
        # Check if product exists first
        cursor.execute("SELECT id FROM products WHERE id = %s", (product_id,))
        if not cursor.fetchone():
            conn.rollback()
            return jsonify({'success': False, 'message': 'Product not found'}), 404
        
        # Update product_approvals table (INSERT or UPDATE)
        cursor.execute("""
            INSERT INTO product_approvals (product_id, status, reviewed_by, reviewed_at)
            VALUES (%s, 'approved', %s, NOW())
            ON DUPLICATE KEY UPDATE 
                status = 'approved',
                reviewed_by = VALUES(reviewed_by),
                reviewed_at = NOW(),
                rejection_reason = NULL
        """, (product_id, session['user_id']))
        
        # Update products table
        cursor.execute("""
            UPDATE products 
            SET status = 'approved' 
            WHERE id = %s
        """, (product_id,))
        
        # Check if update was successful
        if cursor.rowcount == 0:
            conn.rollback()
            return jsonify({'success': False, 'message': 'Failed to update product status'}), 500
        
        conn.commit()
        print(f"DEBUG: Product {product_id} approved successfully")
        return jsonify({'success': True, 'message': 'Product approved successfully'})
        
    except mysql.connector.Error as db_err:
        if conn:
            conn.rollback()
        print(f"DEBUG: Database error approving product: {str(db_err)}")
        return jsonify({'success': False, 'message': f'Database error: {str(db_err)}'}), 500
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"DEBUG: Error approving product: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/admin/reject_product', methods=['POST'])
@role_required('admin')
def admin_reject_product():
    conn = None
    cursor = None
    try:
        product_id = request.form.get('product_id')
        reason = request.form.get('reason', '').strip()
        
        if not product_id:
            return jsonify({'success': False, 'message': 'Product ID is required'}), 400
        if not reason:
            return jsonify({'success': False, 'message': 'Rejection reason is required'}), 400
            
        print(f"DEBUG: Rejecting product {product_id} with reason: {reason}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Start transaction
        conn.start_transaction()
        
        # Check if product exists first
        cursor.execute("SELECT id FROM products WHERE id = %s", (product_id,))
        if not cursor.fetchone():
            conn.rollback()
            return jsonify({'success': False, 'message': 'Product not found'}), 404
        
        # Update products table first
        cursor.execute("""
            UPDATE products 
            SET status = 'rejected' 
            WHERE id = %s
        """, (product_id,))
        
        # Update product_approvals table (INSERT or UPDATE)
        cursor.execute("""
            INSERT INTO product_approvals (product_id, status, rejection_reason, reviewed_by, reviewed_at)
            VALUES (%s, 'rejected', %s, %s, NOW())
            ON DUPLICATE KEY UPDATE 
                status = 'rejected',
                rejection_reason = VALUES(rejection_reason),
                reviewed_by = VALUES(reviewed_by),
                reviewed_at = NOW()
        """, (product_id, reason, session['user_id']))
        
        # Check if update was successful
        if cursor.rowcount == 0:
            conn.rollback()
            return jsonify({'success': False, 'message': 'Failed to update product status'}), 500
        
        conn.commit()
        print(f"DEBUG: Product {product_id} rejected successfully")
        return jsonify({'success': True, 'message': 'Product rejected successfully'})
        
    except mysql.connector.Error as db_err:
        if conn:
            conn.rollback()
        print(f"DEBUG: Database error rejecting product: {str(db_err)}")
        return jsonify({'success': False, 'message': f'Database error: {str(db_err)}'}), 500
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"DEBUG: Error rejecting product: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Replace the current admin_dashboard route with these separate routes:

#  conn = get_db_connection()
#     cursor = conn.cursor(dictionary=True)
    
#     # Get counts for dashboard
#     cursor.execute("SELECT COUNT(*) as count FROM products")
#     products_count = cursor.fetchone()['count']
    
#     cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'seller'")
#     sellers_count = cursor.fetchone()['count']
    
#     cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'customer'")
#     customers_count = cursor.fetchone()['count']
    
#     cursor.execute("SELECT COUNT(*) as count FROM orders")
#     orders_count = cursor.fetchone()['count']
    
#     conn.close()
    
#     return render_template('admin_dashboard.html',
#                          products_count=products_count,
#                          sellers_count=sellers_count,
#                          customers_count=customers_count,
#                          orders_count=orders_count)


@app.route('/admin')
@role_required('admin')
def admin_dashboard():
    # Redirect to products by default
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get counts for dashboard
    cursor.execute("SELECT COUNT(*) as count FROM products")
    products_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'seller'")
    sellers_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'customer'")
    customers_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM orders")
    orders_count = cursor.fetchone()['count']
    
    conn.close()
    
    return render_template('admin_dashboard.html',
                         products_count=products_count,
                         sellers_count=sellers_count,
                         customers_count=customers_count,
                         orders_count=orders_count)
    return render_template('admin_dashboard.html')

@app.route('/admin/products')
@role_required('admin')
def admin_products():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get products for approval
    cursor.execute("""
        SELECT 
            p.*, 
            u.name as seller_name, 
            u.mobile as seller_mobile,
            pa.status,
            pa.rejection_reason,
            COALESCE(inv.stock_quantity, 0) as stock_quantity
        FROM products p
        LEFT JOIN users u ON p.seller_id = u.id
        LEFT JOIN product_approvals pa ON p.id = pa.product_id
        LEFT JOIN inventory inv ON p.id = inv.product_id
        WHERE pa.status = 'pending' OR p.status = 'pending'
        ORDER BY p.created_at DESC
    """)
    products = cursor.fetchall()
    
    conn.close()
    
    return render_template('products_section.html',
                         products=products
                        )
    
    



@app.route('/admin/sellers')
@role_required('admin')
def admin_sellers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get seller profiles (now with both user and profile mobile)
    cursor.execute("""
        SELECT 
            u.id as user_id, 
            u.name, 
            u.email, 
            u.mobile as primary_mobile,
            sp.mobile as business_mobile,
            sp.pan_number, 
            sp.address,
            sp.approval_status,
            u.is_active,
            sp.created_at as profile_created_at,
            COUNT(p.id) as product_count
        FROM users u
        LEFT JOIN seller_profiles sp ON u.id = sp.user_id
        LEFT JOIN products p ON u.id = p.seller_id
        WHERE u.role = 'seller'
        GROUP BY u.id
        ORDER BY sp.approval_status = 'pending' DESC, sp.created_at DESC
    """)
    sellers = cursor.fetchall()
    
    conn.close()
    
    return render_template('sellers_section.html',
                         sellers=sellers
                         )

@app.route('/admin/customers')
@role_required('admin')
def admin_customers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get customer profiles
    cursor.execute("""
        SELECT 
            u.id, 
            u.name, 
            u.email, 
            u.mobile,
            u.is_active,
            COUNT(o.id) as order_count,
            SUM(o.total_amount) as total_spent
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        WHERE u.role = 'customer'
        GROUP BY u.id
    """)
    customers = cursor.fetchall()
    
    conn.close()
    
    return render_template('customers_section.html',
                         customers=customers
                         )

@app.route('/admin/orders')
@role_required('admin')
def admin_orders():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get all orders with customer and item information
    cursor.execute("""
        SELECT 
            o.id, 
            o.order_date, 
            o.total_amount, 
            o.status,
            o.payment_method,
            o.tracking_number,

            o.shipping_address,
            u.name as customer_name,
            u.email as customer_email,
            COUNT(oi.id) as item_count
        FROM orders o
        JOIN users u ON o.user_id = u.id
        JOIN order_items oi ON o.id = oi.order_id
        GROUP BY o.id
        ORDER BY o.order_date DESC
    """)
    orders = cursor.fetchall()
    
    conn.close()
    
    return render_template('orders_section.html',
                         orders=orders
                         )


def get_user_by_email(email):
    """Fetches a user by email including mobile."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, name, email, mobile, password_hash, role, is_active 
        FROM users 
        WHERE email = %s
    """, (email,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    """Fetches a user by ID including mobile."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, name, email, mobile, role, is_active 
        FROM users 
        WHERE id = %s
    """, (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

# --- Seller Routes ---
@app.route('/seller')
@role_required('seller')
def seller_dashboard():
    seller_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Check seller approval status
    cursor.execute("""
        SELECT is_active, approval_status FROM seller_profiles 
        WHERE user_id = %s
    """, (seller_id,))
    seller_status = cursor.fetchone()
    
    if not seller_status or not seller_status['is_active']:
        flash("Your seller account is pending approval", "warning")
        return render_template('seller_pending.html')
    
    # Get seller's products with stock quantity - FIXED QUERY
    cursor.execute("""
        SELECT 
            p.*,
            COALESCE(i.stock_quantity, 0) as stock_quantity,
            (p.price * (1 - p.discount/100)) AS calculated_discounted_price
        FROM products p
        LEFT JOIN inventory i ON p.id = i.product_id
        WHERE p.seller_id = %s
        ORDER BY p.created_at DESC
    """, (seller_id,))
    products = cursor.fetchall()
    
    # Get customers who bought seller's products
    cursor.execute("""
        SELECT DISTINCT 
            u.id as user_id, 
            u.name, 
            u.email, 
            u.mobile,
            p.title as product_title, 
            oi.quantity, 
            o.order_date,
            oi.price as sold_price
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN users u ON o.user_id = u.id
        JOIN products p ON oi.product_id = p.id
        WHERE oi.seller_id = %s
        ORDER BY o.order_date DESC
    """, (seller_id,))
    customers = cursor.fetchall()
    
    # Get seller profile
    cursor.execute("""
        SELECT * FROM seller_profiles 
        WHERE user_id = %s
    """, (seller_id,))
    seller_profile = cursor.fetchone()
    
    
    cursor.execute("""
        SELECT 
        o.id AS order_id,
        o.order_date,
        o.shipping_address,
        o.payment_method,
        o.tracking_number,

        u.name AS customer_name,
        u.email AS customer_email,
        GROUP_CONCAT(CONCAT(p.title, ' (x', oi.quantity, ')') SEPARATOR ', ') AS items,
        SUM(oi.price * oi.quantity) AS total_amount,
        o.status
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.id
    JOIN users u ON o.user_id = u.id
    JOIN products p ON oi.product_id = p.id
    WHERE oi.seller_id = %s
    GROUP BY o.id, o.order_date, o.shipping_address, u.name, u.email, o.status
    HAVING o.status = 'paid'
    ORDER BY o.order_date DESC
    """, (seller_id,))
    orders = cursor.fetchall()
    
    conn.close()
    
    return render_template('seller_dashboard.html',
                         products=products,
                         customers=customers,
                         seller_orders=orders,
                         seller_profile=seller_profile)
    
    

def send_seller_approval_email(seller_email, approved=True, reason=None):
    msg = Message(
        "Your Seller Account Status",
        recipients=[seller_email]
    )
    
    if approved:
        msg.body = "Your seller account has been approved! You can now add products."
    else:
        msg.body = f"Your seller account was rejected. Reason: {reason or 'Not specified'}"
    
    mail.send(msg)

# Call this in approve_seller() and reject_seller() routes

@app.route('/seller/add_product', methods=['POST'])
@role_required('seller')
def add_product():
    seller_id = session['user_id']
    conn = None
    cursor = None
    
    try:
        # Validate form data
        price = float(request.form['price'])
        discount = float(request.form.get('discount', 0))
        compare_price = float(request.form['compare_price']) if request.form.get('compare_price') else None
        stock_quantity = int(request.form['stock_quantity'])  # Get stock quantity
        
        # Handle file upload
        file = request.files['image']
        if not (file and allowed_file(file.filename)):
            flash('Invalid image file', 'danger')
            return redirect(url_for('seller_dashboard'))
        
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        # Generate product ID - prioritize sub-category if available
        category = request.form['category']
        sub_category = request.form.get('sub_category', '')
        
        # Use sub-category if available, otherwise use category
        base_name = sub_category if sub_category else category
        base_id = slugify(f"{base_name}-{request.form['title']}")
        
        product_id = base_id
        suffix = 1
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check for existing ID
        while True:
            cursor.execute("SELECT id FROM products WHERE id = %s", (product_id,))
            if not cursor.fetchone():
                break
            product_id = f"{base_id}-{suffix}"
            suffix += 1
            
        # Disable foreign key checks temporarily
        cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        
        try:
            # Insert into product_approvals
            cursor.execute("""
                INSERT INTO product_approvals (product_id, status)
                VALUES (%s, 'pending')
            """, (product_id,))
            
            # Insert into products
            cursor.execute("""
                INSERT INTO products (
                    id, seller_id, title, price, discount, compare_price,
                    image, description, tags, benefits, 
                    category, sub_category, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
            """, (
                product_id,
                seller_id,
                request.form['title'],
                price,
                discount,
                compare_price,
                filename,
                request.form['description'],
                request.form.get('tags', ''),
                request.form.get('benefits', ''),
                category,
                sub_category
            ))
            
            # Insert into inventory
            cursor.execute("""
                INSERT INTO inventory (product_id, stock_quantity)
                VALUES (%s, %s)
            """, (product_id, stock_quantity))
            
            # Re-enable foreign key checks
            cursor.execute("SET FOREIGN_KEY_CHECKS=1")
            conn.commit()
            
            log_seller_activity(
                seller_id=seller_id,
                action="product_added",
                product_id=product_id,
                details={
                    "title": request.form['title'],
                    "stock": stock_quantity,
                    "status": "pending"
                }
            )
            
            flash('Product submitted for approval with stock quantity', 'success')
            
        except Exception as e:
            cursor.execute("SET FOREIGN_KEY_CHECKS=1")
            raise e
            
    except ValueError:
        if conn:
            conn.rollback()
        flash('Invalid price/discount/stock format', 'danger')
    except Exception as e:
        if conn:
            conn.rollback()
        flash(f'Error adding product: {str(e)}', 'danger')
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
    return redirect(url_for('seller_dashboard'))

@app.route('/seller/edit_profile', methods=['GET', 'POST'])
@role_required('seller')
def edit_seller_profile():
    seller_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        try:
            cursor.execute("""
                UPDATE seller_profiles SET
                    company_name = %s,
                    mobile = %s,
                    pan_number = %s,
                    gst_number = %s,
                    address = %s,
                    bank_account = %s,
                    ifsc_code = %s
                WHERE user_id = %s
            """, (
                request.form['company_name'],
                request.form['mobile'],
                request.form['pan_number'],
                request.form['gst_number'],
                request.form['address'],
                request.form['bank_account'],
                request.form['ifsc_code'],
                seller_id
            ))
            conn.commit()
            flash('Profile updated successfully', 'success')
            log_seller_activity(
                seller_id=session['user_id'],
                action="profile_updated",
                details={
                    "fields_updated": list(request.form.keys())
                }
            )
            
            
        except Exception as e:
            conn.rollback()
            flash(f'Error updating profile: {str(e)}', 'danger')
        finally:
            conn.close()
        return redirect(url_for('seller_dashboard'))
    
    # GET request - show edit form
    cursor.execute("SELECT * FROM seller_profiles WHERE user_id = %s", (seller_id,))
    profile = cursor.fetchone()
    conn.close()
    
    return render_template('edit_seller_profile.html', profile=profile)


@app.route('/admin/reject_seller/<int:seller_id>', methods=['POST'])
@role_required('admin')
def reject_seller(seller_id):
    conn = None
    cursor = None
    try:
        reason = request.form.get('reason', '').strip()
        if not reason:
            return jsonify({'success': False, 'message': 'Rejection reason is required'}), 400
            
        print(f"DEBUG: Rejecting seller {seller_id} with reason: {reason}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Start transaction
        conn.start_transaction()
        
        # Check if seller exists first
        cursor.execute("SELECT id FROM users WHERE id = %s AND role = 'seller'", (seller_id,))
        if not cursor.fetchone():
            conn.rollback()
            return jsonify({'success': False, 'message': 'Seller not found'}), 404
        
        # Update seller profile
        cursor.execute("""
            UPDATE seller_profiles 
            SET is_approved = FALSE, 
                approval_status = 'rejected',
                rejection_reason = %s,
                approved_by = %s,
                approved_at = NOW()
            WHERE user_id = %s
        """, (reason, session['user_id'], seller_id))
        
        # Deactivate the user account
        cursor.execute("""
            UPDATE users 
            SET is_active = FALSE 
            WHERE id = %s
        """, (seller_id,))
        
        conn.commit()
        print(f"DEBUG: Seller {seller_id} rejected successfully")
        return jsonify({'success': True, 'message': 'Seller rejected successfully'})
        
    except mysql.connector.Error as db_err:
        if conn:
            conn.rollback()
        print(f"DEBUG: Database error rejecting seller: {str(db_err)}")
        return jsonify({'success': False, 'message': f'Database error: {str(db_err)}'}), 500
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"DEBUG: Error rejecting seller: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def log_seller_activity(seller_id, action, product_id=None, details=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO seller_activity 
            (seller_id, action, product_id, details)
            VALUES (%s, %s, %s, %s)
        """, (seller_id, action, product_id, str(details)))
        conn.commit()
    except Exception as e:
        print(f"Error logging activity: {e}")
    finally:
        conn.close()






@app.route('/admin/approve_seller/<int:seller_id>', methods=['POST'])
@role_required('admin')
def approve_seller(seller_id):
    conn = None
    cursor = None
    try:
        print(f"DEBUG: Approving seller {seller_id}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Start transaction
        conn.start_transaction()
        
        # Check if seller exists first
        cursor.execute("SELECT id FROM users WHERE id = %s AND role = 'seller'", (seller_id,))
        if not cursor.fetchone():
            conn.rollback()
            return jsonify({'success': False, 'message': 'Seller not found'}), 404
        
        # Update seller profile
        cursor.execute("""
            UPDATE seller_profiles 
            SET is_approved = TRUE, 
                approval_status = 'approved',
                approved_by = %s,
                approved_at = NOW(),
                rejection_reason = NULL
            WHERE user_id = %s
        """, (session['user_id'], seller_id))
        
        # Activate the user account
        cursor.execute("""
            UPDATE users 
            SET is_active = TRUE 
            WHERE id = %s
        """, (seller_id,))
        
        conn.commit()
        print(f"DEBUG: Seller {seller_id} approved successfully")
        return jsonify({'success': True, 'message': 'Seller approved successfully'})
        
    except mysql.connector.Error as db_err:
        if conn:
            conn.rollback()
        print(f"DEBUG: Database error approving seller: {str(db_err)}")
        return jsonify({'success': False, 'message': f'Database error: {str(db_err)}'}), 500
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"DEBUG: Error approving seller: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            




@app.route('/seller/edit_product/<string:product_id>', methods=['GET', 'POST'])
@role_required('seller')
def edit_product(product_id):
    seller_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch current product
    cursor.execute("""
        SELECT p.*, i.stock_quantity, pa.status AS approval_status
        FROM products p
        LEFT JOIN inventory i ON p.id = i.product_id
        LEFT JOIN product_approvals pa ON p.id = pa.product_id
        WHERE p.id = %s AND p.seller_id = %s
    """, (product_id, seller_id))
    product = cursor.fetchone()

    if not product:
        flash("Product not found or you don't have permission to edit it.", "danger")
        return redirect(url_for('seller_dashboard'))

    if request.method == 'POST':
        try:
            # Gather data
            title = request.form['title']
            price = float(request.form['price'])
            compare_price = float(request.form.get('compare_price', price))
            discount = float(request.form.get('discount', 0))
            stock_quantity = int(request.form['stock_quantity'])
            category = request.form['category']
            sub_category = request.form.get('sub_category', '')
            description = request.form['description']
            tags = request.form.get('tags', '').strip()
            benefits = request.form.get('benefits', '').strip()
            product['tags'] = product['tags'].split(',') if product.get('tags') else []
            product['benefits'] = product['benefits'].split(',') if product.get('benefits') else []



            # Validate
            if price <= 0:
                raise ValueError("Price must be positive.")
            if discount < 0 or discount > 100:
                raise ValueError("Discount must be between 0 and 100.")
            if stock_quantity < 0:
                raise ValueError("Stock quantity cannot be negative")
            if stock_quantity > 10000:  # Reasonable upper limit
                raise ValueError("Stock quantity too high")
            
           

            # Handle image
            image_filename = product['image']
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename:
                    if allowed_file(file.filename):
                        if image_filename:
                            try:
                                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
                            except OSError:
                                pass
                        image_filename = secure_filename(file.filename)
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
                    else:
                        raise ValueError("Invalid image format.")

            # Regenerate product_id if title/category changed
            base_name = sub_category if sub_category else category
            base_id = slugify(f"{base_name}-{title}")
            new_product_id = base_id
            suffix = 1

            while True:
                cursor.execute("SELECT id FROM products WHERE id = %s AND id != %s", (new_product_id, product_id))
                if cursor.fetchone():
                    new_product_id = f"{base_id}-{suffix}"
                    suffix += 1
                else:
                    break

            # Update product
            cursor.execute("""
                UPDATE products SET
                    id = %s,
                    title = %s,
                    price = %s,
                    compare_price = %s,
                    discount = %s,
                    image = %s,
                    description = %s,
                    tags = %s,
                    benefits = %s,
                    category = %s,
                    sub_category = %s,
                    updated_at = NOW()
                WHERE id = %s AND seller_id = %s
            """, (
                new_product_id, title, price, compare_price, discount,
                image_filename, description, tags, benefits,
                category, sub_category,
                product_id, seller_id
            ))

            # Update inventory and approvals if product_id changed
            if new_product_id != product_id:
                cursor.execute("UPDATE inventory SET product_id = %s WHERE product_id = %s", (new_product_id, product_id))
                cursor.execute("UPDATE product_approvals SET product_id = %s WHERE product_id = %s", (new_product_id, product_id))

            # Update stock
            cursor.execute("UPDATE inventory SET stock_quantity = %s WHERE product_id = %s", (stock_quantity, new_product_id))

            # Reset approval if stock changed
            if stock_quantity != product['stock_quantity']:
                cursor.execute("""
                    UPDATE product_approvals SET status = 'pending', rejection_reason = NULL
                    WHERE product_id = %s
                """, (new_product_id,))

            conn.commit()

            # Log
            log_seller_activity(
                seller_id=seller_id,
                action="product_updated",
                product_id=new_product_id,
                details={
                    "title": title,
                    "price": price,
                    "old_stock": product['stock_quantity'],
                    "new_stock": stock_quantity,
                    "status": "pending" if stock_quantity != product['stock_quantity'] else product['approval_status']
                }
            )

            flash("Product updated successfully!" + (" Changes require admin re-approval." if stock_quantity != product['stock_quantity'] else ""), "success")
            return redirect(url_for('seller_dashboard'))

        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error updating product {product_id}: {e}", exc_info=True)
            flash("Error updating product. Please try again.", "danger")
        finally:
            cursor.close()
            conn.close()

    # GET request: load form
    try:
        product['tags'] = product['tags'].split(',') if product.get('tags') else []
        product['benefits'] = product['benefits'].split(',') if product.get('benefits') else []

        cursor.execute("SELECT name FROM product_categories WHERE is_active = TRUE")
        categories = [row['name'] for row in cursor.fetchall()]

        return render_template('edit_product.html',
                               product=product,
                               categories=categories)
    except Exception as e:
        app.logger.error(f"Error loading product for editing: {e}", exc_info=True)
        flash("Failed to load product for editing.", "danger")
        return redirect(url_for('seller_dashboard'))
    finally:
        cursor.close()
        conn.close()





@app.route('/seller/delete_product/<string:product_id>', methods=['POST'])
@role_required('seller')
def delete_product(product_id):
    seller_id = session['user_id']
    product = get_product_by_id_from_db(product_id)
    if product:
        log_seller_activity(
            seller_id=seller_id,
            action="product_deleted",
            product_id=product_id,
            details={
                "title": product['title'],
                "reason": "seller_initiated"
            }
        )
    
    
    if delete_product_from_db(product_id, seller_id):
        flash("Product deleted successfully!", "success")
    else:
        flash("Failed to delete product or product not found.", "danger")
    return redirect(url_for('seller_dashboard'))



# Route to render checkout page and create Razorpay order
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        flash("Please log in to checkout", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get cart items with stock check - FIXED QUERY
    cursor.execute("""
        SELECT 
            ci.*,
            COALESCE(i.stock_quantity, 0) as stock_quantity
        FROM cart_items ci
        LEFT JOIN inventory i ON ci.product_id = i.product_id
        WHERE ci.user_id = %s
    """, (user_id,))
    cart_items = cursor.fetchall()
    
    # Check stock availability
    out_of_stock = [item for item in cart_items if item['quantity'] > item['stock_quantity']]
    if out_of_stock:
        flash(f"Some items in your cart are out of stock", "danger")
        return redirect(url_for('cart'))
    
    total_price = sum(item['price'] * item['quantity'] for item in cart_items)

    if request.method == 'POST':
        # Create Razorpay order
        order_data = {
            "amount": int(total_price * 100),
            "currency": "INR",
            "payment_capture": 1,
            "notes": {
                "user_id": user_id,
                "items": json.dumps([{"id": item['product_id'], "quantity": item['quantity']} for item in cart_items])
            }
        }
        
        try:
            razorpay_order = razorpay_client.order.create(data=order_data)
            
            # Store checkout info in session
            session['checkout_info'] = {
                'shipping_info': {
                    'full_name': request.form['full_name'],
                    'address': request.form['shipping_address'],
                    'city': request.form['city'],
                    'state': request.form['state'],
                    'pincode': request.form['pincode'],
                    'phone': request.form['phone']
                },
                'razorpay_order_id': razorpay_order['id'],
                'total_amount': total_price,
                'cart_items': [{'id': item['product_id'], 'quantity': item['quantity']} for item in cart_items]
            }
            
            return render_template("checkout.html", 
                                 razorpay_order_id=razorpay_order['id'],
                                 total_amount=total_price,
                                 razorpay_key="your_razorpay_key_here",  # Replace with actual key
                                 cart_items=cart_items)
            
        except Exception as e:
            flash(f"Error creating payment order: {str(e)}", "danger")
            return redirect(url_for('cart'))

    conn.close()
    return render_template("checkout.html", 
                         cart_items=cart_items,
                         total_price=total_price)
    
    
    
def update_orders_schema():
    """Updates the orders table with additional columns if needed"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Add columns to orders table if they don't exist
        additional_columns = [
            ("shipping_city", "VARCHAR(100)"),
            ("shipping_state", "VARCHAR(100)"),
            ("shipping_pincode", "VARCHAR(10)"),
            ("shipping_phone", "VARCHAR(15)"),
            ("customer_name", "VARCHAR(255)"),
            ("razorpay_order_id", "VARCHAR(100)"),
            ("razorpay_payment_id", "VARCHAR(100)"),
            ("tracking_number", "VARCHAR(100)"),
            ("shipped_at", "DATETIME"),
        ]
        
        for column_name, column_type in additional_columns:
            cursor.execute(f"""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'orders' 
                AND COLUMN_NAME = '{column_name}'
            """)
            if cursor.fetchone()[0] == 0:
                cursor.execute(f"""
                    ALTER TABLE orders 
                    ADD COLUMN {column_name} {column_type}
                """)
                print(f"Added column {column_name} to orders table")

        conn.commit()
        print("✅ Orders table schema updated successfully")
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"❌ Error updating orders schema: {err}")
    finally:
        cursor.close()
        conn.close()

# Handle successful payment webhook (mocked via client-side fetch)
@app.route('/payment-success', methods=['POST'])
def payment_success():
    if 'user_id' not in session or 'checkout_info' not in session:
        return jsonify({'status': 'error', 'message': 'Invalid session'}), 400
        
    data = request.get_json()
    user_id = session['user_id']
    checkout_info = session['checkout_info']
    
    # Verify payment signature
    params_dict = {
        'razorpay_order_id': data['razorpay_order_id'],
        'razorpay_payment_id': data['razorpay_payment_id'],
        'razorpay_signature': data['razorpay_signature']
    }
    
    try:
        razorpay_client.utility.verify_payment_signature(params_dict)
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Invalid payment signature'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create order record
        cursor.execute("""
            INSERT INTO orders (user_id, total_amount, payment_method, status, 
                              shipping_address, shipping_city, shipping_state, 
                              shipping_pincode, shipping_phone, customer_name,
                              razorpay_order_id, razorpay_payment_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            checkout_info['total_amount'],
            'razorpay',
            'paid',
            checkout_info['shipping_info']['address'],
            checkout_info['shipping_info']['city'],
            checkout_info['shipping_info']['state'],
            checkout_info['shipping_info']['pincode'],
            checkout_info['shipping_info']['phone'],
            checkout_info['shipping_info']['full_name'],
            data['razorpay_order_id'],
            data['razorpay_payment_id']
        ))
        order_id = cursor.lastrowid
        
        # Create order items
        for item in checkout_info['cart_items']:
            # Get product details including seller_id
            cursor.execute("""
                SELECT seller_id, price FROM products WHERE id = %s
            """, (item['id'],))
            product = cursor.fetchone()
            
            cursor.execute("""
                INSERT INTO order_items (order_id, product_id, seller_id, quantity, price)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                order_id,
                item['id'],
                product['seller_id'],
                item['quantity'],
                product['price']
            ))
            
            # Update inventory
            cursor.execute("""
                UPDATE inventory 
                SET stock_quantity = stock_quantity - %s
                WHERE product_id = %s
            """, (item['quantity'], item['id']))
        
        # Clear cart
        cursor.execute("DELETE FROM cart_items WHERE user_id = %s", (user_id,))
        
        conn.commit()
        
        # Send confirmation email
        send_order_confirmation_email(user_id, order_id)
        send_payment_received_notification(order_id)
        
        # Clear checkout session
        session.pop('checkout_info', None)
        
        return jsonify({
            'status': 'success',
            'order_id': order_id
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()
        
        
@app.route('/order-confirmation/<int:order_id>')
def order_confirmation(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT o.*, oi.product_id, oi.quantity, oi.price, p.title, p.image
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        WHERE o.id = %s AND o.user_id = %s
    """, (order_id, session['user_id']))
    
    order_items = cursor.fetchall()
    conn.close()
    
    if not order_items:
        abort(404)
    
    order = order_items[0]
    order['items'] = order_items
    
    return render_template('order_confirmation.html', order=order)

# Seller approves and confirms shipment
@app.route('/confirm-shipment/<int:order_id>', methods=['POST'])
@role_required('seller')
def confirm_shipment(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    seller_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    # ✅ Check if the seller is involved in this order
    cursor.execute("""
        SELECT o.id, u.email
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        JOIN users u ON o.user_id = u.id
        WHERE o.id = %s AND p.seller_id = %s
        LIMIT 1
    """, (order_id, seller_id))
    result = cursor.fetchone()

    if not result:
        flash("You don't have permission to confirm this order.", "danger")
        return redirect(url_for('seller_dashboard'))

    customer_email = result[1]

    # ✅ Only update if still in 'paid' state
    cursor.execute("""
        UPDATE orders 
        SET status = 'confirmed' 
        WHERE id = %s AND status = 'paid'
    """, (order_id,))
    conn.commit()

    # ✅ Send confirmation email
    try:
        msg = Message("Order Confirmed!", recipients=[customer_email])
        msg.body = f"Hi! Your order #{order_id} has been confirmed and is being prepared for shipment."
        mail.send(msg)
    except Exception as e:
        flash(f"Confirmation sent, but failed to email customer: {str(e)}", "warning")

    cursor.close()
    conn.close()

    flash("Order confirmed and customer notified.", "success")
    return redirect(url_for('seller_dashboard'))


@app.route('/seller/orders')
@role_required('seller')
def seller_orders():
    seller_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT o.id, o.order_date, o.status, o.tracking_number,
               u.name as customer_name, u.email as customer_email,
               GROUP_CONCAT(p.title SEPARATOR ', ') as products,
               SUM(oi.quantity * oi.price) as order_total
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        JOIN users u ON o.user_id = u.id
        WHERE oi.seller_id = %s
        GROUP BY o.id
        ORDER BY o.order_date DESC
    """, (seller_id,))
    
    orders = cursor.fetchall()
    conn.close()
    
    return render_template('seller_orders.html', orders=orders)

def generate_unique_tracking_number(cursor):
    while True:
        tracking_number = "ORD-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        
        cursor.execute("SELECT 1 FROM orders WHERE tracking_number = %s LIMIT 1", (tracking_number,))
        if not cursor.fetchone():
            return tracking_number



@app.route('/seller/orders/<int:order_id>/ship', methods=['POST'])
@role_required('seller')
def ship_order(order_id):
    seller_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # ✅ Check seller is associated with this order
        cursor.execute("""
            SELECT o.user_id, u.email 
            FROM orders o
            JOIN users u ON o.user_id = u.id
            JOIN order_items oi ON o.id = oi.order_id
            JOIN products p ON oi.product_id = p.id
            WHERE o.id = %s AND p.seller_id = %s
            LIMIT 1
        """, (order_id, seller_id))
        result = cursor.fetchone()

        if not result:
            flash("You are not authorized to ship this order.", "danger")
            return redirect(url_for('seller_dashboard'))

        customer_email = result[1]

        # ✅ Generate random tracking number (10 characters)
        tracking_number = generate_unique_tracking_number(cursor)



        # ✅ Update order status and tracking info
        cursor.execute("""
            UPDATE orders 
            SET status = 'shipped',
                tracking_number = %s,
                shipped_at = NOW()
            WHERE id = %s
        """, (tracking_number, order_id))
        conn.commit()

        # ✅ Notify customer via email
        try:
            send_shipping_notification(order_id, tracking_number)
        except Exception as e:
            flash(f"Order shipped, but email failed: {str(e)}", "warning")

        flash(f"Order shipped with tracking number {tracking_number}.", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Error processing shipment: {str(e)}", "danger")

    finally:
        conn.close()

    return redirect(url_for('seller_dashboard'))



# Customer view their orders and tracking
@app.route('/my-orders')
def my_orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT o.id, o.status, o.total_amount, o.order_date, o.shipping_address, o.tracking_id,
               GROUP_CONCAT(p.title SEPARATOR ', ') AS items
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        WHERE o.user_id = %s
        GROUP BY o.id
        ORDER BY o.order_date DESC
    """, (user_id,))
    orders = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("my_orders.html", orders=orders)


def send_order_confirmation_email(user_id, order_id):
    """Send order confirmation email to customer"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get order and user details
    cursor.execute("""
        SELECT o.id, o.total_amount, o.order_date, u.email, u.name
        FROM orders o
        JOIN users u ON o.user_id = u.id
        WHERE o.id = %s AND o.user_id = %s
    """, (order_id, user_id))
    order = cursor.fetchone()
    
    if not order:
        return False
    
    cursor.execute("""
        SELECT p.title, oi.quantity, oi.price
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = %s
    """, (order_id,))
    items = cursor.fetchall()
    conn.close()
    
    # Create email message
    subject = f"Your Order #{order_id} Confirmation"
    html = render_template('emails/order_confirmation.html',
                         order=order,
                         items=items)
    text = render_template('emails/order_confirmation.txt',
                         order=order,
                         items=items)
    
    msg = Message(subject,
                 recipients=[order['email']],
                 html=html,
                 body=text)
    
    try:
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error sending order confirmation email: {str(e)}")
        return False

def send_shipping_notification(order_id, tracking_number):
    """Send shipping notification to customer"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get order and user details
    cursor.execute("""
        SELECT o.id, u.email, u.name, o.tracking_number,
               o.shipping_address, o.shipping_city, o.shipping_state,
               o.shipping_pincode
        FROM orders o
        JOIN users u ON o.user_id = u.id
        WHERE o.id = %s
    """, (order_id,))
    order = cursor.fetchone()
    
    if not order:
        return False
    
    cursor.execute("""
        SELECT p.title, oi.quantity
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = %s
    """, (order_id,))
    items = cursor.fetchall()
    conn.close()
    
    # Create email message
    subject = f"Your Order #{order_id} Has Shipped!"
    html = render_template('emails/shipping_notification.html',
                         order=order,
                         items=items,
                         tracking_number=tracking_number)
    text = render_template('emails/shipping_notification.txt',
                         order=order,
                         items=items,
                         tracking_number=tracking_number)
    
    msg = Message(subject,
                 recipients=[order['email']],
                 html=html,
                 body=text)
    
    try:
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error sending shipping notification: {str(e)}")
        return False

def send_payment_received_notification(order_id):
    """Notify sellers when payment is received for their products"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get all sellers with products in this order
    cursor.execute("""
        SELECT DISTINCT u.id, u.email, u.name as seller_name
        FROM order_items oi
        JOIN users u ON oi.seller_id = u.id
        WHERE oi.order_id = %s
    """, (order_id,))
    sellers = cursor.fetchall()
    
    # Get order details
    cursor.execute("""
        SELECT o.id, o.order_date, o.total_amount
        FROM orders o
        WHERE o.id = %s
    """, (order_id,))
    order = cursor.fetchone()
    
    if not order or not sellers:
        conn.close()
        return False
    
    # Get items for each seller
    for seller in sellers:
        cursor.execute("""
            SELECT p.title, oi.quantity, oi.price
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = %s AND oi.seller_id = %s
        """, (order_id, seller['id']))
        items = cursor.fetchall()
        
        # Create email for each seller - UPDATED TEMPLATE NAMES
        subject = f"Payment Received for Order #{order_id}"
        html = render_template('emails/seller_payment.html',  # Changed from seller_payment_notification.html
                             order=order,
                             items=items,
                             seller=seller)
        text = render_template('emails/seller_payment.txt',   # Changed from seller_payment_notification.txt
                             order=order,
                             items=items,
                             seller=seller)
        
        msg = Message(subject,
                     recipients=[seller['email']],
                     html=html,
                     body=text)
        
        try:
            mail.send(msg)
        except Exception as e:
            print(f"Error sending payment notification to seller {seller['email']}: {str(e)}")
    
    conn.close()
    return True










if __name__ == '__main__':
    init_db()
    # --- IMPORTANT: FOR INITIAL SETUP ONLY ---
    # This function creates a default admin user (admin@example.com / admin123)
    # and migrates products from all_products.py to the database.
    # RUN THIS ONCE, THEN COMMENT IT OUT OR REMOVE IT.
    # If you remove all_products.py, ensure you have already migrated data.
    migrate_products_to_db()
    add_missing_inventory_records()
    update_db_schema() 
    update_orders_schema()
    # ----------------------------------------
    # app.run(host='192.168.1.3',port=3000,debug=True)
    app.run(debug=True)
