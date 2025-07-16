import os
import json
import logging
import sqlite3
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import schedule
import threading
from flask import Flask, jsonify, request
from dotenv import load_dotenv
print("App is running")

# here i Load environment variables.
load_dotenv()

# and this is flask app setup
app = Flask(__name__)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("price_tracker.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PriceTracker")

# this is Database setup
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('price_tracker.db', check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS products (
                            id INTEGER PRIMARY KEY,
                            url TEXT NOT NULL UNIQUE,
                            name TEXT,
                            current_price REAL,
                            target_price REAL,
                            last_checked TIMESTAMP,
                            price_history TEXT DEFAULT '[]'
                        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY,
                            email TEXT UNIQUE NOT NULL,
                            phone TEXT,
                            alert_preference TEXT DEFAULT 'email'
                        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS trackings (
                            user_id INTEGER,
                            product_id INTEGER,
                            custom_target_price REAL,
                            FOREIGN KEY(user_id) REFERENCES users(id),
                            FOREIGN KEY(product_id) REFERENCES products(id)
                        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS price_history (
                            product_id INTEGER,
                            price REAL,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY(product_id) REFERENCES products(id)
                        )''')
        self.conn.commit()

    def execute(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()
        return cursor

    def fetch(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

# Initialize our db
db = Database()

# Scraper Class(design to encapsulate logic)
class Scraper:
    @staticmethod
    def get_price(url):
        try:
            headers = {'User-Agent': "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            price_element = soup.select_one('span.a-offscreen')
            if price_element:
                return float(price_element.text.replace('₹', '').replace(',', '').strip())
        except Exception as e:
            logger.error(f"Scraper error for {url}: {str(e)}")
        return None

# Price Tracker Logic
class PriceTracker:
    @staticmethod
    def update_price_history(product_id, price):
        db.execute("INSERT INTO price_history (product_id, price) VALUES (?, ?)", (product_id, price))
        history = db.fetch("SELECT price_history FROM products WHERE id = ?", (product_id,))[0][0]
        history = json.loads(history) if history else []
        history.append({'price': price, 'timestamp': datetime.now().isoformat()})
        if len(history) > 30:
            history = history[-30:]
        db.execute("UPDATE products SET price_history = ? WHERE id = ?", (json.dumps(history), product_id))

    @staticmethod
    def track_products():
        logger.info("Starting product tracking cycle...")
        products = db.fetch("""
            SELECT p.id, p.url, p.name, p.current_price, t.custom_target_price, u.email, u.alert_preference
            FROM products p
            JOIN trackings t ON p.id = t.product_id
            JOIN users u ON t.user_id = u.id
        """)
        for (product_id, url, name, current_price, target_price, email, alert_pref) in products:
            last_checked = db.fetch("SELECT last_checked FROM products WHERE id = ?", (product_id,))[0][0]
            if last_checked:
                try:
                    last_dt = datetime.strptime(last_checked, "%Y-%m-%d %H:%M:%S")
                    if (datetime.now() - last_dt).seconds < 600:
                        continue
                except Exception:
                    pass
            new_price = Scraper.get_price(url)
            if new_price is None:
                continue
            db.execute("UPDATE products SET current_price = ?, last_checked = CURRENT_TIMESTAMP WHERE id = ?",
                       (new_price, product_id))
            PriceTracker.update_price_history(product_id, new_price)
            if new_price <= target_price:
                logger.info(f"[ALERT] {name} dropped to ₹{new_price} (Target: ₹{target_price})")

        logger.info("Tracking cycle completed.")

# Scheduler( checked all tracked product)
def run_scheduler():
    PriceTracker.track_products()  
    schedule.every(30).minutes.do(PriceTracker.track_products)
    while True:
        schedule.run_pending()
        time.sleep(60)

# API Endpoints(which we do in postman)
@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.json
    email = data.get('email')
    alert_preference = data.get('alert_preference', 'email')
    if not email:
        return jsonify({"error": "Email required"}), 400
    try:
        db.execute("INSERT INTO users (email, alert_preference) VALUES (?, ?)", (email, alert_preference))
        user_id = db.fetch("SELECT last_insert_rowid()")[0][0]
        return jsonify({"success": True, "user_id": user_id})
    except:
        return jsonify({"error": "User already exists"}), 400

@app.route('/api/products', methods=['POST'])
def add_product():
    data = request.json
    url = data.get('url')
    target_price = data.get('target_price')
    user_id = data.get('user_id')
    if not url or not target_price or not user_id:
        return jsonify({"error": "Missing parameters"}), 400
    existing = db.fetch("SELECT id FROM products WHERE url = ?", (url,))
    if existing:
        product_id = existing[0][0]
    else:
        name = url.split('/')[-1]
        db.execute("INSERT INTO products (url, name, target_price) VALUES (?, ?, ?)", (url, name, target_price))
        product_id = db.fetch("SELECT last_insert_rowid()")[0][0]
    try:
        db.execute("INSERT INTO trackings (user_id, product_id, custom_target_price) VALUES (?, ?, ?)",
                   (user_id, product_id, target_price))
        return jsonify({"success": True, "product_id": product_id})
    except:
        return jsonify({"error": "Tracking already exists"}), 400

@app.route('/')
def home():
    return '''
    <h2 style="font-family: Arial; color: green;">
         Product Price Tracker API is Running!
    
    '''

if __name__ == "__main__":
    print(" Starting scheduler thread...")
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    print(" Starting Flask server...")
    app.run(host='0.0.0.0', port=5000, debug=True)