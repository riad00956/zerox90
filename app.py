import os
import json
import secrets
from flask import Flask, render_template, request, session, redirect, flash
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder='UI')
app.config['SECRET_KEY'] = secrets.token_hex(16)

# Render-এ SocketIO এর জন্য 'threading' মোড বেশি স্টেবল
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ডাটা ফাইল পাথ (Render Disk না থাকলে সাময়িকভাবে কাজ করবে)
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

# অন্য সব রাউট আগের মতোই থাকবে...
# [বাকি রাউটগুলো এখানে যুক্ত করে নিন]

if __name__ == '__main__':
    # Render-এর পোর্টের জন্য ডাইনামিক কনফিগারেশন
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)
