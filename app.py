import os
import secrets
import subprocess
import sqlite3
import threading
from pathlib import Path
from flask import Flask, render_template_string, request, session, redirect, flash
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

# ১. কনফিগারেশন
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    PASSWORD = os.environ.get('PASSWORD', 'admin123')
    PROJECT_DIR = 'projects'
    DB_NAME = 'packages.db'
    PORT = int(os.environ.get('PORT', 8080))

app = Flask(__name__)
app.config.from_object(Config)
# রেলওয়ের জন্য eventlet মোড
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

project_path = Path(Config.PROJECT_DIR)
project_path.mkdir(exist_ok=True)

# ২. ডেটাবেজ লজিক
def init_db():
    conn = sqlite3.connect(Config.DB_NAME)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS libs (id INTEGER PRIMARY KEY, name TEXT UNIQUE)')
    conn.commit()
    conn.close()

def save_lib_to_db(lib_name):
    conn = sqlite3.connect(Config.DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO libs (name) VALUES (?)', (lib_name,))
    conn.commit()
    conn.close()

def restore_libs():
    conn = sqlite3.connect(Config.DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM libs')
    libs = cursor.fetchall()
    conn.close()
    for lib in libs:
        print(f"Restoring library: {lib[0]}")
        subprocess.run(['pip', 'install', lib[0]])

init_db()
restore_libs()

# ৩. ফ্রন্টএন্ড UI (টার্মিনাল সহ)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>CyberIDE Pro Max</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.0/socket.io.min.js"></script>
    <style>
        :root { --bg: #0f172a; --card: #1e293b; --text: #f1f5f9; --primary: #3b82f6; --success: #10b981; --danger: #ef4444; }
        body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; }
        .card { background: var(--card); border-radius: 12px; padding: 20px; border: 1px solid #334155; margin-bottom: 15px; }
        textarea { width: 100%; height: 250px; background: #010409; color: #00ff00; border: 1px solid #475569; border-radius: 8px; font-family: monospace; padding: 10px; box-sizing: border-box; }
        .terminal-box { background: #000; color: #00ff00; padding: 15px; height: 180px; overflow-y: auto; border-radius: 8px 8px 0 0; font-family: monospace; border: 1px solid #334155; }
        .terminal-input-area { display: flex; background: #000; border: 1px solid #334155; border-top: none; border-radius: 0 0 8px 8px; padding: 5px; }
        .terminal-input-area span { color: #3b82f6; padding: 5px; font-family: monospace; }
        .terminal-input { flex: 1; background: transparent; border: none; color: #fff; outline: none; font-family: monospace; padding: 5px; }
        .btn { padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer; color: white; background: var(--primary); font-weight: bold; }
    </style>
</head>
<body>
    {% if not session.logged_in %}
    <div style="max-width: 400px; margin: 100px auto;" class="card">
        <form method="POST"><h2>CyberIDE Login</h2><input type="password" name="password" style="width:100%; padding:10px; border-radius:8px;"><br><br><button class="btn" style="width:100%">Unlock</button></form>
    </div>
    {% else %}
    <div style="max-width: 1000px; margin: 0 auto;">
        <div class="card">
            <h3 style="margin-top:0;">Editor: <input type="text" id="filename" value="main.py" style="background:transparent; border:1px solid #475569; color:white; padding:5px; border-radius:5px;"></h3>
            <textarea id="code-editor"></textarea>
            <div style="margin-top:10px; display:flex; gap:10px;">
                <button class="btn" onclick="saveFile()">Save</button>
                <button class="btn" style="background:var(--success)" onclick="runCode()">Run Code</button>
            </div>
        </div>

        <div class="card">
            <h3 style="margin-top:0;">Interactive Terminal</h3>
            <div id="terminal" class="terminal-box"></div>
            <div class="terminal-input-area">
                <span>$</span>
                <input type="text" id="term-input" class="terminal-input" placeholder="Enter command (e.g. pip install requests)" onkeydown="if(event.key==='Enter') executeCommand()">
            </div>
        </div>
    </div>
    {% endif %}

    <script>
        let socket = io();
        {% if session.logged_in %}
        socket.on('connect', () => { 
            appendTerminal("System: Connected to CyberIDE Terminal.");
            socket.emit('get_file', {filename: document.getElementById('filename').value}); 
        });

        socket.on('file_content', d => { document.getElementById('code-editor').value = d.content; });
        
        socket.on('output', d => { appendTerminal(d.data); });

        function appendTerminal(text) {
            const t = document.getElementById('terminal');
            const div = document.createElement('div');
            div.textContent = text;
            t.appendChild(div);
            t.scrollTop = t.scrollHeight;
        }

        function saveFile() { socket.emit('save_file', {filename: document.getElementById('filename').value, content: document.getElementById('code-editor').value}); }
        
        function runCode() { 
            appendTerminal("\\n[Running Code...]");
            saveFile(); 
            socket.emit('run_code', {filename: document.getElementById('filename').value}); 
        }

        function executeCommand() {
            const input = document.getElementById('term-input');
            const cmd = input.value.trim();
            if(!cmd) return;
            
            appendTerminal("$ " + cmd);
            socket.emit('terminal_cmd', {command: cmd});
            input.value = '';
        }
        {% endif %}
    </script>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if request.form.get('password') == Config.PASSWORD:
            session['logged_in'] = True
            return redirect('/')
        flash('Invalid Password')
    return render_template_string(HTML_TEMPLATE)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ৪. সকেট ইভেন্ট হ্যান্ডলার
@socketio.on('get_file')
def get_file(data):
    name = secure_filename(data['filename'])
    path = project_path / name
    content = path.read_text() if path.exists() else "# Start coding here"
    emit('file_content', {'content': content})

@socketio.on('save_file')
def save_file(data):
    name = secure_filename(data['filename'])
    (project_path / name).write_text(data['content'])

@socketio.on('run_code')
def run_code(data):
    name = secure_filename(data['filename'])
    def run_proc():
        proc = subprocess.Popen(['python', str(project_path / name)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            socketio.emit('output', {'data': line.strip()})
    socketio.start_background_task(run_proc)

# ৫. ইন্টারেক্টিভ টার্মিনাল হ্যান্ডলার
@socketio.on('terminal_cmd')
def handle_terminal(data):
    cmd = data['command'].strip()
    
    def execute_cmd():
        try:
            # কমান্ড রান করা
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            # রিয়েলটাইম আউটপুট দেখানো
            for line in proc.stdout:
                socketio.emit('output', {'data': line.strip()})
            
            proc.wait()

            # লাইব্রেরি সেভ করার লজিক (যদি pip install হয়)
            if cmd.startswith('pip install'):
                parts = cmd.split()
                # 'pip install requests' থেকে 'requests' অংশটি নেওয়া
                if len(parts) >= 3:
                    lib_name = parts[2]
                    if proc.returncode == 0:
                        save_lib_to_db(lib_name)
                        socketio.emit('output', {'data': f"--- Database: {lib_name} has been tracked ---"})
                    else:
                        socketio.emit('output', {'data': f"--- Error: Could not install {lib_name} ---"})

        except Exception as e:
            socketio.emit('output', {'data': f"Error: {str(e)}"})

    socketio.start_background_task(execute_cmd)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=Config.PORT)
