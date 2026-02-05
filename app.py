import os
import secrets
import subprocess
import sqlite3
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
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

project_path = Path(Config.PROJECT_DIR)
project_path.mkdir(exist_ok=True)

# ২. ডেটাবেজ সেটআপ (লাইব্রেরি ট্র্যাকিং এর জন্য)
def init_db():
    conn = sqlite3.connect(Config.DB_NAME)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS libs (id INTEGER PRIMARY KEY, name TEXT UNIQUE)')
    conn.commit()
    conn.close()

# আগে ইন্সটল করা লাইব্রেরিগুলো রিস্টোর করা
def restore_libs():
    conn = sqlite3.connect(Config.DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM libs')
    libs = cursor.fetchall()
    conn.close()
    for lib in libs:
        subprocess.run(['pip', 'install', lib[0]])

init_db()
restore_libs()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>CyberIDE Pro</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.0/socket.io.min.js"></script>
    <style>
        :root { --bg: #0f172a; --card: #1e293b; --text: #f1f5f9; --primary: #3b82f6; --success: #10b981; --danger: #ef4444; }
        body { background: var(--bg); color: var(--text); font-family: sans-serif; padding: 20px; }
        .card { background: var(--card); border-radius: 12px; padding: 20px; border: 1px solid #334155; margin-bottom: 20px; }
        textarea { width: 100%; height: 250px; background: #0f172a; color: #00ff00; border: 1px solid #475569; border-radius: 8px; font-family: monospace; }
        .terminal { background: #000; color: #00ff00; padding: 15px; height: 150px; overflow-y: auto; border-radius: 8px; font-family: monospace; }
        .btn { padding: 10px 15px; border-radius: 8px; border: none; cursor: pointer; color: white; background: var(--primary); font-weight: bold; }
        .btn-install { background: #8b5cf6; }
        input { padding: 10px; background: #0f172a; border: 1px solid #475569; color: white; border-radius: 8px; margin-right: 5px; }
    </style>
</head>
<body>
    {% if not session.logged_in %}
    <div style="max-width: 400px; margin: 100px auto;" class="card">
        <form method="POST"><h2>CyberIDE</h2><input type="password" name="password" style="width:100%"><br><br><button class="btn" style="width:100%">Login</button></form>
    </div>
    {% else %}
    <div style="max-width: 900px; margin: 0 auto;">
        <div class="card">
            <h3>Code Editor</h3>
            <input type="text" id="filename" value="main.py">
            <textarea id="code-editor"></textarea>
            <div style="margin-top:10px;">
                <button class="btn" onclick="saveFile()">Save</button>
                <button class="btn" style="background:var(--success)" onclick="runCode()">Run Code</button>
            </div>
        </div>

        <div class="card">
            <h3>Library Manager</h3>
            <input type="text" id="lib-name" placeholder="Example: requests">
            <button class="btn btn-install" onclick="installLib()">Install Library</button>
        </div>

        <div class="card">
            <h3>Console Output</h3>
            <div id="terminal" class="terminal"></div>
        </div>
    </div>
    {% endif %}

    <script>
        let socket = io();
        {% if session.logged_in %}
        socket.on('connect', () => { socket.emit('get_file', {filename: 'main.py'}); });
        socket.on('file_content', d => { document.getElementById('code-editor').value = d.content; });
        socket.on('output', d => { 
            const t = document.getElementById('terminal');
            t.innerHTML += `<div>> ${d.data}</div>`;
            t.scrollTop = t.scrollHeight;
        });

        function saveFile() { socket.emit('save_file', {filename: document.getElementById('filename').value, content: document.getElementById('code-editor').value}); }
        function runCode() { document.getElementById('terminal').innerHTML = ''; saveFile(); socket.emit('run_code', {filename: document.getElementById('filename').value}); }
        function installLib() {
            const lib = document.getElementById('lib-name').value;
            if(lib) {
                document.getElementById('terminal').innerHTML += `<div>Installing ${lib}...</div>`;
                socket.emit('install_lib', {name: lib});
                document.getElementById('lib-name').value = '';
            }
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

@socketio.on('get_file')
def get_file(data):
    name = secure_filename(data['filename'])
    path = project_path / name
    content = path.read_text() if path.exists() else "# Start coding"
    emit('file_content', {'content': content})

@socketio.on('save_file')
def save_file(data):
    name = secure_filename(data['filename'])
    (project_path / name).write_text(data['content'])

@socketio.on('run_code')
def run_code(data):
    name = secure_filename(data['filename'])
    try:
        proc = subprocess.Popen(['python', str(project_path / name)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            emit('output', {'data': line.strip()})
    except Exception as e:
        emit('output', {'data': str(e)})

# লাইব্রেরি ইন্সটল এবং ডেটাবেজে সেভ করার হ্যান্ডলার
@socketio.on('install_lib')
def install_lib(data):
    lib_name = data['name'].strip()
    try:
        # pip দিয়ে ইন্সটল করা
        process = subprocess.run(['pip', 'install', lib_name], capture_output=True, text=True)
        if process.returncode == 0:
            # ডেটাবেজে সেভ করা
            conn = sqlite3.connect(Config.DB_NAME)
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO libs (name) VALUES (?)', (lib_name,))
            conn.commit()
            conn.close()
            emit('output', {'data': f'Successfully installed {lib_name} and saved to database.'})
        else:
            emit('output', {'data': f'Error installing {lib_name}: {process.stderr}'})
    except Exception as e:
        emit('output', {'data': str(e)})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=Config.PORT)
