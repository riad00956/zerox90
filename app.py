import os
import json
import secrets
import subprocess
import threading
import sqlite3
import telebot
from flask import Flask, render_template, request, session, redirect, flash
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DB_FILE = 'cyber_data.db'
USER_DATA = 'users.json'
SETTINGS_FILE = 'settings.json'

# --- SQL ডাটাবেজ সেটআপ ---
def init_sql_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # লাইব্রেরি টেবিল
    cursor.execute('''CREATE TABLE IF NOT EXISTS libraries (id INTEGER PRIMARY KEY, name TEXT UNIQUE)''')
    # ফাইল টেবিল (আপলোড করা স্ক্রিপ্ট বা ফাইল সেভ রাখার জন্য)
    cursor.execute('''CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY, filename TEXT, content TEXT)''')
    conn.commit()
    conn.close()

def init_db():
    if not os.path.exists(USER_DATA):
        with open(USER_DATA, 'w') as f: json.dump({}, f)
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'w') as f:
            json.dump({"access_key": "cyber123", "admin_pass": "admin", "admin_user": "admin", "bot_token": "YOUR_TOKEN"}, f)
    init_sql_db()

init_db()

# --- লাইব্রেরি ডাটাবেজে সেভ করার ফাংশন ---
def save_lib_to_db(lib_name):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO libraries (name) VALUES (?)", (lib_name,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

# --- টার্মিনাল লজিক (Pip Install + SQL Save) ---
@socketio.on('terminal_command')
def handle_command(data):
    command = data.get('command')
    if not command: return

    try:
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        
        for line in iter(process.stdout.readline, ''):
            emit('terminal_output', {'output': line})
        
        process.stdout.close()
        return_code = process.wait()

        if "pip install" in command and return_code == 0:
            # কমান্ড থেকে লাইব্রেরির নাম আলাদা করা (উদা: pip install telebot -> telebot)
            lib_name = command.split("install")[-1].strip()
            save_lib_to_db(lib_name)
            emit('terminal_output', {'output': f'\n[SQL] {lib_name} saved to database. ✅\n'})
            emit('terminal_output', {'output': '\n[SYSTEM] Installation Complete! ✅\n'})

    except Exception as e:
        emit('terminal_output', {'output': f'Error: {str(e)}'})

# --- ফাইল আপলোড ও ডাটাবেজে সেভ ---
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files: return "No file"
    file = request.files['file']
    if file.filename == '': return "No filename"
    
    content = file.read().decode('utf-8')
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO files (filename, content) VALUES (?, ?)", (file.filename, content))
    conn.commit()
    conn.close()
    return f"File {file.filename} saved to SQL DB!"

# --- টেলিগ্রাম বট থ্রেড ---
def run_my_bot():
    try:
        with open(SETTINGS_FILE, 'r') as f: settings = json.load(f)
        bot = telebot.TeleBot(settings.get('bot_token', 'YOUR_BOT_TOKEN_HERE'))
        @bot.message_handler(commands=['start'])
        def welcome(m): bot.reply_to(m, "Cyber Engine SQL Bot Active!")
        bot.infinity_polling()
    except: pass

# --- Routes ---
@app.route('/')
def index():
    if 'user' not in session: return redirect('/login')
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user, pw, key = request.form.get('username'), request.form.get('password'), request.form.get('access_key')
        with open(SETTINGS_FILE, 'r') as f: settings = json.load(f)
        if key != settings['access_key']: return redirect('/login')
        with open(USER_DATA, 'r') as f: users = json.load(f)
        if user in users and check_password_hash(users[user], pw):
            session['user'] = user
            return redirect('/')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user, pw = request.form.get('username'), request.form.get('password')
        with open(USER_DATA, 'r') as f: users = json.load(f)
        users[user] = generate_password_hash(pw)
        with open(USER_DATA, 'w') as f: json.dump(users, f)
        return redirect('/login')
    return render_template('register.html')

if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_my_bot); bot_thread.daemon = True; bot_thread.start()
    port = int(os.environ.get('PORT', 5003))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
