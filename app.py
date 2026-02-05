import os
import secrets
import subprocess
from pathlib import Path
from flask import Flask, render_template_string, request, session, redirect, flash
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

# ১. কনফিগারেশন
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    PASSWORD = os.environ.get('PASSWORD', 'admin123')
    PROJECT_DIR = 'projects'
    PORT = int(os.environ.get('PORT', 8080))

app = Flask(__name__)
app.config.from_object(Config)

# ২. রেলওয়ের জন্য eventlet মোড (নিখুঁত পারফরম্যান্সের জন্য)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# প্রজেক্ট ডিরেক্টরি তৈরি
project_path = Path(Config.PROJECT_DIR)
project_path.mkdir(exist_ok=True)

# ডিফল্ট main.py কন্টেন্ট
DEFAULT_CODE = '''# Welcome to CyberIDE
print("🚀 Hello from Railway!")
'''

# ৩. ফ্রন্টএন্ড টেমপ্লেট
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>CyberIDE Final</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.0/socket.io.min.js"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        :root { --bg: #0f172a; --card: #1e293b; --text: #f1f5f9; --primary: #3b82f6; --success: #10b981; --danger: #ef4444; }
        body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; }
        .card { background: var(--card); border-radius: 12px; padding: 20px; margin-bottom: 20px; border: 1px solid #334155; }
        textarea { width: 100%; height: 300px; background: #0f172a; color: #fff; border: 1px solid #475569; padding: 10px; border-radius: 8px; font-family: monospace; }
        .terminal { background: #000; color: #00ff00; padding: 15px; height: 200px; overflow-y: auto; border-radius: 8px; font-family: monospace; margin-top: 10px; }
        .btn { padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer; font-weight: bold; color: white; background: var(--primary); }
        .btn-run { background: var(--success); }
        input { padding: 10px; background: #0f172a; border: 1px solid #475569; color: white; border-radius: 8px; }
    </style>
</head>
<body>
    {% if not session.logged_in %}
    <div style="max-width: 400px; margin: 100px auto;" class="card">
        <h2>CyberIDE Login</h2>
        <form method="POST"><input type="password" name="password" style="width:100%"><br><br><button class="btn" style="width:100%">Login</button></form>
        {% with m = get_flashed_messages() %}{% if m %}<p style="color:var(--danger)">{{m[0]}}</p>{% endif %}{% endwith %}
    </div>
    {% else %}
    <div style="max-width: 1000px; margin: 0 auto;">
        <div style="display:flex; justify-content: space-between; align-items: center;">
            <h1>CyberIDE</h1>
            <a href="/logout" style="color:var(--danger)">Logout</a>
        </div>
        <div class="card">
            <input type="text" id="filename" value="main.py">
            <textarea id="code-editor" placeholder="Write code here..."></textarea>
            <div style="margin-top:10px; display:flex; gap:10px;">
                <button class="btn" onclick="saveFile()">Save</button>
                <button class="btn btn-run" onclick="runCode()">Run Code</button>
            </div>
        </div>
        <div class="card">
            <h3>Terminal Output</h3>
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

        function saveFile() {
            socket.emit('save_file', {
                filename: document.getElementById('filename').value,
                content: document.getElementById('code-editor').value
            });
        }
        function runCode() {
            document.getElementById('terminal').innerHTML = '';
            socket.emit('run_code', {
                filename: document.getElementById('filename').value,
                content: document.getElementById('code-editor').value
            });
        }
        {% endif %}
    </script>
</body>
</html>
"""

# ৪. ফ্লাস্ক রাউটস
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

# ৫. সকেট হ্যান্ডলার
@socketio.on('get_file')
def get_file(data):
    name = secure_filename(data['filename'])
    path = project_path / name
    content = path.read_text() if path.exists() else DEFAULT_CODE
    emit('file_content', {'content': content})

@socketio.on('save_file')
def save_file(data):
    name = secure_filename(data['filename'])
    (project_path / name).write_text(data['content'])

@socketio.on('run_code')
def run_code(data):
    save_file(data)
    name = secure_filename(data['filename'])
    try:
        # সাবপ্রসেস রান করা
        proc = subprocess.Popen(['python', str(project_path / name)], 
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            emit('output', {'data': line.strip()})
    except Exception as e:
        emit('output', {'data': str(e)})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=Config.PORT)
