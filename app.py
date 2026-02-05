import os, json, sqlite3, subprocess, secrets
from pathlib import Path
from flask import Flask, render_template, request, session, redirect, flash, url_for
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder='UI') # আপনার চাহিদা অনুযায়ী UI ফোল্ডার
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# পাথ সেটিংস
USER_DATA = 'users.json'
SETTINGS_FILE = 'settings.json'

def init_db():
    if not os.path.exists(USER_DATA):
        with open(USER_DATA, 'w') as f: json.dump({}, f)
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'w') as f:
            json.dump({"access_key": "cyber123", "admin_pass": "admin", "admin_user": "admin"}, f)

init_db()

# হেল্পার ফাংশন
def get_settings():
    with open(SETTINGS_FILE, 'r') as f: return json.load(f)

# --- রাউটস ---

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

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    settings = get_settings()
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        if u == settings['admin_user'] and p == settings['admin_pass']:
            session['admin'] = True
            return render_template('admin.html', settings=settings)
        flash("Admin Access Denied!")
    
    if session.get('admin'):
        return render_template('admin.html', settings=settings)
    return render_template('login.html') # অথবা আলাদা admin_login.html

@app.route('/admin/update_key', methods=['POST'])
def update_key():
    if not session.get('admin'): return redirect('/')
    new_key = request.form.get('new_key')
    settings = get_settings()
    settings['access_key'] = new_key
    with open(SETTINGS_FILE, 'w') as f: json.dump(settings, f)
    flash("Access Key Updated Successfully!")
    return redirect('/admin')

@app.route('/myliber')
def myliber():
    if 'user' not in session: return redirect('/login')
    return render_template('myliber.html')

@app.route('/profi')
def profi():
    if 'user' not in session: return redirect('/login')
    return render_template('profi.html')

@app.route('/change')
def change():
    if 'user' not in session: return redirect('/login')
    return render_template('change.html')

@app.route('/addata')
def addata():
    if not session.get('admin'): return redirect('/')
    with open(USER_DATA, 'r') as f: users = json.load(f)
    return render_template('addata.html', users=users)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# --- সকেট ইঞ্জিন (কোড রান করার জন্য) ---
@socketio.on('terminal_cmd')
def handle_terminal(data):
    cmd = data['command']
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        emit('output', {'data': line})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
