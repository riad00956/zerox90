import os
import sys
import subprocess
import threading
import hashlib
import secrets
from pathlib import Path
from flask import Flask, render_template_string, request, session, redirect, url_for, flash, jsonify
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

# Configuration for Railway
class Config:
    # Railway automatically sets PORT
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    PASSWORD = os.environ.get('PASSWORD', 'admin123')
    PROJECT_DIR = os.environ.get('PROJECT_DIR', 'projects')
    ALLOWED_EXTENSIONS = {'py', 'js', 'html', 'css', 'txt', 'md', 'json'}
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    HOST = '0.0.0.0'
    PORT = int(os.environ.get('PORT', 8000))

app = Flask(__name__)
app.config.from_object(Config)

# For Railway, use async_mode 'threading'
socketio = SocketIO(app, 
                   cors_allowed_origins="*",
                   async_mode='threading',
                   ping_timeout=60,
                   ping_interval=25,
                   logger=False,
                   engineio_logger=False)

# Create project directory
project_path = Path(Config.PROJECT_DIR)
project_path.mkdir(exist_ok=True)

# HTML Template (will be in templates/index.html for production)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CyberIDE on Railway</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.0/socket.io.min.js"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #11111f;
            --accent: #6366f1;
            --text: #f8fafc;
            --border: rgba(255, 255, 255, 0.1);
        }
        [data-theme="light"] {
            --bg-primary: #f8fafc;
            --bg-secondary: #f1f5f9;
            --text: #0f172a;
            --border: rgba(0, 0, 0, 0.1);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: system-ui, sans-serif; }
        body { background: var(--bg-primary); color: var(--text); min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; padding: 20px 0; }
        .logo { font-size: 24px; font-weight: bold; background: linear-gradient(45deg, #6366f1, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .card { background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin: 20px 0; }
        input, textarea, select { width: 100%; padding: 12px; margin: 10px 0; background: rgba(0,0,0,0.2); border: 1px solid var(--border); color: var(--text); border-radius: 8px; }
        .btn { background: linear-gradient(45deg, #6366f1, #8b5cf6); color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: bold; }
        .btn:hover { opacity: 0.9; }
        .terminal { background: #000; color: #0f0; font-family: monospace; padding: 15px; border-radius: 8px; height: 300px; overflow-y: auto; margin: 20px 0; }
        .file-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; margin: 20px 0; }
        .file-item { padding: 10px; background: rgba(99, 102, 241, 0.1); border-radius: 8px; cursor: pointer; }
        .file-item:hover { background: rgba(99, 102, 241, 0.2); }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; }
        .modal.active { display: flex; }
        .modal-content { background: var(--bg-secondary); padding: 30px; border-radius: 12px; width: 90%; max-width: 400px; }
    </style>
</head>
<body>
    {% if not session.logged_in %}
    <div class="container" style="display: flex; justify-content: center; align-items: center; height: 100vh;">
        <div class="card" style="max-width: 400px;">
            <h2 style="text-align: center; margin-bottom: 20px;">🔐 CyberIDE Login</h2>
            <form method="POST" action="/login">
                <input type="password" name="password" placeholder="Enter password" required>
                <button type="submit" class="btn" style="width: 100%;">Access IDE</button>
            </form>
            {% with messages = get_flashed_messages() %}
                {% if messages %}
                    <div style="color: #ef4444; margin-top: 10px; text-align: center;">{{ messages[0] }}</div>
                {% endif %}
            {% endwith %}
            <div style="text-align: center; margin-top: 20px; color: #64748b; font-size: 12px;">
                Deployed on Railway • Secure Web IDE
            </div>
        </div>
    </div>
    {% else %}
    <div class="container">
        <header class="header">
            <div class="logo">🚀 CyberIDE</div>
            <div style="display: flex; gap: 10px;">
                <div style="padding: 8px 16px; background: rgba(16, 185, 129, 0.1); border-radius: 20px; font-size: 14px;">
                    <span style="color: #10b981;">●</span> Online
                </div>
                <button onclick="toggleTheme()" class="btn">🌙 Theme</button>
                <a href="/logout" class="btn" style="background: #ef4444;">Logout</a>
            </div>
        </header>

        <div style="display: grid; grid-template-columns: 250px 1fr; gap: 20px;">
            <!-- Sidebar -->
            <div class="card">
                <h3>📁 Files</h3>
                <button onclick="showNewFileModal()" class="btn" style="width: 100%; margin: 10px 0;">+ New File</button>
                <div id="file-list" class="file-list">
                    <!-- Files will load here -->
                </div>
            </div>

            <!-- Main Editor -->
            <div>
                <div class="card">
                    <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                        <input type="text" id="filename" placeholder="main.py" value="main.py" style="flex: 1;">
                        <select id="file-type" style="width: 120px;">
                            <option value="python">Python</option>
                            <option value="javascript">JavaScript</option>
                            <option value="html">HTML</option>
                        </select>
                    </div>
                    <textarea id="code" rows="15" placeholder="Write your code here...">print("Hello from Railway!")</textarea>
                    <div style="display: flex; gap: 10px; margin-top: 15px;">
                        <button onclick="saveFile()" class="btn" style="flex: 1;">💾 Save</button>
                        <button onclick="runCode()" class="btn" style="flex: 1; background: linear-gradient(45deg, #10b981, #34d399);">▶️ Run</button>
                        <button onclick="downloadFile()" class="btn" style="flex: 1; background: linear-gradient(45deg, #3b82f6, #60a5fa);">📥 Download</button>
                    </div>
                </div>

                <!-- Terminal -->
                <div class="card">
                    <h3>💻 Terminal</h3>
                    <div class="terminal" id="terminal-output">
                        <div>$ Ready for commands...</div>
                    </div>
                    <div style="display: flex; gap: 10px; margin-top: 15px;">
                        <input type="text" id="command-input" placeholder="python --version" style="flex: 1;">
                        <button onclick="sendCommand()" class="btn">Send</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Modals -->
        <div class="modal" id="new-file-modal">
            <div class="modal-content">
                <h3 style="margin-bottom: 20px;">Create New File</h3>
                <input type="text" id="new-filename" placeholder="example.py">
                <div style="display: flex; gap: 10px; margin-top: 20px;">
                    <button onclick="closeModal()" class="btn" style="background: #64748b;">Cancel</button>
                    <button onclick="createFile()" class="btn">Create</button>
                </div>
            </div>
        </div>

        <footer style="text-align: center; padding: 40px 0; color: #64748b; font-size: 14px;">
            <div>CyberIDE • Deployed on Railway • Powered by Flask & Socket.IO</div>
            <div style="font-size: 12px; margin-top: 10px;">© 2024 All rights reserved</div>
        </footer>
    </div>
    {% endif %}

    <script>
        // Initialize icons
        lucide.createIcons();
        
        // Socket.IO connection
        const socket = io();
        let currentFile = 'main.py';
        
        // Theme
        function toggleTheme() {
            const current = document.documentElement.getAttribute('data-theme');
            const newTheme = current === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        }
        
        // Load saved theme
        const savedTheme = localStorage.getItem('theme') || 'dark';
        document.documentElement.setAttribute('data-theme', savedTheme);
        
        {% if session.logged_in %}
        // Socket events
        socket.on('connect', () => {
            addTerminalLine('✅ Connected to server');
            loadFiles();
            loadFile(currentFile);
        });
        
        socket.on('file_list', (files) => {
            updateFileList(files);
        });
        
        socket.on('file_content', (data) => {
            if (data.filename === currentFile) {
                document.getElementById('code').value = data.content;
            }
        });
        
        socket.on('command_output', (data) => {
            addTerminalLine(data.output);
        });
        
        socket.on('file_saved', () => {
            alert('File saved successfully!');
            loadFiles();
        });
        
        // File functions
        function loadFiles() {
            socket.emit('get_files');
        }
        
        function loadFile(filename) {
            currentFile = filename;
            document.getElementById('filename').value = filename;
            socket.emit('get_file', { filename: filename });
        }
        
        function saveFile() {
            const filename = document.getElementById('filename').value;
            const content = document.getElementById('code').value;
            socket.emit('save_file', { filename, content });
        }
        
        function runCode() {
            const filename = document.getElementById('filename').value;
            const content = document.getElementById('code').value;
            addTerminalLine(`$ Running ${filename}...`);
            socket.emit('run_code', { filename, content });
        }
        
        function sendCommand() {
            const cmd = document.getElementById('command-input').value;
            if (!cmd) return;
            addTerminalLine(`$ ${cmd}`);
            socket.emit('execute_command', { command: cmd });
            document.getElementById('command-input').value = '';
        }
        
        function downloadFile() {
            const content = document.getElementById('code').value;
            const filename = document.getElementById('filename').value;
            const blob = new Blob([content], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
        }
        
        // Modal functions
        function showNewFileModal() {
            document.getElementById('new-file-modal').classList.add('active');
        }
        
        function closeModal() {
            document.getElementById('new-file-modal').classList.remove('active');
        }
        
        function createFile() {
            const filename = document.getElementById('new-filename').value;
            if (!filename) return alert('Enter filename');
            socket.emit('create_file', { filename });
            closeModal();
            setTimeout(loadFiles, 500);
        }
        
        // Helper functions
        function updateFileList(files) {
            const container = document.getElementById('file-list');
            container.innerHTML = '';
            files.forEach(file => {
                const div = document.createElement('div');
                div.className = 'file-item';
                div.textContent = file.name;
                div.onclick = () => loadFile(file.name);
                container.appendChild(div);
            });
        }
        
        function addTerminalLine(text) {
            const terminal = document.getElementById('terminal-output');
            const div = document.createElement('div');
            div.textContent = text;
            terminal.appendChild(div);
            terminal.scrollTop = terminal.scrollHeight;
        }
        
        // Enter key for command input
        document.getElementById('command-input')?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendCommand();
        });
        {% endif %}
    </script>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main page"""
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == Config.PASSWORD:
            session['logged_in'] = True
            return redirect('/')
        else:
            flash('Invalid password!')
    
    if session.get('logged_in'):
        return render_template_string(HTML_TEMPLATE)
    return render_template_string(HTML_TEMPLATE)

@app.route('/login', methods=['POST'])
def login():
    """Login endpoint"""
    password = request.form.get('password', '')
    if password == Config.PASSWORD:
        session['logged_in'] = True
        return redirect('/')
    else:
        flash('Invalid password!')
        return redirect('/')

@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    return redirect('/')

# Socket.IO Events
@socketio.on('connect')
def handle_connect():
    """Handle new connection"""
    if not session.get('logged_in'):
        return False

@socketio.on('get_files')
def handle_get_files():
    """Get list of files"""
    try:
        files = []
        for f in project_path.iterdir():
            if f.is_file():
                files.append({'name': f.name, 'size': f.stat().st_size})
        emit('file_list', files)
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('get_file')
def handle_get_file(data):
    """Get file content"""
    try:
        filename = secure_filename(data.get('filename', ''))
        filepath = project_path / filename
        
        if filepath.exists():
            content = filepath.read_text(encoding='utf-8')
            emit('file_content', {'filename': filename, 'content': content})
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('save_file')
def handle_save_file(data):
    """Save file"""
    try:
        filename = secure_filename(data.get('filename', ''))
        content = data.get('content', '')
        
        if not filename:
            emit('error', {'message': 'Filename required'})
            return
        
        filepath = project_path / filename
        filepath.write_text(content, encoding='utf-8')
        emit('file_saved', {'filename': filename})
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('create_file')
def handle_create_file(data):
    """Create new file"""
    try:
        filename = secure_filename(data.get('filename', ''))
        if not filename:
            return
        
        filepath = project_path / filename
        filepath.touch()
        handle_get_files()
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('execute_command')
def handle_execute_command(data):
    """Execute shell command"""
    if not session.get('logged_in'):
        return
    
    cmd = data.get('command', '')
    
    # Security: Block dangerous commands
    dangerous = ['rm -rf', 'sudo', 'shutdown', 'reboot', 'mkfs', 'dd', '> /', '>> /']
    if any(d in cmd.lower() for d in dangerous):
        emit('command_output', {'output': 'Error: Command blocked for security'})
        return
    
    try:
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=project_path
        )
        
        for line in process.stdout:
            emit('command_output', {'output': line.strip()})
    except Exception as e:
        emit('command_output', {'output': f'Error: {str(e)}'})

@socketio.on('run_code')
def handle_run_code(data):
    """Run Python code"""
    if not session.get('logged_in'):
        return
    
    filename = secure_filename(data.get('filename', ''))
    code = data.get('code', '')
    
    if not filename.endswith('.py'):
        emit('command_output', {'output': 'Error: Only Python files can be executed'})
        return
    
    try:
        # Save file
        filepath = project_path / filename
        filepath.write_text(code, encoding='utf-8')
        
        # Run it
        process = subprocess.Popen(
            ['python', str(filepath)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=project_path
        )
        
        for line in process.stdout:
            emit('command_output', {'output': line.strip()})
    except Exception as e:
        emit('command_output', {'output': f'Error: {str(e)}'})

if __name__ == '__main__':
    print(f"""
    🚀 CyberIDE Starting on Railway
    📍 URL: https://your-app.railway.app
    🔐 Password: {Config.PASSWORD}
    📁 Project Dir: {project_path.absolute()}
    """)
    
    # Create default file
    default_file = project_path / 'main.py'
    if not default_file.exists():
        default_file.write_text('print("Hello from CyberIDE on Railway!")', encoding='utf-8')
    
    socketio.run(app, host=Config.HOST, port=Config.PORT)
