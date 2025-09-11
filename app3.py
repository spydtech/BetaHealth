from flask import Flask, render_template, redirect, url_for, request, session, abort, flash,jsonify,json,get_flashed_messages
import difflib
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import random
from flask_wtf import CSRFProtect
from flask_mail import Mail, Message
from functools import wraps
import re # Import re for slugify
import os # Import os for file path manipulation
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import razorpay
from flask_mail import Message
import string
import time
from flask_caching import Cache
from math import ceil

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
csrf = CSRFProtect(app)

UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Permanent upload folder on VPS
# UPLOAD_FOLDER = '/var/www/btahealth-upload-images'
# ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# # Ensure static/images points to permanent upload folder
# STATIC_IMAGE_PATH = os.path.join(app.root_path, 'static/images')

# try:
#     if not os.path.islink(STATIC_IMAGE_PATH):
#         # Backup existing images folder if it exists
#         if os.path.exists(STATIC_IMAGE_PATH):
#             backup_path = STATIC_IMAGE_PATH + "_backup"
#             if not os.path.exists(backup_path):
#                 os.rename(STATIC_IMAGE_PATH, backup_path)
#         # Create symlink
#         os.symlink(UPLOAD_FOLDER, STATIC_IMAGE_PATH)
#         print(f"✅ Symlink created: {STATIC_IMAGE_PATH} -> {UPLOAD_FOLDER}")
#     else:
#         print(f"✅ Symlink already exists: {STATIC_IMAGE_PATH} -> {os.readlink(STATIC_IMAGE_PATH)}")
# except Exception as e:
#     print(f"❌ Error creating symlink for static/images: {e}")



def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Database Connection ---
def get_db_connection():
    """Establishes a connection to the MySQL database."""
    try:
        conn = mysql.connector.connect(
            host="153.92.15.84",
            user="u861150102_spyd",
            password="Spyd@2025",
            database="u861150102_metahealth" # !!! IMPORTANT: Changed to 'spy-d' for consistency with your app3.py
        )
        print("✅ Connecting to database: ")
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
    cursor.execute("""
       CREATE TABLE IF NOT EXISTS user_addresses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,       -- receiver name
    mobile VARCHAR(15) NOT NULL,      -- delivery phone
    address_line1 VARCHAR(255) NOT NULL,
    address_line2 VARCHAR(255),
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL,
    pincode VARCHAR(10) NOT NULL,
    country VARCHAR(100) DEFAULT 'India',
    is_default TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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
    # In the init_db() function, add:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS carousel_slides (
            id INT AUTO_INCREMENT PRIMARY KEY,
            image_path VARCHAR(255) NOT NULL,
            alt_text VARCHAR(255),
            title VARCHAR(100),
            description TEXT,
            link_url VARCHAR(255),
            is_active BOOLEAN DEFAULT TRUE,
            sort_order INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_reviews (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            product_id VARCHAR(255) NOT NULL,
            rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
            review TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        )

    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wishlist_items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            product_id VARCHAR(255) NOT NULL,
            title VARCHAR(255) NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            image VARCHAR(255),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        )
    """)
    # In init_db(), after creating the product_categories table:

    initial_categories = [
        ('Food and Health', None),
        ('Shop by Care', None),
        ('Shop by Concern', None),
        ('Kids Special', None),
        ('Hair Care', None),
        ('Skin Care', None),
        ('Weight Management', None),
        ('Tea Blends', None),
        ('Milk Malts', 1),
        ('Amla-Human-Sanjeevani', 1),
        ('Sprouted Flours', 1),
        ('Cooking Essentials', 1),
        ('Kaaram Podis', 1),
        ('Basic Health', 1),
        ('Pregnancy Care', 2),
        ('Diabetic Care', 2),
        ('Baby Care', 2),
        ('Iron Deficiency', 3),
        ('B-Complex Deficiency', 3),
        ('Irregular Periods', 3),
        ('Constipation', 3),
        ('Bones Strength', 3),
        ('Immunity Booster', 3),
        ('Cold and Cough', 3)
    ]
    
    for name, parent_id in initial_categories:
        cursor.execute("""
        INSERT INTO product_categories (name, parent_id)
        SELECT %s, %s
        WHERE NOT EXISTS (
            SELECT 1 FROM product_categories 
            WHERE name = %s AND (parent_id = %s OR (%s IS NULL AND parent_id IS NULL))
        )
    """, (name, parent_id, name, parent_id, parent_id))
        
    # In init_db() function, add:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS category_links (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    image_path VARCHAR(255) NOT NULL,
    url VARCHAR(255) NOT NULL,
    alt_text VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS navbar_links (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            slug VARCHAR(255) NOT NULL,
            parent_id INT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            sort_order INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES navbar_links(id) ON DELETE CASCADE
        )
    """)

    # 2. Fill table if empty
    cursor.execute("SELECT COUNT(*) FROM navbar_links")
    if cursor.fetchone()[0] == 0:
        # Insert links (top-level & dropdowns)
        cursor.execute("INSERT INTO navbar_links (title, slug, sort_order) VALUES ('Home', '/', 1)")
        cursor.execute("INSERT INTO navbar_links (title, slug, sort_order) VALUES ('All Products', 'all-products', 2)")
        cursor.execute("INSERT INTO navbar_links (title, slug, sort_order) VALUES ('Food and Health', 'food-and-health', 3)")
        food_id = cursor.lastrowid
        cursor.executemany(
            "INSERT INTO navbar_links (title, slug, parent_id, sort_order) VALUES (%s, %s, %s, %s)",
            [
                ('Milk Malts', 'milk-malts', food_id, 1),
                ('Healthy Snacks', 'healthy-snacks', food_id, 2),
                ('Amla-Human Sanjeevani', 'amla-human-sanjeevani', food_id, 3),
                ('Sprouted Flours', 'sprouted-flours', food_id, 4),
                ('Cooking Essentials', 'cooking-essentials', food_id, 5),
                ("Kaaram Podi's", 'kaaram-podis', food_id, 6),
                ('Basic Health', 'basic-health', food_id, 7)
            ]
        )

        cursor.execute("INSERT INTO navbar_links (title, slug, sort_order) VALUES ('Kids Special', 'kids-special', 4)")
        cursor.execute("INSERT INTO navbar_links (title, slug, sort_order) VALUES ('Shop by Concern', 'shop-by-concern', 5)")
        concern_id = cursor.lastrowid
        cursor.executemany(
            "INSERT INTO navbar_links (title, slug, parent_id, sort_order) VALUES (%s, %s, %s, %s)",
            [
                ('Iron Deficiency', 'iron-deficiency', concern_id, 1),
                ('B-Complex Deficiency', 'b-complex-deficiency', concern_id, 2),
                ('Irregular Periods', 'irregular-periods', concern_id, 3),
                ('Constipation', 'constipation', concern_id, 4),
                ('Bones Strength', 'bones-strength', concern_id, 5),
                ('Immunity Booster', 'immunity-booster', concern_id, 6),
                ('Cold and Cough', 'cold-and-cough', concern_id, 7)
            ]
        )

        cursor.execute("INSERT INTO navbar_links (title, slug, sort_order) VALUES ('Shop by Care', 'shop-by-care', 6)")
        care_id = cursor.lastrowid
        cursor.executemany(
            "INSERT INTO navbar_links (title, slug, parent_id, sort_order) VALUES (%s, %s, %s, %s)",
            [
                ('Pregnancy Care', 'pregnancy-care', care_id, 1),
                ('Diabetic Care', 'diabetic-care', care_id, 2),
                ('Baby Care', 'baby-care', care_id, 3)
            ]
        )

        cursor.executemany(
            "INSERT INTO navbar_links (title, slug, sort_order) VALUES (%s, %s, %s)",
            [
                ('Skin Care', 'skin-care', 7),
                ('Hair Care', 'hair-care', 8),
                ('Tea Blends', 'tea-blends', 9),
                ('Weight Management', 'weight-management', 10),
                ('About Us', 'contact', 11)
            ]
        )
    
    
    
    

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
        # Check if 'image2' column exists
        cursor.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'products'
            AND COLUMN_NAME = 'image2'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE products ADD COLUMN image2 VARCHAR(255) NULL AFTER image")
         
        
        
          
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
            
        cursor.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'products'
            AND COLUMN_NAME = 'details'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE products ADD COLUMN details TEXT;")
            print("✅ Added 'details' column to products table")

        # Check and add 'ingredients' column
        cursor.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'products'
            AND COLUMN_NAME = 'ingredients'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE products ADD COLUMN ingredients TEXT;")
            print("✅ Added 'ingredients' column to products table")
          
        

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
            
        # Add sold_quantity column to products table if it doesn't exist
        cursor.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'products' 
            AND COLUMN_NAME = 'sold_quantity'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE products
                ADD COLUMN sold_quantity INT DEFAULT 0
            """)
            print("✅ Added sold_quantity column to products table")

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
        cursor.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
            WHERE CONSTRAINT_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'product_categories' 
            AND CONSTRAINT_NAME = 'uc_category_name_parent'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE product_categories 
                ADD CONSTRAINT uc_category_name_parent 
                UNIQUE (name, parent_id)
            """)
        cursor.execute(f"""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'orders' 
                AND COLUMN_NAME = 'delivered_at'
            """)
        if cursor.fetchone()[0] == 0:
                cursor.execute(f"""
                    ALTER TABLE orders 
                    ADD COLUMN delivered_at DATETIME 
                """)

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
# def migrate_products_to_db():
#     # Only import ALL_PRODUCTS if this function is called, to avoid dependency if not needed
#     try:
#         from all_products import ALL_PRODUCTS
#     except ImportError:
#         print("❌ all_products.py not found. Skipping product migration.")
#         return

#     conn = get_db_connection()
#     cursor = conn.cursor()

#     # Check if products table is empty
#     cursor.execute("SELECT COUNT(*) FROM products")
#     count = cursor.fetchone()[0]

#     if count == 0:
#         print("Migrating products from all_products.py to database...")

#         # Ensure admin user with ID 1 exists for product assignment
#         admin_user_id = 1
#         cursor.execute("SELECT id FROM users WHERE id = %s", (admin_user_id,))
#         if not cursor.fetchone():
#             from werkzeug.security import generate_password_hash
#             # Create a default admin user if ID 1 doesn't exist
#             hashed_password = generate_password_hash("admin123") # Default password for admin
#             cursor.execute("""
#                 INSERT INTO users (id, name, email, password_hash, role)
#                 VALUES (%s, %s, %s, %s, %s)
#             """, (admin_user_id, 'Admin', 'admin@example.com', hashed_password, 'admin'))
#             conn.commit() # Commit the new admin user
#             print("✅ Created default admin user with ID 1 (admin@example.com / admin123)")
#         else:
#             print("Admin user with ID 1 already exists.")

#         # Now migrate products
#         for product in ALL_PRODUCTS:
#             try:
#                 # Insert product
#                 cursor.execute(
#                     """INSERT INTO products (id, seller_id, title, price, compare_price, image, tags, description, benefits, category, status)
#                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved')""",
#                     (product['id'],
#                      admin_user_id, # Assign to default admin
#                      product['title'],
#                      product['price'],
#                      product.get('compare_price'),
#                      product.get('image'),
#                      ','.join(product.get('tags', [])),
#                      product.get('description'),
#                      ','.join(product.get('benefits', [])),
#                      product.get('category'))
#                 )
                
#                 # Create inventory record with 0 stock - sellers will add stock themselves
#                 cursor.execute("""
#                     INSERT INTO inventory (product_id, stock_quantity)
#                     VALUES (%s, %s)
#                 """, (product['id'], 0))  # Start with 0 stock
                
#                 # Insert product approval record
#                 cursor.execute("""
#                     INSERT INTO product_approvals (product_id, status, reviewed_by, reviewed_at)
#                     VALUES (%s, 'approved', %s, NOW())
#                 """, (product['id'], admin_user_id))
                
#             except mysql.connector.Error as err:
#                 if err.errno == 1062: # Duplicate entry for primary key 'id'
#                     print(f"Product '{product['id']}' already exists. Skipping.")
#                 else:
#                     print(f"Error migrating product {product['id']}: {err}")
        
#         conn.commit()
#         print(f"✅ Migrated {len(ALL_PRODUCTS)} products to the database. Stock quantities set to 0 - sellers can update them.")
#     else:
#         print("Products table is not empty. Skipping migration.")

#     cursor.close()
#     conn.close()
def migrate_products_to_db():
    """Initial migration setup without importing all_products.py"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if products table is empty
    cursor.execute("SELECT COUNT(*) FROM products")
    count = cursor.fetchone()[0]

    if count == 0:
        print("Products table is empty. No automatic migration will be performed.")

        # Ensure admin user with ID 1 exists
        admin_user_id = 1
        cursor.execute("SELECT id FROM users WHERE id = %s", (admin_user_id,))
        if not cursor.fetchone():
            from werkzeug.security import generate_password_hash
            hashed_password = generate_password_hash("admin123")
            cursor.execute("""
                INSERT INTO users (id, name, email, password_hash, role)
                VALUES (%s, %s, %s, %s, %s)
            """, (admin_user_id, 'Admin', 'admin@example.com', hashed_password, 'admin'))
            conn.commit()
            print("✅ Created default admin user with ID 1 (admin@example.com / admin123)")
        else:
            print("Admin user with ID 1 already exists.")
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
        LEFT JOIN inventory i ON p.id = i.product_id WHERE p.status = 'approved'
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
        WHERE p.id = %s AND p.status = 'approved'
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
            """INSERT INTO products 
            (id, seller_id, title, price, compare_price, image, tags, description, benefits, category, sub_category, details, ingredients)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (product_data['id'], product_data['seller_id'], product_data['title'], price, compare_price,
            product_data.get('image'), ','.join(product_data.get('tags', [])),
            product_data.get('description'), ','.join(product_data.get('benefits', [])),
            product_data.get('category'), product_data.get('sub_category'),
            product_data.get('details'), product_data.get('ingredients'))
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
            """UPDATE products 
               SET title = %s,
                   price = %s,
                   compare_price = %s,
                   image = %s,
                   tags = %s,
                   description = %s,
                   benefits = %s,
                   category = %s,
                   sub_category = %s,
                   details = %s,
                   ingredients = %s
             WHERE id = %s AND seller_id = %s""",
            (
                product_data['title'],
                price,
                compare_price,
                product_data.get('image'),
                ','.join(product_data.get('tags', [])),
                product_data.get('description'),
                ','.join(product_data.get('benefits', [])),
                product_data.get('category'),
                product_data.get('sub_category'),
                product_data.get('details'),
                product_data.get('ingredients'),
                product_id,
                product_data['seller_id']
            )
        )

        # Update inventory quantity
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
        WHERE (p.category = %s OR p.sub_category = %s) AND p.status = 'approved'
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
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM carousel_slides WHERE is_active = TRUE ORDER BY sort_order")
    carousel_slides = cursor.fetchall()
    cursor.execute("SELECT * FROM category_links WHERE is_active = TRUE ORDER BY sort_order ASC")
    category_links = cursor.fetchall()
    conn.close()
    cart_length = get_cart_length()
    all_products_data = get_all_products_from_db()

    # Get unique products (by title)
    unique_products = []
    seen_titles = set()
    for product_item in all_products_data:
        if product_item['title'] not in seen_titles:
            unique_products.append(product_item)
            seen_titles.add(product_item['title'])

    # Get newest approved products
    all_newest_products = sorted(
    [p for p in all_products_data if p.get('status') == 'approved'],
    key=lambda x: x.get('created_at', ''), 
    reverse=True
)

    newest_products = all_newest_products[:7]  # Only first 8 for display


    # Get best selling products (sorted by sold_quantity)
    all_best_sellers = sorted(
    [p for p in all_products_data if p.get('sold_quantity', 0) > 0],
    key=lambda x: x.get('sold_quantity', 0),
    reverse=True
)

    best_sellers = all_best_sellers[:7]  # For homepage display


    return render_template("base.html", 
                         carousel_slides=carousel_slides,
                         category_links=category_links,
                         collection={'products': unique_products},
                         newest_products=newest_products,
                         all_newest_products=all_newest_products,
                         best_sellers=best_sellers,
                         all_best_sellers=all_best_sellers,
                         current_collection='all-products',
                         cart_length=cart_length)

ITEMS_PER_PAGE = 12  # number of products per page

@app.route('/recently-added')
def recently_added():
    all_products_data = get_all_products_from_db()
    thirty_days_ago = datetime.now() - timedelta(days=45)

    newest_products = [
        p for p in all_products_data
        if p.get('status') == 'approved'
        and isinstance(p.get('created_at'), datetime)
        and p['created_at'] >= thirty_days_ago
    ]
    newest_products = sorted(newest_products, key=lambda x: x['created_at'], reverse=True)

    # --- Pagination ---
    page = request.args.get('page', 1, type=int)
    total_pages = ceil(len(newest_products) / ITEMS_PER_PAGE)
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    paginated_products = newest_products[start:end]

    cart_length = get_cart_length()
    return render_template(
        "recently_added.html",
        newest_products=paginated_products,
        cart_length=cart_length,
        current_collection="recently-added",
        page=page,
        total_pages=total_pages
    )


@app.route('/most-sold')
def most_sold():
    all_products_data = get_all_products_from_db()
    best_sellers = sorted(
        [p for p in all_products_data if p.get('sold_quantity', 0) > 0],
        key=lambda x: x['sold_quantity'],
        reverse=True
    )

    # --- Pagination ---
    page = request.args.get('page', 1, type=int)
    total_pages = ceil(len(best_sellers) / ITEMS_PER_PAGE)
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    paginated_products = best_sellers[start:end]

    cart_length = get_cart_length()
    return render_template(
        "most_sold.html",
        best_sellers=paginated_products,
        cart_length=cart_length,
        current_collection="most-sold",
        page=page,
        total_pages=total_pages
    )




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
    


@app.route('/category/<parent_slug>')
def parent_category_page(parent_slug):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # First, get the category name from the slug
    cursor.execute("""
        SELECT name FROM product_categories 
        WHERE parent_id IS NULL 
        AND is_active = TRUE
        AND %s = LOWER(REPLACE(name, ' ', '-'))
    """, (parent_slug,))
    category = cursor.fetchone()
    
    if not category:
        abort(404)
        
    category_name = category['name']

    # Get all active subcategories for this parent category
    cursor.execute("""
        SELECT 
            c.id AS child_id,
            c.name AS child_name,
            c.parent_id,
            p.name AS parent_name
        FROM 
            product_categories c
        JOIN 
            product_categories p ON c.parent_id = p.id
        WHERE 
            p.name = %s
            AND c.is_active = TRUE
        ORDER BY c.name
    """, (category_name,))
    
    subcategories = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('subcategory_list.html',
                           parent_category=category_name,
                           parent_slug=parent_slug,
                           subcategories=subcategories)




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

@app.route('/toggle-wishlist/<product_id>', methods=['POST'])
def toggle_wishlist(product_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Please log in to use wishlist"}), 401
    if session.get('user_role') != 'customer':
        return jsonify({"success": False, "message": "Wishlist is only available for customers"}), 403
    
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM wishlist_items WHERE user_id=%s AND product_id=%s",
                   (user_id, product_id))
    existing = cursor.fetchone()

    in_wishlist = False
    if existing:
        cursor.execute("DELETE FROM wishlist_items WHERE user_id=%s AND product_id=%s",
                       (user_id, product_id))
        conn.commit()
        in_wishlist = False
    else:
        cursor.execute("SELECT title, price, image FROM products WHERE id=%s", (product_id,))
        product = cursor.fetchone()
        if product:
            cursor.execute(
                "INSERT INTO wishlist_items (user_id, product_id, title, price, image) VALUES (%s,%s,%s,%s,%s)",
                (user_id, product_id, product[0], product[1], product[2])
            )
            conn.commit()
            in_wishlist = True

    cursor.close()
    conn.close()
    return jsonify({"success": True, "in_wishlist": in_wishlist})


@app.route('/products/<product_id>')
def product(product_id):
    product_item = get_product_by_id_from_db(product_id)
    if not product_item:
        abort(404)
    recently_viewed = session.get('recently_viewed', [])
    # Remove if already exists
    recently_viewed = [p for p in recently_viewed if p['id'] != product_item['id']]
    # Insert at beginning
    recently_viewed.insert(0, {
    'id': product_item['id'],
    'title': product_item['title'],
    'image': product_item['image'],
    'price': product_item['price'],
    'in_stock': product_item['stock_quantity'] > 0
})

    # Keep only last 5 viewed
    recently_viewed = recently_viewed[:6]
    session['recently_viewed'] = recently_viewed
    # Get reviews for the product
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT r.*, u.name as user_name FROM product_reviews r
        JOIN users u ON r.user_id = u.id
        WHERE r.product_id = %s
        ORDER BY r.created_at DESC
    """, (product_id,))
    reviews = cursor.fetchall()
    cursor.close()
    conn.close()

    user_has_purchased = False
    if 'user_id' in session:
        user_has_purchased = user_has_purchased_product(session['user_id'], product_id)
        
    in_wishlist = False
    if 'user_id' in session:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM wishlist_items WHERE user_id=%s AND product_id=%s",
                    (session['user_id'], product_id))
        in_wishlist = cursor.fetchone() is not None
        cursor.close()
        conn.close()


    collection_title = product_item.get('category', 'Products').replace('-', ' ').title()

    return render_template('product.html',
                           product=product_item,
                           collection_title=collection_title,
                           reviews=reviews,
                           user_has_purchased=user_has_purchased,in_wishlist=in_wishlist)

@app.route('/wishlist')
def wishlist():
    if 'user_id' not in session:
        flash("Please log in to use wishlist", "warning")
        return redirect(url_for('login'))
    if session.get('user_role') != 'customer':
        flash("Wishlist functionality is only available for customers", "warning")
        return redirect(url_for('home'))
   
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT w.product_id as id, w.title, w.price, w.image,
               COALESCE(i.stock_quantity, 0) as stock_quantity
        FROM wishlist_items w
        LEFT JOIN inventory i ON w.product_id = i.product_id
        WHERE w.user_id = %s
    """, (user_id,))
    wishlist_items = cursor.fetchall()
    conn.close()

    return render_template("wishlist.html", wishlist_items=wishlist_items)

def get_wishlist_length():
    """Returns the number of items in the user's wishlist"""
    if 'user_id' not in session:
        return 0
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM wishlist_items WHERE user_id = %s", (session['user_id'],))
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count



@app.route('/move-to-wishlist/<product_id>', methods=['POST'])
def move_to_wishlist(product_id):
    if 'user_id' not in session:
        flash("Please log in to use wishlist", "warning")
        return redirect(url_for('login'))
    if session.get('user_role') != 'customer':
        flash("Wishlist functionality is only available for customers", "warning")
        return redirect(url_for('home'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get product details from cart
    cursor.execute("SELECT title, price, image FROM cart_items WHERE user_id=%s AND product_id=%s",
                   (user_id, product_id))
    product = cursor.fetchone()

    if product:
        # ✅ Check if already in wishlist
        cursor.execute("SELECT id FROM wishlist_items WHERE user_id=%s AND product_id=%s",
                       (user_id, product_id))
        existing = cursor.fetchone()

        if existing:
            flash("This item is already in your wishlist ❤️", "info")
        else:
            cursor.execute("""INSERT INTO wishlist_items (user_id, product_id, title, price, image) 
                              VALUES (%s, %s, %s, %s, %s)""",
                           (user_id, product_id, product["title"], product["price"], product["image"]))
            flash("Moved to Wishlist ❤️", "success")

        # Always remove from cart (to avoid duplicates in cart)
        cursor.execute("DELETE FROM cart_items WHERE user_id=%s AND product_id=%s",
                       (user_id, product_id))
        conn.commit()

    cursor.close()
    conn.close()
    return redirect(url_for('cart'))



@app.route('/move-to-cart/<product_id>', methods=['POST'])
def move_to_cart(product_id):
    if 'user_id' not in session:
        flash("Please log in to use wishlist", "warning")
        return redirect(url_for('login'))
    if session.get('user_role') != 'customer':
        flash("Wishlist functionality is only available for customers", "warning")
        return redirect(url_for('home'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get product details from wishlist
    cursor.execute("SELECT title, price, image FROM wishlist_items WHERE user_id=%s AND product_id=%s",
                   (user_id, product_id))
    product = cursor.fetchone()

    if product:
        # Check if already in cart
        cursor.execute("SELECT id, quantity FROM cart_items WHERE user_id=%s AND product_id=%s",
                       (user_id, product_id))
        existing_cart = cursor.fetchone()

        if existing_cart:
            # Update quantity instead of creating duplicate row
            new_quantity = existing_cart["quantity"] + 1
            cursor.execute("UPDATE cart_items SET quantity=%s WHERE id=%s",
                           (new_quantity, existing_cart["id"]))
        else:
            # Insert new cart row
            cursor.execute("""INSERT INTO cart_items (user_id, product_id, title, price, image, quantity)
                              VALUES (%s, %s, %s, %s, %s, %s)""",
                           (user_id, product_id, product["title"], product["price"], product["image"], 1))

        # Remove from wishlist
        cursor.execute("DELETE FROM wishlist_items WHERE user_id=%s AND product_id=%s",
                       (user_id, product_id))

        conn.commit()
        flash("Moved to Cart 🛒", "success")

    cursor.close()
    conn.close()
    
    # Smart redirect logic - same as remove_from_wishlist
    redirect_to = request.args.get('redirect_to')
    if redirect_to == 'wishlist':
        return redirect(url_for('wishlist'))
    elif redirect_to == 'profile':
        return redirect(url_for('profile'))
    else:
        # Use referer to automatically detect where user came from
        referer = request.headers.get('Referer', '')
        if 'wishlist' in referer:
            return redirect(url_for('wishlist'))
        else:
            return redirect(url_for('profile'))

@app.route('/remove-from-wishlist/<product_id>', methods=['POST'])
def remove_from_wishlist(product_id):
    if 'user_id' not in session:
        flash("Please log in to use wishlist", "warning")
        return redirect(url_for('login'))
    if session.get('user_role') != 'customer':
        flash("Wishlist functionality is only available for customers", "warning")
        return redirect(url_for('home'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM wishlist_items WHERE user_id=%s AND product_id=%s", 
                   (user_id, product_id))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Item removed from wishlist ❌", "info")
    
    # Check for redirect parameter to determine where to go
    redirect_to = request.args.get('redirect_to', 'profile')  # Default to 'profile'
    
    if redirect_to == 'profile':
        return redirect(url_for('profile'))
    else:
        return redirect(url_for('wishlist'))


@app.route('/cart')
def cart():
    message = request.args.get('message')
    product_title = request.args.get('product_title')
    
    if message == 'out_of_stock' and product_title:
        flash(f"{product_title} added to cart! Note: This product is currently out of stock.", "warning")
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
    recently_viewed = session.get('recently_viewed', [])
    wishlist_length = get_wishlist_length()

    return render_template('cart.html', cart_items=cart_items, total_price=total_price,recently_viewed=recently_viewed,wishlist_length=wishlist_length)

@app.route('/remove-from-cart/<product_id>', methods=['POST'])
def remove_from_cart(product_id):
    user_id = session.get('user_id')

    if user_id:
        # Remove from DB cart
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cart_items WHERE user_id = %s AND product_id = %s", (user_id, product_id))
        conn.commit()
        conn.close()
    else:
        # Remove from session cart
        cart = session.get('cart', [])
        session['cart'] = [item for item in cart if str(item['id']) != str(product_id)]

    flash("Item removed from cart.", "info")
    return redirect(url_for('cart'))



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

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash("Please log in first", "warning")
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get user details
    cursor.execute("SELECT id, name, email, mobile FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()

    # Get user addresses
    cursor.execute("SELECT * FROM user_addresses WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
    addresses = cursor.fetchall()

    # Get previous orders
    cursor.execute("""
        SELECT id, total_amount, status, order_date 
        FROM orders 
        WHERE user_id = %s 
        ORDER BY order_date DESC
    """, (session['user_id'],))
    orders = cursor.fetchall()
    #wishlist
    cursor.execute("""
        SELECT w.product_id, w.title, w.price, w.image, 
               COALESCE(i.stock_quantity, 0) as stock_quantity
        FROM wishlist_items w 
        LEFT JOIN inventory i ON w.product_id = i.product_id
        WHERE w.user_id = %s
    """, (session['user_id'],))
    wishlist = cursor.fetchall()
    

    cursor.close()
    conn.close()

    return render_template("profile.html", user=user, addresses=addresses, orders=orders, wishlist=wishlist)


@app.route('/profile/address/add', methods=['POST'])
def add_address():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    data = request.form
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_addresses 
        (user_id, name, mobile, address_line1, address_line2, city, state, pincode, country, is_default)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (session['user_id'], data['name'], data['mobile'], data['address_line1'], data.get('address_line2'),
          data['city'], data['state'], data['pincode'], data.get('country', 'India'), data.get('is_default', 0)))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Address added successfully!", "success")
    return redirect(url_for('profile'))


@app.route('/profile/address/delete/<int:address_id>', methods=['POST'])
def delete_address(address_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_addresses WHERE id = %s AND user_id = %s", (address_id, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Address deleted successfully!", "info")
    return redirect(url_for('profile'))


@app.route('/profile/edit', methods=['POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    data = request.form
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET name = %s, email = %s, mobile = %s 
        WHERE id = %s
    """, (data['name'], data['email'], data['mobile'], session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Profile updated successfully!", "success")
    return redirect(url_for('profile'))
@app.route('/make_default_address/<int:address_id>', methods=['POST'])
def make_default_address(address_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    # Reset all addresses to not default
    cursor.execute("UPDATE user_addresses SET is_default = 0 WHERE user_id = %s", (user_id,))
    # Set chosen one as default
    cursor.execute("UPDATE user_addresses SET is_default = 1 WHERE id = %s AND user_id = %s", (address_id, user_id))
    conn.commit()

    cursor.close()
    conn.close()

    flash("Default address updated successfully!", "success")
    return redirect(request.referrer or url_for('profile'))




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


# @app.route('/admin/customers')
# @role_required('admin')
# def admin_view_customers():
#     """Admin view to list all customers."""
#     customers = get_all_customers_from_db()
#     return render_template('admin_customers.html', customers=customers)

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

# @app.route('/admin/sellers')
# @role_required('admin')
# def admin_view_sellers():
#     """Admin view to list all sellers."""
#     sellers = get_all_sellers_from_db()
#     return render_template('admin_sellers.html', sellers=sellers)

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
        session['mobile'] = request.form['mobile']
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
            
            # Check seller approval status
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT approval_status 
                FROM seller_profiles 
                WHERE user_id = %s
            """, (user['id'],))
            profile = cursor.fetchone()
            conn.close()

            if not profile or profile['approval_status'] != 'approved':
                flash("Your account is awaiting admin approval.", "warning")
                return redirect(url_for('seller_login'))

            # Seller approved → set session
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            flash("Login successful", "success")
            return redirect(url_for('seller_dashboard'))
        
        flash("Invalid email or password", "danger")
    
    return render_template('seller_login.html')


@app.route('/seller/forgot-password', methods=['GET', 'POST'])
def seller_forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        
        # Check if user exists and is an approved seller
        user = get_user_by_email(email)
        if not user or user['role'] != 'seller':
            flash("No seller account found with this email", "danger")
            return redirect(url_for('seller_forgot_password'))
        
        # Check if seller is approved
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT approval_status FROM seller_profiles 
            WHERE user_id = %s
        """, (user['id'],))
        seller_profile = cursor.fetchone()
        conn.close()
        
        if not seller_profile or seller_profile['approval_status'] != 'approved':
            flash("Your seller account is not approved yet. Please contact admin.", "warning")
            return redirect(url_for('seller_forgot_password'))
        
        # Generate OTP
        otp = str(random.randint(100000, 999999))
        session['seller_reset_email'] = email
        session['seller_reset_otp'] = otp
        session['seller_reset_otp_time'] = time.time()  # Store generation time
        
        # Send OTP email
        msg = Message("Seller Password Reset OTP", recipients=[email])
        msg.body = f"Your password reset OTP is {otp}. This OTP is valid for 10 minutes."
        mail.send(msg)
        
        flash("OTP sent to your email. Please check your inbox.", "success")
        return redirect(url_for('seller_verify_reset_otp'))
    
    return render_template('seller_forgot_password.html')

@app.route('/seller/verify-reset-otp', methods=['GET', 'POST'])
def seller_verify_reset_otp():
    if 'seller_reset_email' not in session:
        flash("Password reset session expired. Please try again.", "danger")
        return redirect(url_for('seller_forgot_password'))
    
    if request.method == 'POST':
        entered_otp = request.form['otp']
        new_password = request.form['new_password']
        email = session.get('seller_reset_email')
        
        # Check if OTP is expired (10 minutes)
        if time.time() - session.get('seller_reset_otp_time', 0) > 600:
            session.pop('seller_reset_email', None)
            session.pop('seller_reset_otp', None)
            session.pop('seller_reset_otp_time', None)
            flash("OTP has expired. Please request a new one.", "danger")
            return redirect(url_for('seller_forgot_password'))
        
        if entered_otp == session.get('seller_reset_otp') and email:
            hashed_password = generate_password_hash(new_password)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password_hash = %s WHERE email = %s", (hashed_password, email))
            conn.commit()
            conn.close()
            
            session.pop('seller_reset_email', None)
            session.pop('seller_reset_otp', None)
            session.pop('seller_reset_otp_time', None)
            
            flash("Password reset successfully. You can now login with your new password.", "success")
            return redirect(url_for('seller_login'))
        else:
            flash("Invalid OTP. Please try again.", "danger")
    
    return render_template('seller_verify_reset_otp.html')


@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        user_otp = request.form['otp']
        if user_otp == session.get('otp'):
            hashed_password = generate_password_hash(session['password'])

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, email,mobile, password_hash, role) VALUES (%s, %s, %s, %s)",
                (session['name'], session['email'],session['mobile'], hashed_password, 'customer')
            )
            conn.commit()
            conn.close()

            session.pop('name', None)
            session.pop('email', None)
            session.pop('mobile', None)
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


@app.route('/profile/change_password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        flash("Please log in first", "warning")
        return redirect(url_for('login'))

    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch stored hash + role
    cursor.execute("SELECT password_hash, role FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()

    if not user or not check_password_hash(user['password_hash'], current_password):
        flash("Current password is incorrect.", "danger")
        return redirect(url_for('seller_dashboard') if user and user['role'] == 'seller' else url_for('profile'))

    if new_password != confirm_password:
        flash("New passwords do not match.", "danger")
        return redirect(url_for('seller_dashboard') if user and user['role'] == 'seller' else url_for('profile'))

    # Update password_hash
    hashed = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s", (hashed, session['user_id']))
    conn.commit()

    cursor.close()
    conn.close()

    flash("Password updated successfully!", "success")
    return redirect(url_for('seller_dashboard') if user['role'] == 'seller' else url_for('profile'))




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
    product = get_product_by_id_from_db(product_id)

    if not product:
        flash("Product not found", "danger")
        return redirect(url_for('home'))

    title = product['title']
    price = float(product['price'])
    image = product['image']
    stock_quantity = product.get('stock_quantity', 0)

    user_id = session.get('user_id')
    user_role = session.get('user_role')

    # 🚫 Block sellers and admins
    if user_role in ['seller', 'admin']:
        flash("Only customers can add products to the cart.", "danger")
        return redirect(url_for('home'))

    if user_id:  # ✅ Logged in customer
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT quantity FROM cart_items WHERE user_id = %s AND product_id = %s", (user_id, product_id))
        existing_item = cursor.fetchone()

        if existing_item:
            new_quantity = existing_item[0] + 1
            cursor.execute("UPDATE cart_items SET quantity = %s WHERE user_id = %s AND product_id = %s",
                           (new_quantity, user_id, product_id))
        else:
            cursor.execute(
                "INSERT INTO cart_items (user_id, product_id, title, price, image, quantity) VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, product_id, title, price, image, 1)
            )
        conn.commit()
        conn.close()
    else:  # ✅ Guest user (session cart)
        cart = session.get('cart', [])
        for item in cart:
            if item['id'] == product_id:
                item['quantity'] += 1
                break
        else:
            cart.append({'id': product_id, 'title': title, 'price': price, 'image': image, 'quantity': 1})
        session['cart'] = cart

    # Show appropriate message based on stock status
    if stock_quantity < 1:
        return redirect(url_for('cart', message='out_of_stock', product_title=title))
    else:
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
            flash("Product ID is required", "danger")
            return redirect(url_for('admin_products'))

        conn = get_db_connection()
        cursor = conn.cursor()
        conn.start_transaction()

        cursor.execute("SELECT id FROM products WHERE id = %s", (product_id,))
        if not cursor.fetchone():
            conn.rollback()
            flash("Product not found", "danger")
            return redirect(url_for('admin_products'))

        cursor.execute("""
            INSERT INTO product_approvals (product_id, status, reviewed_by, reviewed_at)
            VALUES (%s, 'approved', %s, NOW())
            ON DUPLICATE KEY UPDATE 
                status = 'approved',
                reviewed_by = VALUES(reviewed_by),
                reviewed_at = NOW(),
                rejection_reason = NULL
        """, (product_id, session['user_id']))

        cursor.execute("UPDATE products SET status = 'approved' WHERE id = %s", (product_id,))
        if cursor.rowcount == 0:
            conn.rollback()
            flash("Failed to update product status", "danger")
            return redirect(url_for('admin_products'))

        conn.commit()
        flash("Product approved successfully", "success")
        return redirect(url_for('admin_products'))

    except mysql.connector.Error as db_err:
        if conn: conn.rollback()
        flash(f"Database error: {db_err}", "danger")
        return redirect(url_for('admin_products'))
    except Exception as e:
        if conn: conn.rollback()
        flash(f"Error: {e}", "danger")
        return redirect(url_for('admin_products'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@app.route('/admin/reject_product', methods=['POST'])
@role_required('admin')
def admin_reject_product():
    conn = None
    cursor = None
    try:
        product_id = request.form.get('product_id')
        reason = request.form.get('rejection_reason', '').strip()

        if not product_id:
            flash("Product ID is required", "danger")
            return redirect(url_for('admin_products'))
        if not reason:
            flash("Rejection reason is required", "danger")
            return redirect(url_for('admin_products'))

        conn = get_db_connection()
        cursor = conn.cursor()
        conn.start_transaction()

        cursor.execute("SELECT id FROM products WHERE id = %s", (product_id,))
        if not cursor.fetchone():
            conn.rollback()
            flash("Product not found", "danger")
            return redirect(url_for('admin_products'))

        cursor.execute("UPDATE products SET status = 'rejected' WHERE id = %s", (product_id,))
        cursor.execute("""
            INSERT INTO product_approvals (product_id, status, rejection_reason, reviewed_by, reviewed_at)
            VALUES (%s, 'rejected', %s, %s, NOW())
            ON DUPLICATE KEY UPDATE 
                status = 'rejected',
                rejection_reason = VALUES(rejection_reason),
                reviewed_by = VALUES(reviewed_by),
                reviewed_at = NOW()
        """, (product_id, reason, session['user_id']))

        if cursor.rowcount == 0:
            conn.rollback()
            flash("Failed to update product status", "danger")
            return redirect(url_for('admin_products'))

        conn.commit()
        flash("Product rejected successfully", "warning")
        return redirect(url_for('admin_products'))

    except mysql.connector.Error as db_err:
        if conn: conn.rollback()
        flash(f"Database error: {db_err}", "danger")
        return redirect(url_for('admin_products'))
    except Exception as e:
        if conn: conn.rollback()
        flash(f"Error: {e}", "danger")
        return redirect(url_for('admin_products'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

            
@app.route('/admin/carousel', methods=['GET', 'POST'])
@role_required('admin')
def admin_carousel():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        # Handle form submission for adding/editing slides
        action = request.form.get('action')
        
        if action == 'add':
            # Process new slide
            image_file = request.files.get('image')
            if image_file and allowed_file(image_file.filename):
                filename = secure_filename(image_file.filename)
                image_path = os.path.join('images', filename).replace('\\', '/')
                full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_file.save(full_path)
                
                cursor.execute("""
                    INSERT INTO carousel_slides 
                    (image_path, alt_text, title, description, link_url, sort_order)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    image_path,
                    request.form.get('alt_text'),
                    request.form.get('title'),
                    request.form.get('description'),
                    request.form.get('link_url'),
                    request.form.get('sort_order', 0)
                ))
                conn.commit()
                flash('New slide added successfully!', 'success')
        
        elif action == 'update':
            # Process slide update
            slide_id = request.form.get('slide_id')
            updates = []
            params = []
            
            if 'image' in request.files and request.files['image'].filename:
                image_file = request.files['image']
                if allowed_file(image_file.filename):
                    filename = secure_filename(image_file.filename)
                    image_path = os.path.join('images', filename)
                    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    image_file.save(full_path)
                    updates.append("image_path = %s")
                    params.append(image_path)
            
            for field in ['alt_text', 'title', 'description', 'link_url', 'sort_order']:
                if field in request.form:
                    updates.append(f"{field} = %s")
                    params.append(request.form[field])
            
            if updates:
                params.append(slide_id)
                query = f"UPDATE carousel_slides SET {', '.join(updates)} WHERE id = %s"
                cursor.execute(query, params)
                conn.commit()
                flash('Slide updated successfully!', 'success')
        
        elif action == 'delete':
            slide_id = request.form.get('slide_id')
            cursor.execute("DELETE FROM carousel_slides WHERE id = %s", (slide_id,))
            conn.commit()
            flash('Slide deleted successfully!', 'success')
    
    # Get all slides
    cursor.execute("SELECT * FROM carousel_slides ORDER BY sort_order, created_at DESC")
    slides = cursor.fetchall()
    conn.close()
    
    return render_template('admin_carousel.html', slides=slides,active_section='carousel')

@app.route('/admin/links', methods=['GET', 'POST'])
@role_required('admin')
def admin_links():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            title = request.form['title']
            alt_text = request.form.get('alt_text')
            url = request.form['url']
            sort_order = int(request.form.get('sort_order', 0))
            image = request.files['image']

            if image and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image.save(image_path)
                db_path = os.path.relpath(image_path, 'static')

                cursor.execute("""INSERT INTO category_links (title, image_path, alt_text, url, sort_order) 
                                  VALUES (%s, %s, %s, %s, %s)""",
                               (title, db_path, alt_text, url, sort_order))
                conn.commit()

        elif action == 'update':
            link_id = request.form['link_id']
            title = request.form['title']
            alt_text = request.form.get('alt_text')
            url = request.form['url']
            sort_order = int(request.form.get('sort_order', 0))
            image = request.files['image']

            if image and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image.save(image_path)
                db_path = os.path.relpath(image_path, 'static')
                cursor.execute("""UPDATE category_links SET title=%s, image_path=%s, alt_text=%s, url=%s, sort_order=%s WHERE id=%s""",
                               (title, db_path, alt_text, url, sort_order, link_id))
            else:
                cursor.execute("""UPDATE category_links SET title=%s, alt_text=%s, url=%s, sort_order=%s WHERE id=%s""",
                               (title, alt_text, url, sort_order, link_id))

            conn.commit()

        elif action == 'delete':
            link_id = request.form['link_id']
            cursor.execute("DELETE FROM category_links WHERE id = %s", (link_id,))
            conn.commit()

    cursor.execute("SELECT * FROM category_links ORDER BY sort_order ASC")
    links = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("admin_links.html", links=links, active_section='links')






def cleanup_duplicate_categories():
    """Temporary function to clean up duplicate categories"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            CREATE TEMPORARY TABLE temp_categories AS
            SELECT MIN(id) as id, name, parent_id
            FROM product_categories
            GROUP BY name, parent_id;
        """)
        
        cursor.execute("""
            DELETE FROM product_categories
            WHERE id NOT IN (SELECT id FROM temp_categories);
        """)
        
        cursor.execute("DROP TEMPORARY TABLE temp_categories;")
        conn.commit()
        print("✅ Duplicate categories cleaned up successfully")
    except Exception as e:
        conn.rollback()
        print(f"Error cleaning duplicates: {e}")
    finally:
        conn.close()



# Add these new routes to your app3.py
cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})
cache.init_app(app)



@cache.cached(timeout=300)

@app.route('/admin/categories')
@role_required('admin')
def admin_categories():
    """Admin view to manage product categories and subcategories"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get all categories with their hierarchy information
    cursor.execute("""
        SELECT 
            c.id,
            c.name,
            c.is_active,
            c.parent_id,
            p.name AS parent_name
        FROM product_categories c
        LEFT JOIN product_categories p ON c.parent_id = p.id
        ORDER BY COALESCE(c.parent_id, c.id), c.id
    """)
    
    all_categories = cursor.fetchall()
    conn.close()
    
    # Organize categories into a dictionary
    categories_dict = {}
    for cat in all_categories:
        if cat['parent_id'] is None:
            # It's a parent category
            if cat['id'] not in categories_dict:
                categories_dict[cat['id']] = {
                    'id': cat['id'],
                    'name': cat['name'],
                    'is_active': cat['is_active'],
                    'subcategories': []
                }
        else:
            # It's a subcategory
            if cat['parent_id'] in categories_dict:
                categories_dict[cat['parent_id']]['subcategories'].append({
                    'id': cat['id'],
                    'name': cat['name'],
                    'is_active': cat['is_active']
                })
    
    # Convert dictionary to list for template
    categories = list(categories_dict.values())
    
    # Get just parent categories for the form dropdown
    parent_categories = [{
        'id': cat['id'],
        'name': cat['name']
    } for cat in categories_dict.values()]
    
    # Convert flash messages to JSON
    flash_messages = [
        {'category': cat, 'message': msg} 
        for cat, msg in get_flashed_messages(with_categories=True)
    ]
    
    return render_template('admin_categories.html',
                         parent_categories=parent_categories,
                         categories=categories,
                         active_section='categories',
                         flash_messages_json=json.dumps(flash_messages))  # Add this line

@app.route('/admin/add_category', methods=['POST'])
@role_required('admin')
def add_category():
    """Add a new category or subcategory"""
    name = request.form.get('name', '').strip()
    parent_id = request.form.get('parent_id') or None
    
    if not name:
        flash('Category name is required', 'danger')
        return redirect(url_for('admin_categories'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if the category exists at any level with the same name
        cursor.execute("""
            SELECT 1 FROM product_categories 
            WHERE name = %s AND (parent_id = %s OR (%s IS NULL AND parent_id IS NULL))
            LIMIT 1
        """, (name, parent_id, parent_id))
            
        if cursor.fetchone():
            flash(f'A category with name "{name}" already exists at this level', 'danger')
            return redirect(url_for('admin_categories'))
        
        # Insert the new category
        cursor.execute("""
            INSERT INTO product_categories (name, parent_id)
            VALUES (%s, %s)
        """, (name, parent_id))
        
        conn.commit()
        
        if parent_id:
            flash(f'Subcategory "{name}" added successfully', 'success')
        else:
            flash(f'Main category "{name}" added successfully', 'success')
            
    except mysql.connector.Error as err:
        conn.rollback()
        flash(f'Error adding category: {err}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('admin_categories'))

@app.route('/admin/toggle_category/<int:category_id>', methods=['POST'])
@role_required('admin')
def toggle_category(category_id):
    """Toggle category active status"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get current status
        cursor.execute("SELECT is_active FROM product_categories WHERE id = %s", (category_id,))
        category = cursor.fetchone()
        
        if not category:
            flash('Category not found', 'danger')
            return redirect(url_for('admin_categories'))
        
        new_status = not category['is_active']
        
        # Update status
        cursor.execute("""
            UPDATE product_categories 
            SET is_active = %s 
            WHERE id = %s
        """, (new_status, category_id))
        
        # If deactivating a parent category, also deactivate its subcategories
        if not new_status:
            cursor.execute("""
                UPDATE product_categories 
                SET is_active = FALSE 
                WHERE parent_id = %s
            """, (category_id,))
        
        conn.commit()
        status = 'activated' if new_status else 'deactivated'
        flash(f'Category {status} successfully', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error updating category: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('admin_categories'))

@app.route('/admin/delete_category/<int:category_id>', methods=['POST'])
@role_required('admin')
def delete_category(category_id):
    """Delete a category or subcategory"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if category has products
        cursor.execute("""
            SELECT COUNT(*) 
            FROM products 
            WHERE category = (SELECT name FROM product_categories WHERE id = %s)
               OR sub_category = (SELECT name FROM product_categories WHERE id = %s)
        """, (category_id, category_id))
        
        product_count = cursor.fetchone()[0]
        if product_count > 0:
            flash('Cannot delete category with associated products', 'danger')
            return redirect(url_for('admin_categories'))
        
        # Delete the category
        cursor.execute("DELETE FROM product_categories WHERE id = %s", (category_id,))
        conn.commit()
        flash('Category deleted successfully', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting category: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('admin_categories'))

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

@app.route('/admin/navbar')
def admin_navbar():
    if session.get('user_role') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM navbar_links ORDER BY sort_order")
    links = cursor.fetchall()

    cursor.close()
    conn.close()

    # Get only top-level links for parent dropdown
    parents = [link for link in links if not link['parent_id']]

    return render_template('admin_navbar.html', links=links, parents=parents,active_section='navbar')


@app.route('/admin/navbar/add', methods=['POST'])
def add_navbar_link():
    if session.get('user_role') != 'admin':
        return redirect(url_for('login'))

    title = request.form['title']
    slug = request.form['slug']
    parent_id = request.form.get('parent_id') or None
    sort_order = request.form.get('sort_order') or 0
    is_active = 1 if request.form.get('is_active') == 'on' else 0

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO navbar_links (title, slug, parent_id, sort_order, is_active)
        VALUES (%s, %s, %s, %s, %s)
    """, (title, slug, parent_id, sort_order, is_active))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Navbar link added successfully!', 'success')
    return redirect(url_for('admin_navbar'))


@app.route('/admin/navbar/edit/<int:link_id>', methods=['POST'])
def edit_navbar_link(link_id):
    if session.get('user_role') != 'admin':
        return redirect(url_for('login'))

    title = request.form['title']
    slug = request.form['slug']
    parent_id = request.form.get('parent_id') or None
    sort_order = request.form.get('sort_order') or 0
    is_active = 1 if request.form.get('is_active') == 'on' else 0

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE navbar_links
        SET title=%s, slug=%s, parent_id=%s, sort_order=%s, is_active=%s
        WHERE id=%s
    """, (title, slug, parent_id, sort_order, is_active, link_id))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Navbar link updated successfully!', 'success')
    return redirect(url_for('admin_navbar'))


@app.route('/admin/navbar/delete/<int:link_id>', methods=['POST'])
def delete_navbar_link(link_id):
    if session.get('user_role') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM navbar_links WHERE id=%s", (link_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Navbar link deleted successfully!', 'danger')
    return redirect(url_for('admin_navbar'))



@app.route('/admin')
@role_required('admin')
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get counts for dashboard
    cursor.execute("SELECT COUNT(*) as count FROM products")
    products = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'seller'")
    sellers = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'customer'")
    customers = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM orders")
    orders = cursor.fetchone()['count']
    
    conn.close()
    
    return render_template('admin_dashboard.html',
                         products=products,
                         sellers=sellers,
                         customers=customers,
                         orders=orders,
                         active_section='dashboard')

@app.route('/admin/products')
@role_required('admin')
def admin_products():
    stock_filter = request.args.get('stock')   # in_stock, out_of_stock, low_stock
    status_filter = request.args.get('status') # pending, rejected, approved, or None

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
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
        WHERE 1=1
    """

    # Stock filter
    if stock_filter == "in_stock":
        query += " AND COALESCE(inv.stock_quantity, 0) > 0"
    elif stock_filter == "out_of_stock":
        query += " AND COALESCE(inv.stock_quantity, 0) <= 0"
    elif stock_filter == "low_stock":
        query += " AND COALESCE(inv.stock_quantity, 0) > 0 AND COALESCE(inv.stock_quantity, 0) < 5"

    # Status filter
    if status_filter == "pending":
        query += " AND (pa.status = 'pending' OR p.status = 'pending')"
    elif status_filter == "rejected":
        query += " AND (pa.status = 'rejected' OR p.status = 'rejected')"
    elif status_filter == "approved":
        query += " AND (pa.status = 'approved' OR p.status = 'approved')"

    # Sort: pending → rejected → approved → newest first
    query += """
        ORDER BY 
            CASE 
                WHEN pa.status = 'pending' OR p.status = 'pending' THEN 1
                WHEN pa.status = 'rejected' OR p.status = 'rejected' THEN 2
                ELSE 3
            END,
            p.created_at DESC
    """

    cursor.execute(query)
    products = cursor.fetchall()
    conn.close()

    return render_template('admin_products.html',
                           products=products,
                           active_section='products',
                           stock_filter=stock_filter,
                           status_filter=status_filter)
    



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
    
    return render_template('admin_sellers.html',
                         sellers=sellers,active_section='sellers'
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
    
    return render_template('admin_customers.html',
                         customers=customers,active_section='customers'
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
    
    return render_template('admin_orders.html',
                         orders=orders,active_section='orders'
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


def get_navbar_links():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM navbar_links
        WHERE is_active = TRUE
        ORDER BY sort_order
    """)
    links = cursor.fetchall()
    cursor.close()
    conn.close()
    return links







def build_category_map():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, name, parent_id FROM product_categories WHERE is_active = TRUE")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    category_map = {}
    parent_id_to_slug = {}

    # Step 1: Create slug map for parent categories
    for row in rows:
        if row['parent_id'] is None:
            slug = slugify(row['name'])
            category_map[slug] = []
            parent_id_to_slug[row['id']] = slug

    # Step 2: Assign subcategories
    for row in rows:
        if row['parent_id']:
            parent_slug = parent_id_to_slug.get(row['parent_id'])
            if parent_slug:
                category_map[parent_slug].append(row['name'])

    return category_map
@app.route('/get_category_map')
def get_category_map():
    return jsonify(build_category_map())







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
            (p.price * (1 - p.discount/100)) AS calculated_discounted_price,
            pa.rejection_reason,
            pa.reviewed_at
        FROM products p
        LEFT JOIN inventory i ON p.id = i.product_id
        LEFT JOIN product_approvals pa ON p.id = pa.product_id
        WHERE p.seller_id = %s
        ORDER BY p.created_at DESC
    """, (seller_id,))
    products = cursor.fetchall()
    category_map=build_category_map()

    cursor.execute("""
    SELECT id, name, 
           LOWER(REPLACE(REPLACE(REPLACE(name, ' ', '-'), '&', 'and'), '.', '')) as slug 
    FROM product_categories 
    WHERE parent_id IS NULL AND is_active = 1
""")
    categories = cursor.fetchall()

    cursor.execute("SELECT id, name, parent_id FROM product_categories WHERE parent_id IS NOT NULL AND is_active = 1")
    subcategories = cursor.fetchall()
    
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
                         seller_profile=seller_profile,categories=categories, subcategories=subcategories,category_map=category_map)
    
    

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
        # Validate and parse form data
        price = float(request.form['price'])
        discount = float(request.form.get('discount', 0))
        compare_price = float(request.form['compare_price']) if request.form.get('compare_price') else None
        stock_quantity = int(request.form['stock_quantity'])

        # Handle file upload (image1 - required)
        file1 = request.files['image']
        if not (file1 and allowed_file(file1.filename)):
            flash('Invalid primary image file', 'danger')
            return redirect(url_for('seller_dashboard'))

        filename1 = secure_filename(file1.filename)
        file1.save(os.path.join(app.config['UPLOAD_FOLDER'], filename1))

        # Handle optional second image
        file2 = request.files.get('image2')
        filename2 = None
        if file2 and allowed_file(file2.filename):
            filename2 = secure_filename(file2.filename)
            file2.save(os.path.join(app.config['UPLOAD_FOLDER'], filename2))

        # Product ID generation
        category = request.form['category']
        sub_category = request.form.get('sub_category', '')
        base_name = sub_category if sub_category else category
        base_id = slugify(f"{base_name}-{request.form['title']}")
        product_id = base_id
        suffix = 1

        conn = get_db_connection()
        cursor = conn.cursor()

        # Ensure product_id is unique
        while True:
            cursor.execute("SELECT id FROM products WHERE id = %s", (product_id,))
            if not cursor.fetchone():
                break
            product_id = f"{base_id}-{suffix}"
            suffix += 1

        # Disable foreign key checks
        cursor.execute("SET FOREIGN_KEY_CHECKS=0")

        try:
            # Insert into product_approvals
            cursor.execute("""
                INSERT INTO product_approvals (product_id, status)
                VALUES (%s, 'pending')
            """, (product_id,))

            # Insert into products (added image2 column)
            cursor.execute("""
                INSERT INTO products (
                    id, seller_id, title, price, discount, compare_price,
                    image, image2, description, tags, benefits,
                    category, sub_category, details, ingredients, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
            """, (
                product_id,
                seller_id,
                request.form['title'],
                price,
                discount,
                compare_price,
                filename1,
                filename2,
                request.form['description'],
                request.form.get('tags', ''),
                request.form.get('benefits', ''),
                category,
                sub_category,
                request.form.get('details', ''),
                request.form.get('ingredients', '')
            ))

            # Insert into inventory
            cursor.execute("""
                INSERT INTO inventory (product_id, stock_quantity)
                VALUES (%s, %s)
            """, (product_id, stock_quantity))

            # Re-enable foreign key checks and commit
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
        reason = request.form.get('rejection_reason', '').strip()
        if not reason:
            flash("Rejection reason is required", "danger")
            return redirect(url_for('admin_sellers'))

        conn = get_db_connection()
        cursor = conn.cursor()
        conn.start_transaction()

        # Get seller's email along with the ID
        cursor.execute("SELECT id, email FROM users WHERE id = %s AND role = 'seller'", (seller_id,))
        seller = cursor.fetchone()
        if not seller:
            conn.rollback()
            flash("Seller not found", "danger")
            return redirect(url_for('admin_sellers'))

        seller_id, seller_email = seller

        cursor.execute("""
            UPDATE seller_profiles 
            SET is_approved = FALSE, 
                approval_status = 'rejected',
                rejection_reason = %s,
                approved_by = %s,
                approved_at = NOW()
            WHERE user_id = %s
        """, (reason, session['user_id'], seller_id))

        cursor.execute("UPDATE users SET is_active = FALSE WHERE id = %s", (seller_id,))

        conn.commit()
        
        # Send rejection email
        try:
            send_seller_approval_email(seller_email, approved=False, reason=reason)
        except Exception as email_error:
            # Log the email error but don't fail the whole operation
            app.logger.error(f"Failed to send rejection email: {email_error}")

        flash("Seller rejected successfully", "warning")
        return redirect(url_for('admin_sellers'))

    except mysql.connector.Error as db_err:
        if conn: conn.rollback()
        flash(f"Database error: {db_err}", "danger")
        return redirect(url_for('admin_sellers'))
    except Exception as e:
        if conn: conn.rollback()
        flash(f"Error: {e}", "danger")
        return redirect(url_for('admin_sellers'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()



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
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)  # ✅ Use dictionary cursor for column names
        conn.start_transaction()

        cursor.execute("SELECT id, email FROM users WHERE id = %s AND role = 'seller'", (seller_id,))
        seller = cursor.fetchone()
        if not seller:
            conn.rollback()
            flash("Seller not found", "danger")
            return redirect(url_for('admin_sellers'))

        cursor.execute("""
            UPDATE seller_profiles 
            SET is_approved = TRUE, 
                approval_status = 'approved',
                approved_by = %s,
                approved_at = NOW(),
                rejection_reason = NULL
            WHERE user_id = %s
        """, (session['user_id'], seller_id))

        cursor.execute("UPDATE users SET is_active = TRUE WHERE id = %s", (seller_id,))
        
        # ✅ Now send email with seller's email
        send_seller_approval_email(seller['email'], approved=True, reason=None)

        conn.commit()
        flash("Seller approved successfully", "success")
        return redirect(url_for('admin_sellers'))

    except mysql.connector.Error as db_err:
        if conn: conn.rollback()
        flash(f"Database error: {db_err}", "danger")
        return redirect(url_for('admin_sellers'))
    except Exception as e:
        if conn: conn.rollback()
        flash(f"Error: {e}", "danger")
        return redirect(url_for('admin_sellers'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

            
def user_has_purchased_product(user_id, product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM order_items 
        WHERE product_id = %s AND order_id IN (
            SELECT id FROM orders WHERE user_id = %s
        )
    """, (product_id, user_id))
    result = cursor.fetchone()[0]
    conn.close()
    return result > 0

@app.route('/submit_review/<product_id>', methods=['POST'])
def submit_review(product_id):
    if 'user_id' not in session:
        flash("Please login to submit a review.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    if not user_has_purchased_product(user_id, product_id):
        flash("You must purchase this product to review it.", "danger")
        return redirect(url_for('product', product_id=product_id))

    rating = int(request.form['rating'])
    review = request.form['review'].strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO product_reviews (user_id, product_id, rating, review)
        VALUES (%s, %s, %s, %s)
    """, (user_id, product_id, rating, review))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash("Thank you for your review!", "success")
    return redirect(url_for('product', product_id=product_id))




@app.route('/seller/edit_product/<product_id>', methods=['GET', 'POST'])
@role_required('seller')
def edit_product(product_id):
    seller_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch product with inventory and approval info
        cursor.execute("""
            SELECT p.*, i.stock_quantity, pa.status AS approval_status
            FROM products p
            LEFT JOIN inventory i ON p.id = i.product_id
            LEFT JOIN product_approvals pa ON p.id = pa.product_id
            WHERE p.id = %s AND p.seller_id = %s
        """, (product_id, seller_id))
        product = cursor.fetchone()

        if not product:
            flash("Product not found or unauthorized.", "danger")
            return redirect(url_for('seller_dashboard'))
        if 'image2' not in product:
            product['image2'] = None
        if request.method == 'POST':
            # Read form values
            title = request.form['title']
            price = float(request.form['price'])
            compare_price = float(request.form['compare_price']) if request.form.get('compare_price') else None
            discount = float(request.form.get('discount', 0))
            stock_quantity = int(request.form.get('stock_quantity', 0))
            category = request.form['category']
            sub_category = request.form.get('sub_category', '')
            description = request.form.get('description')
            tags = request.form.get('tags', '').split(',')
            benefits = request.form.get('benefits', '').split(',')
            details = request.form.get('details')
            ingredients = request.form.get('ingredients')

            # Validations
            if price <= 0:
                raise ValueError("Price must be positive.")
            if discount < 0 or discount > 100:
                raise ValueError("Discount must be between 0 and 100.")
            if stock_quantity < 0:
                raise ValueError("Stock quantity cannot be negative.")
            if stock_quantity > 10000:
                raise ValueError("Stock quantity too high.")

            # Handle image1 upload
            image = product.get('image')
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    image = filename

            # Handle image2 upload
            image2 = product.get('image2')
            if 'image2' in request.files:
                file2 = request.files['image2']
                if file2 and allowed_file(file2.filename):
                    filename2 = secure_filename(file2.filename)
                    file2.save(os.path.join(app.config['UPLOAD_FOLDER'], filename2))
                    image2 = filename2

            # Regenerate product_id if needed
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

            if new_product_id != product_id:
                cursor.execute("UPDATE inventory SET product_id = %s WHERE product_id = %s", (new_product_id, product_id))
                cursor.execute("UPDATE product_approvals SET product_id = %s WHERE product_id = %s", (new_product_id, product_id))
                cursor.execute("UPDATE products SET id = %s WHERE id = %s", (new_product_id, product_id))

            # Update product
            cursor.execute("""
                UPDATE products SET
                    title = %s,
                    price = %s,
                    compare_price = %s,
                    discount = %s,
                    image = %s,
                    image2 = %s,
                    tags = %s,
                    description = %s,
                    benefits = %s,
                    category = %s,
                    sub_category = %s,
                    details = %s,
                    ingredients = %s
                WHERE id = %s AND seller_id = %s
            """, (
                title, price, compare_price, discount,
                image, image2,
                ','.join(tags), description, ','.join(benefits),
                category, sub_category, details, ingredients,
                new_product_id, seller_id
            ))

            # Update inventory
            cursor.execute("""
                UPDATE inventory SET stock_quantity = %s
                WHERE product_id = %s
            """, (stock_quantity, new_product_id))

            # Reset approval if stock changed
            if stock_quantity != product['stock_quantity']:
                cursor.execute("""
                    UPDATE product_approvals SET status = 'pending', rejection_reason = NULL
                    WHERE product_id = %s
                """, (new_product_id,))

            conn.commit()

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

            flash("Product updated successfully.", "success")
            return redirect(url_for('seller_dashboard'))

        # Handle GET request — prepare product data for form
        product['tags'] = product['tags'].split(',') if product.get('tags') else []
        product['benefits'] = product['benefits'].split(',') if product.get('benefits') else []

        cursor.execute("""
            SELECT name,
                   LOWER(REPLACE(REPLACE(REPLACE(name, ' ', '-'), '&', 'and'), '.', '')) as slug
            FROM product_categories
            WHERE is_active = TRUE and parent_id IS NULL
        """)
        categories = cursor.fetchall()
        category_map = build_category_map()
        
        return render_template('edit_product.html', product=product, categories=categories, category_map=category_map)

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

@app.route('/buy-now', methods=['POST'])
def buy_now():
    product_id = request.form.get('product_id')
    product = get_product_by_id_from_db(product_id)

    if not product or product.get('stock_quantity', 0) < 1:
        flash("This product is currently out of stock", "danger")
        return redirect(url_for('product', product_id=product_id))

    user_role = session.get('user_role')

    # 🚫 Block sellers and admins
    if user_role in ['seller', 'admin']:
        flash("Only customers can buy products.", "danger")
        return redirect(url_for('home'))

    # ✅ Store this single product in session for checkout
    session['buy_now_product'] = {
        'id': product['id'],
        'title': product['title'],
        'price': float(product['price']),
        'image': product['image'],
        'quantity': 1
    }

    return redirect(url_for('checkout'))






# Route to render checkout page and create Razorpay order
@app.route('/checkout', methods=['GET', 'POST'])
@role_required('customer')
def checkout():
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ✅ Fetch saved addresses
    cursor.execute("SELECT * FROM user_addresses WHERE user_id = %s", (user_id,))
    addresses = cursor.fetchall()

    # ✅ Check if "buy now"
    buy_now_product = session.pop('buy_now_product', None)

    if buy_now_product:
        cart_items = [buy_now_product]
        total_price = buy_now_product['price']
    else:
        cursor.execute("""
            SELECT ci.*, COALESCE(i.stock_quantity, 0) as stock_quantity
            FROM cart_items ci
            LEFT JOIN inventory i ON ci.product_id = i.product_id
            WHERE ci.user_id = %s
        """, (user_id,))
        cart_items = cursor.fetchall()
        total_price = sum(item['price'] * item['quantity'] for item in cart_items)

    conn.close()

    # ✅ Stock check
    out_of_stock = [item for item in cart_items if item['quantity'] > item.get('stock_quantity', 1)]
    if out_of_stock:
        flash("Some items in your cart are out of stock", "danger")
        return redirect(url_for('cart'))

    if request.method == 'POST':
        address_id = request.form.get('address_id')

        # ✅ Case 1: Saved Address
        if address_id:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM user_addresses WHERE id=%s AND user_id=%s", (address_id, user_id))
            selected_address = cursor.fetchone()
            cursor.close()
            conn.close()

            if not selected_address:
                flash("Invalid address selected!", "danger")
                return redirect(url_for('checkout'))

            shipping_info = {
                'full_name': selected_address['name'],
                'address': f"{selected_address['address_line1']} {selected_address['address_line2']}",
                'city': selected_address['city'],
                'state': selected_address['state'],
                'pincode': selected_address['pincode'],
                'phone': selected_address['mobile']
            }

        # ✅ Case 2: New Address
        else:
            shipping_info = {
                'full_name': request.form['full_name'],
                'address': request.form['shipping_address'],
                'city': request.form['city'],
                'state': request.form['state'],
                'pincode': request.form['pincode'],
                'phone': request.form['phone']
            }

            # Save new address (optional: set default)
            conn = get_db_connection()
            cursor = conn.cursor()
            is_default = 1 if request.form.get('is_default') else 0
            if is_default:
                cursor.execute("UPDATE user_addresses SET is_default=0 WHERE user_id=%s", (user_id,))
            cursor.execute("""
                INSERT INTO user_addresses (user_id, name, mobile, address_line1, address_line2, city, state, pincode, country, is_default)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                user_id,
                shipping_info['full_name'],
                shipping_info['phone'],
                request.form['shipping_address'],  # address_line1
                "",  # address_line2 (you can split if needed)
                shipping_info['city'],
                shipping_info['state'],
                shipping_info['pincode'],
                "India",
                is_default
            ))
            conn.commit()
            cursor.close()
            conn.close()

        # ✅ Create Razorpay Order
        order_data = {
            "amount": int(total_price * 100),
            "currency": "INR",
            "payment_capture": 1,
            "notes": {
                "user_id": user_id,
                "items": json.dumps([{"id": item['id'], "quantity": item['quantity']} for item in cart_items])
            }
        }

        try:
            razorpay_order = razorpay_client.order.create(data=order_data)
            session['checkout_info'] = {
                'shipping_info': shipping_info,
                'razorpay_order_id': razorpay_order['id'],
                'total_amount': total_price,
                'cart_items': [{'id': item['id'], 'quantity': item['quantity']} for item in cart_items],
                'is_buy_now': bool(buy_now_product)
            }

            return render_template("checkout.html",
                                   razorpay_order_id=razorpay_order['id'],
                                   total_amount=total_price,
                                   razorpay_key="your_razorpay_key_here",
                                   cart_items=cart_items,
                                   addresses=addresses)
        except Exception as e:
            flash(f"Error creating payment order: {str(e)}", "danger")
            return redirect(url_for('cart'))

    # ✅ GET
    return render_template("checkout.html",
                           cart_items=cart_items,
                           total_price=total_price,
                           addresses=addresses)


    
    
    
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
    """Handle successful payment confirmation and create order"""
    # Validate session
    if 'user_id' not in session or 'checkout_info' not in session:
        return jsonify({'status': 'error', 'message': 'Invalid session'}), 400
    checkout_info = session['checkout_info']
    is_buy_now = checkout_info.get('is_buy_now', False)    
    # Verify payment signature
    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': request.json['razorpay_order_id'],
            'razorpay_payment_id': request.json['razorpay_payment_id'],
            'razorpay_signature': request.json['razorpay_signature']
        })
    except Exception as e:
        app.logger.error(f"Payment verification failed: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Invalid payment signature'}), 400
    
    user_id = session['user_id']
    checkout_info = session['checkout_info']
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Begin transaction
        conn.start_transaction()
        
        # 1. Create order record
        cursor.execute("""
            INSERT INTO orders (
                user_id, total_amount, payment_method, status,
                shipping_address, shipping_city, shipping_state,
                shipping_pincode, shipping_phone, customer_name,
                razorpay_order_id, razorpay_payment_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            request.json['razorpay_order_id'],
            request.json['razorpay_payment_id']
        ))
        order_id = cursor.lastrowid
        
        # 2. Process each item in cart
        for item in checkout_info['cart_items']:
            # Verify product exists and get details
            cursor.execute("""
                SELECT id, seller_id, price, title 
                FROM products 
                WHERE id = %s AND status = 'approved'
                FOR UPDATE  -- Lock row for inventory update
            """, (item['id'],))
            product = cursor.fetchone()
            
            if not product:
                conn.rollback()
                app.logger.error(f"Product {item['id']} not found or not approved")
                return jsonify({
                    'status': 'error',
                    'message': f'Product "{item.get("title", item["id"])}" is no longer available'
                }), 400
            
            # Verify sufficient stock
            cursor.execute("""
                SELECT stock_quantity 
                FROM inventory 
                WHERE product_id = %s
                FOR UPDATE  -- Lock row for inventory update
            """, (item['id'],))
            stock = cursor.fetchone()
            
            if not stock or stock['stock_quantity'] < item['quantity']:
                conn.rollback()
                app.logger.warning(
                    f"Insufficient stock for {product['title']}. "
                    f"Requested: {item['quantity']}, Available: {stock['stock_quantity'] if stock else 0}"
                )
                return jsonify({
                    'status': 'error',
                    'message': f'Not enough stock for "{product["title"]}"'
                }), 400
            
            # Create order item
            cursor.execute("""
                INSERT INTO order_items (
                    order_id, product_id, seller_id, 
                    quantity, price
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                order_id,
                product['id'],
                product['seller_id'],
                item['quantity'],
                product['price']
            ))
            
            # Update inventory
            cursor.execute("""
                UPDATE inventory 
                SET stock_quantity = stock_quantity - %s 
                WHERE product_id = %s
            """, (item['quantity'], product['id']))
            
            # Update sales count
            cursor.execute("""
                UPDATE products 
                SET sold_quantity = sold_quantity + %s 
                WHERE id = %s
            """, (item['quantity'], product['id']))
        
        # 3. Clear cart after successful order
        if not is_buy_now:
            cursor.execute("DELETE FROM cart_items WHERE user_id = %s", (user_id,))
        
        # Commit transaction
        conn.commit()
        
        # Send notifications (outside transaction)
        try:
            send_order_confirmation_email(user_id, order_id)
            send_payment_received_notification(order_id)
        except Exception as e:
            app.logger.error(f"Notification failed: {str(e)}")
        
        # Clear checkout session
        session.pop('checkout_info', None)
        
        return jsonify({
            'status': 'success',
            'order_id': order_id,
            'message': 'Order placed successfully'
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        app.logger.error(f"Order processing failed: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Failed to process order. Please contact support.'
        }), 500
        
    finally:
        if cursor:
            cursor.close()
        if conn:
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
    
    # Get all orders with their items
    cursor.execute("""
        SELECT 
            o.id, 
            o.status, 
            o.total_amount, 
            o.order_date, 
            o.shipping_address,
            o.shipping_city,
            o.shipping_state,
            o.shipping_pincode,
            o.tracking_number,
            o.shipped_at,
            GROUP_CONCAT(p.title SEPARATOR ', ') AS items
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        WHERE o.user_id = %s
        GROUP BY o.id
        ORDER BY o.order_date DESC
    """, (user_id,))
    orders = cursor.fetchall()
    
    conn.close()

    return render_template("my_orders.html", orders=orders)

@app.route('/order-delivered/<int:order_id>', methods=['POST'])
def mark_order_delivered(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify this order belongs to the user
        cursor.execute("SELECT 1 FROM orders WHERE id = %s AND user_id = %s", (order_id, user_id))
        if not cursor.fetchone():
            flash("Order not found or not authorized", "danger")
            return redirect(url_for('my_orders'))
        
        # Update status to delivered
        cursor.execute("""
            UPDATE orders 
            SET status = 'delivered', 
                delivered_at = NOW() 
            WHERE id = %s AND user_id = %s
        """, (order_id, user_id))
        
        conn.commit()
        flash("Order marked as delivered", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error updating order status: {str(e)}", "danger")
    finally:
        conn.close()
    
    return redirect(url_for('my_orders'))


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



@app.context_processor
def inject_navbar():
    return {'navbar_links':get_navbar_links()}

@app.context_processor
def inject_cart_length():
    """Make cart_length available in all templates (like base.html)."""
    return dict(cart_length=get_cart_length())





if __name__ == '__main__':
    init_db()
    cleanup_duplicate_categories()
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
    app.run(host='0.0.0.0',port=5001,debug=True)
