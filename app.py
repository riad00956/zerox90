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

# রেন্ডারের জন্য async_mode='eventlet' বা 'threading' ব্যবহার করা হয়
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DB_FILE = 'cyber_data.db'
USER_DATA = 'users.json'
SETTINGS_FILE = 'settings.json'

# --- ডাটাবেজ সেটআপ ---
def init_db():
    if not os.path.exists(USER_DATA):
        with open(USER_DATA, 'w') as f: json.dump({}, f)
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'w') as f:
            json.dump({"access_key": "cyber123", "bot_token": ""}, f)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS libraries (id INTEGER PRIMARY KEY, name TEXT UNIQUE)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY, filename TEXT, content TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- নতুন ইভেন্ট হ্যান্ডলার (যা আপনার আগের কোডে ছিল না) ---

@socketio.on('save_file')
def handle_save_file(data):
    filename = data.get('filename')
    content = data.get('content')
    if filename and content:
        with open(filename, 'w') as f:
            f.write(content)
        # SQL ডাটাবেজেও ব্যাকআপ রাখা
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO files (filename, content) VALUES (?, ?)", (filename, content))
        conn.commit()
        conn.close()
        emit('terminal_output', {'output': f'[SYSTEM] {filename} saved successfully.'})

@socketio.on('run_code')
def handle_run_code(data):
    filename = data.get('filename')
    if not filename or not os.path.exists(filename):
        emit('terminal_output', {'output': '[ERROR] File not found!'})
        return

    def execute():
        try:
            # পাইথন ফাইল রান করা
            process = subprocess.Popen(['python', filename], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in iter(process.stdout.readline, ''):
                socketio.emit('terminal_output', {'output': line})
            process.wait()
        except Exception as e:
            socketio.emit('terminal_output', {'output': f'[EXEC ERROR] {str(e)}'})

    threading.Thread(target=execute).start()

@socketio.on('terminal_command')
def handle_command(data):
    command = data.get('command')
    if not command: return

    def run_cmd():
        try:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in iter(process.stdout.readline, ''):
                socketio.emit('terminal_output', {'output': line})
            
            return_code = process.wait()
            if "pip install" in command and return_code == 0:
                lib_name = command.split("install")[-1].strip()
                conn = sqlite3.connect(DB_FILE)
                conn.execute("INSERT OR IGNORE INTO libraries (name) VALUES (?)", (lib_name,))
                conn.commit()
                conn.close()
                socketio.emit('terminal_output', {'output': f'\n[SQL] {lib_name} saved to DB. ✅'})
        except Exception as e:
            socketio.emit('terminal_output', {'output': str(e)})

    threading.Thread(target=run_cmd).start()

# --- Routes ---
@app.route('/')
def index():
    if 'user' not in session: return redirect('/login')
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        key = request.form.get('access_key')
        
        with open(SETTINGS_FILE, 'r') as f: settings = json.load(f)
        if key != settings['access_key']:
            flash("Invalid Key!")
            return redirect('/login')
            
        with open(USER_DATA, 'r') as f: users = json.load(f)
        if user in users and check_password_hash(users[user], pw):
            session['user'] = user
            return redirect('/')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        with open(USER_DATA, 'r') as f: users = json.load(f)
        users[user] = generate_password_hash(pw)
        with open(USER_DATA, 'w') as f: json.dump(users, f)
        return redirect('/login')
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

def run_my_bot():
    try:
        with open(SETTINGS_FILE, 'r') as f: settings = json.load(f)
        token = settings.get('bot_token')
        if token:
            bot = telebot.TeleBot(token)
            @bot.message_handler(commands=['start'])
            def welcome(m): bot.reply_to(m, "Cyber Engine Active!")
            bot.infinity_polling()
    except: pass

if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_my_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.environ.get('PORT', 5003))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
