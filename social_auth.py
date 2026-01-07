from flask import redirect, url_for, session
from authlib.integrations.flask_client import OAuth

oauth = OAuth()


def init_social_auth(app):
    oauth.init_app(app)

    # Google
    oauth.register(
        name='google',
        client_id='GOOGLE_CLIENT_ID',
        client_secret='GOOGLE_CLIENT_SECRET',
        authorize_url='https://accounts.google.com/o/oauth2/auth',
        access_token_url='https://oauth2.googleapis.com/token',
        api_base_url='https://www.googleapis.com/oauth2/v1/',
        client_kwargs={'scope': 'openid email profile'},
        authorize_params={'prompt': 'select_account'}
    )

    # Facebook
    oauth.register(
        name='facebook',
        client_id='FACEBOOK_APP_ID',
        client_secret='FACEBOOK_APP_SECRET',
        authorize_url='https://www.facebook.com/dialog/oauth',
        access_token_url='https://graph.facebook.com/oauth/access_token',
        api_base_url='https://graph.facebook.com/',
        client_kwargs={'scope': 'email'}
    )


def register_social_routes(app, get_db_connection):

    @app.route('/login/google')
    def login_google():
        return oauth.google.authorize_redirect(
            url_for('google_callback', _external=True)
        )

    @app.route('/login/google/callback')
    def google_callback():
        token = oauth.google.authorize_access_token()
        user = oauth.google.get('userinfo').json()

        email = user['email']
        name = user['name']
        oauth_id = user['id']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        db_user = cursor.fetchone()

        # ❌ block seller/admin
        if db_user and db_user['role'] in ['seller', 'admin']:
            cursor.close()
            conn.close()
            return redirect(url_for('login', error='Social login not allowed'))

        if not db_user:
            cursor.execute("""
                INSERT INTO users (name, email, oauth_id, auth_provider, role)
                VALUES (%s,%s,%s,'google','customer')
            """, (name, email, oauth_id))
            conn.commit()
            user_id = cursor.lastrowid
        else:
            user_id = db_user['id']

        # 🔥 merge guest cart (same logic as normal login)
        temp_cart = session.pop('cart', [])
        if temp_cart:
            cart_cursor = conn.cursor()
            for item in temp_cart:
                price = float(item['price'])
                cart_cursor.execute(
                    "SELECT quantity FROM cart_items WHERE user_id=%s AND product_id=%s",
                    (user_id, item['id'])
                )
                row = cart_cursor.fetchone()
                if row:
                    cart_cursor.execute(
                        "UPDATE cart_items SET quantity=%s WHERE user_id=%s AND product_id=%s",
                        (row[0] + item['quantity'], user_id, item['id'])
                    )
                else:
                    cart_cursor.execute("""
                        INSERT INTO cart_items
                        (user_id, product_id, title, price, image, quantity)
                        VALUES (%s,%s,%s,%s,%s,%s)
                    """, (user_id, item['id'], item['title'], price, item['image'], item['quantity']))
            conn.commit()

        cursor.close()
        conn.close()

        session['user_id'] = user_id
        session['user_role'] = 'customer'
        return redirect(url_for('home'))


    @app.route('/login/facebook')
    def login_facebook():
        return oauth.facebook.authorize_redirect(
            url_for('facebook_callback', _external=True)
        )

    @app.route('/login/facebook/callback')
    def facebook_callback():
        token = oauth.facebook.authorize_access_token()
        user = oauth.facebook.get('me?fields=id,name,email').json()

        email = user.get('email')
        name = user.get('name')
        oauth_id = user.get('id')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        db_user = cursor.fetchone()

        # ❌ block seller/admin
        if db_user and db_user['role'] in ['seller', 'admin']:
            cursor.close()
            conn.close()
            return redirect(url_for('login', error='Social login not allowed'))

        if not db_user:
            cursor.execute("""
                INSERT INTO users (name, email, oauth_id, auth_provider, role)
                VALUES (%s,%s,%s,'facebook','customer')
            """, (name, email, oauth_id))
            conn.commit()
            user_id = cursor.lastrowid
        else:
            user_id = db_user['id']

        # 🔥 merge guest cart
        temp_cart = session.pop('cart', [])
        if temp_cart:
            cart_cursor = conn.cursor()
            for item in temp_cart:
                price = float(item['price'])
                cart_cursor.execute(
                    "SELECT quantity FROM cart_items WHERE user_id=%s AND product_id=%s",
                    (user_id, item['id'])
                )
                row = cart_cursor.fetchone()
                if row:
                    cart_cursor.execute(
                        "UPDATE cart_items SET quantity=%s WHERE user_id=%s AND product_id=%s",
                        (row[0] + item['quantity'], user_id, item['id'])
                    )
                else:
                    cart_cursor.execute("""
                        INSERT INTO cart_items
                        (user_id, product_id, title, price, image, quantity)
                        VALUES (%s,%s,%s,%s,%s,%s)
                    """, (user_id, item['id'], item['title'], price, item['image'], item['quantity']))
            conn.commit()

        cursor.close()
        conn.close()

        session['user_id'] = user_id
        session['user_role'] = 'customer'
        return redirect(url_for('home'))
