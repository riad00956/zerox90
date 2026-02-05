import os
import json
import secrets
from flask import Flask, render_template, request, session, redirect, flash
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash

# ফ্লাস্ক অটোমেটিক 'templates' ফোল্ডার চিনে নেবে
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)

# লোকাল এবং সার্ভার দুই জায়গার জন্যই স্টেবল সেটিংস
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ডাটা ফাইল পাথ (এটি মেইন ডিরেক্টরিতেই থাকবে)
USER_DATA = 'users.json'
SETTINGS_FILE = 'settings.json'

def init_db():
    if not os.path.exists(USER_DATA):
        with open(USER_DATA, 'w') as f: json.dump({}, f)
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'w') as f:
            json.dump({"access_key": "cyber123", "admin_pass": "admin", "admin_user": "admin"}, f)

init_db()

def get_settings():
    with open(SETTINGS_FILE, 'r') as f: return json.load(f)

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        key = request.form.get('access_key')
        
        settings = get_settings()
        if key != settings['access_key']:
            flash("Invalid Access Key!")
            return redirect('/login')
            
        with open(USER_DATA, 'r') as f: users = json.load(f)
        if user in users and check_password_hash(users[user], pw):
            session['user'] = user
            return redirect('/')
        flash("Invalid Credentials!")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        with open(USER_DATA, 'r') as f: users = json.load(f)
        if user in users:
            flash("User already exists!")
        else:
            users[user] = generate_password_hash(pw)
            with open(USER_DATA, 'w') as f: json.dump(users, f)
            return redirect('/login')
    return render_template('register.html')

# --- Admin & Other Routes ---
@app.route('/admin')
def admin():
    if not session.get('admin'): return redirect('/login')
    return render_template('admin.html', settings=get_settings())

@app.route('/profi')
def profi():
    if 'user' not in session: return redirect('/login')
    return render_template('profi.html')

@app.route('/myliber')
def myliber():
    if 'user' not in session: return redirect('/login')
    return render_template('myliber.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    # এটি লোকাল হোস্টে রান করলে ৫০০৩ পোর্ট ব্যবহার করবে (অথবা আপনার পছন্দমতো)
    # আর রেন্ডারে দিলে তাদের নিজস্ব পোর্ট ব্যবহার করবে
    port = int(os.environ.get('PORT', 5003)) 
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
