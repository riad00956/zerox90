import os, json, sqlite3, subprocess, secrets
from pathlib import Path
from flask import Flask, render_template, request, session, redirect, flash, url_for
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# ফাইল পাথ কনফিগারেশন
PROJECT_DIR = Path('projects')
PROJECT_DIR.mkdir(exist_ok=True)
USER_DATA = 'users.json'
SETTINGS_FILE = 'settings.json'
DB_NAME = 'packages.db'

# ২. ইনিশিয়ালাইজেশন লজিক
def init_system():
    # SQL DB তৈরি
    conn = sqlite3.connect(DB_NAME)
    conn.execute('CREATE TABLE IF NOT EXISTS libs (id INTEGER PRIMARY KEY, name TEXT UNIQUE)')
    conn.commit()
    conn.close()

    # ইউজার ফাইল চেক
    if not os.path.exists(USER_DATA):
        with open(USER_DATA, 'w') as f: json.dump({}, f)

    # গ্লোবাল সেটিংস (অ্যাক্সেস কি) চেক
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'w') as f:
            json.dump({"access_key": "cyber123", "admin_pass": "admin"}, f)

init_system()

# ৩. হেল্পার ফাংশনস
def get_settings():
    with open(SETTINGS_FILE, 'r') as f: return json.load(f)

def save_settings(data):
    with open(SETTINGS_FILE, 'w') as f: json.dump(data, f)

def get_users():
    with open(USER_DATA, 'r') as f: return json.load(f)

# ৪. রাউটস (Routes)
@app.route('/')
def home():
    if 'user' in session: return render_template('index.html')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        acc_key = request.form.get('access_key')
        
        settings = get_settings()
        if acc_key != settings['access_key']:
            flash('Invalid Access Key!')
            return redirect(url_for('login'))

        users = get_users()
        if username in users and check_password_hash(users[username], password):
            session['user'] = username
            return redirect(url_for('home'))
        flash('Invalid Username or Password!')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users = get_users()
        if username in users:
            flash('Username already exists!')
        else:
            users[username] = generate_password_hash(password)
            with open(USER_DATA, 'w') as f: json.dump(users, f)
            flash('Registration Successful!')
            return redirect(url_for('login'))
    return render_template('register.html')

# ৫. অ্যাডমিন প্যানেল
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    settings = get_settings()
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        if user == 'admin' and pw == settings['admin_pass']:
            session['admin'] = True
            return render_template('admin.html', settings=settings)
        flash('Admin Access Denied!')
    
    if session.get('admin'):
        return render_template('admin.html', settings=settings)
    return render_template('admin_login.html') # আলাদা অ্যাডমিন লগইন পেজ

@app.route('/admin/update_key', methods=['POST'])
def update_key():
    if not session.get('admin'): return redirect('/admin')
    new_key = request.form.get('new_key')
    settings = get_settings()
    settings['access_key'] = new_key
    save_settings(settings)
    flash('Access Key Updated!')
    return redirect('/admin')

# ৬. সকেট ইঞ্জিন (কোড রান ও টার্মিনাল)
@socketio.on('run_code')
def run_code(data):
    name = secure_filename(data['filename'])
    def run_proc():
        proc = subprocess.Popen(['python', str(PROJECT_DIR / name)], 
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout: socketio.emit('output', {'data': line.strip()})
    socketio.start_background_task(run_proc)

@socketio.on('terminal_cmd')
def handle_terminal(data):
    cmd = data['command'].strip()
    def execute_cmd():
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout: socketio.emit('output', {'data': line.strip()})
        proc.wait()
        # SQL এ লাইব্রেরি ট্র্যাকিং
        if cmd.startswith('pip install') and proc.returncode == 0:
            parts = cmd.split()
            if len(parts) >= 3:
                conn = sqlite3.connect(DB_NAME)
                conn.execute('INSERT OR IGNORE INTO libs (name) VALUES (?)', (parts[2],))
                conn.commit()
                conn.close()
    socketio.start_background_task(execute_cmd)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8080)
