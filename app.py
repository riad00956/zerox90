import os
import sys
import subprocess
import threading
import secrets
from pathlib import Path
from flask import Flask, render_template_string, request, session, redirect, url_for, flash
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

# Configuration
class Config:
    # Railway automatically provides PORT or uses 8000
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    PASSWORD = os.environ.get('PASSWORD', 'admin123')
    PROJECT_DIR = 'projects'
    HOST = '0.0.0.0'
    PORT = int(os.environ.get('PORT', 8000))

app = Flask(__name__)
app.config.from_object(Config)

# SocketIO setup
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading'
)

# Create project directory
project_path = Path(Config.PROJECT_DIR)
project_path.mkdir(exist_ok=True)

# default main.py content
DEFAULT_MAIN_PY = '''# Welcome to CyberIDE on Railway!
# This is a Python file that runs on Railway cloud

print("🚀 Hello from CyberIDE!")
print("🌐 Running on Railway cloud platform")

# Simple example
numbers = [1, 2, 3, 4, 5]
print(f"\\nList of numbers: {numbers}")
print(f"Sum: {sum(numbers)}")
'''

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CyberIDE on Railway</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.0/socket.io.min.js"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        :root {
            --bg: #0f172a; --card: #1e293b; --text: #f1f5f9;
            --primary: #3b82f6; --success: #10b981; --danger: #ef4444;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: var(--bg); color: var(--text); font-family: sans-serif; min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; padding: 20px 0; border-bottom: 1px solid #334155; margin-bottom: 30px; }
        .logo { font-size: 24px; font-weight: bold; background: linear-gradient(135deg, #3b82f6, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .card { background: var(--card); border-radius: 12px; padding: 25px; margin-bottom: 20px; border: 1px solid #334155; }
        input, textarea, select { width: 100%; padding: 12px; background: #0f172a; border: 1px solid #475569; border-radius: 8px; color: var(--text); margin-bottom: 15px; }
        .btn { background: var(--primary); color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; }
        .btn-success { background: var(--success); } .btn-danger { background: var(--danger); }
        .terminal { background: #000; color: #00ff00; font-family: monospace; padding: 20px; height: 300px; overflow-y: auto; border-radius: 8px; }
        .file-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; margin-top: 15px; }
        .file-item { background: rgba(59,130,246,0.1); border: 1px solid #334155; border-radius: 8px; padding: 12px; }
        .alert { position: fixed; top: 20px; right: 20px; padding: 15px; border-radius: 8px; z-index: 9999; color: white; }
    </style>
</head>
<body>
    {% if not session.logged_in %}
    <div class="container" style="display: flex; justify-content: center; align-items: center; min-height: 100vh;">
        <div class="card" style="max-width: 400px; width: 100%;">
            <h2 style="text-align: center; margin-bottom: 25px;"><i data-lucide="lock"></i> CyberIDE</h2>
            <form method="POST">
                <input type="password" name="password" placeholder="Password" required>
                <button type="submit" class="btn" style="width: 100%;">Unlock</button>
            </form>
            {% with messages = get_flashed_messages() %}{% if messages %}<p style="color:var(--danger); margin-top:10px;">{{ messages[0] }}</p>{% endif %}{% endwith %}
        </div>
    </div>
    {% else %}
    <div class="container">
        <header class="header">
            <div class="logo"><i data-lucide="cpu"></i> CyberIDE</div>
            <div style="display: flex; gap: 15px;">
                <a href="/logout" class="btn btn-danger">Logout</a>
            </div>
        </header>

        <div style="display: grid; grid-template-columns: 250px 1fr; gap: 20px;">
            <div class="card">
                <h3>Files</h3>
                <button onclick="showNewFileModal()" class="btn" style="width: 100%; margin: 15px 0;">New File</button>
                <div id="file-list" class="file-list"></div>
            </div>
            <div>
                <div class="card">
                    <input type="text" id="filename" value="main.py" style="width: 200px;">
                    <textarea id="code" rows="15"></textarea>
                    <div style="display: flex; gap: 10px;">
                        <button onclick="saveFile()" class="btn">Save</button>
                        <button onclick="runCode()" class="btn btn-success">Run</button>
                    </div>
                </div>
                <div class="card">
                    <h3>Terminal</h3>
                    <div class="terminal" id="terminal-output"></div>
                    <div style="display: flex; gap: 10px; margin-top: 10px;">
                        <input type="text" id="command-input" placeholder="Command..." style="flex:1;">
                        <button onclick="sendCommand()" class="btn">Send</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
    {% endif %}

    <script>
        lucide.createIcons();
        let socket = null;
        let currentFile = 'main.py';

        {% if session.logged_in %}
        socket = io();
        socket.on('connect', () => { loadFiles(); loadFile(currentFile); });
        socket.on('file_list', (files) => { updateFileList(files); });
        socket.on('file_content', (data) => { document.getElementById('code').value = data.content; });
        socket.on('command_output', (data) => { 
            const term = document.getElementById('terminal-output');
            term.innerHTML += `<div>${data.output}</div>`;
            term.scrollTop = term.scrollHeight;
        });

        function loadFiles() { socket.emit('get_files'); }
        function loadFile(name) { currentFile = name; document.getElementById('filename').value = name; socket.emit('get_file', {filename: name}); }
        function saveFile() { socket.emit('save_file', {filename: document.getElementById('filename').value, content: document.getElementById('code').value}); }
        function runCode() { socket.emit('run_code', {filename: document.getElementById('filename').value, content: document.getElementById('code').value}); }
        function sendCommand() { 
            const cmd = document.getElementById('command-input').value;
            socket.emit('execute_command', {command: cmd});
            document.getElementById('command-input').value = '';
        }

        function updateFileList(files) {
            const list = document.getElementById('file-list');
            list.innerHTML = '';
            files.forEach(f => {
                list.innerHTML += `<div class="file-item">${f.name}<br><button onclick="loadFile('${f.name}')">Open</button></div>`;
            });
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
        flash('Invalid password!')
    return render_template_string(HTML_TEMPLATE)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@socketio.on('get_files')
def handle_get_files():
    files = [{'name': f.name} for f in project_path.iterdir() if f.is_file()]
    emit('file_list', files)

@socketio.on('get_file')
def handle_get_file(data):
    filename = secure_filename(data.get('filename', 'main.py'))
    path = project_path / filename
    if path.exists():
        emit('file_content', {'filename': filename, 'content': path.read_text()})

@socketio.on('save_file')
def handle_save_file(data):
    filename = secure_filename(data.get('filename', ''))
    if filename:
        (project_path / filename).write_text(data.get('content', ''))
        handle_get_files()

@socketio.on('execute_command')
def handle_command(data):
    cmd = data.get('command', '')
    try:
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=project_path)
        for line in process.stdout:
            emit('command_output', {'output': line.strip()})
    except Exception as e:
        emit('command_output', {'output': str(e)})

@socketio.on('run_code')
def handle_run(data):
    handle_save_file(data)
    filename = secure_filename(data.get('filename', 'main.py'))
    try:
        process = subprocess.Popen(['python', filename], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=project_path)
        for line in process.stdout:
            emit('command_output', {'output': line.strip()})
    except Exception as e:
        emit('command_output', {'output': str(e)})

if __name__ == '__main__':
    # Auto-create main.py if not exists
    main_file = project_path / 'main.py'
    if not main_file.exists():
        main_file.write_text(DEFAULT_MAIN_PY)
        
    socketio.run(app, host=Config.HOST, port=Config.PORT)
