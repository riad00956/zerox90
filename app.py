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
    # Railway automatically provides PORT
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    PASSWORD = os.environ.get('PASSWORD', 'admin123')
    PROJECT_DIR = 'projects'
    HOST = '0.0.0.0'
    PORT = int(os.environ.get('PORT', 8000))

app = Flask(__name__)
app.config.from_object(Config)

# Use async_mode='threading' for Railway compatibility
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    logger=False,
    engineio_logger=False
)

# Create project directory
project_path = Path(Config.PROJECT_DIR)
project_path.mkdir(exist_ok=True)

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
            --bg: #0f172a;
            --card: #1e293b;
            --text: #f1f5f9;
            --primary: #3b82f6;
            --success: #10b981;
            --danger: #ef4444;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            background: var(--bg); 
            color: var(--text); 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            min-height: 100vh;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            padding: 20px 0; 
            border-bottom: 1px solid #334155; 
            margin-bottom: 30px;
        }
        .logo { 
            font-size: 24px; 
            font-weight: bold; 
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .card { 
            background: var(--card); 
            border-radius: 12px; 
            padding: 25px; 
            margin-bottom: 20px;
            border: 1px solid #334155;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        input, textarea, select {
            width: 100%;
            padding: 12px 15px;
            background: #0f172a;
            border: 1px solid #475569;
            border-radius: 8px;
            color: var(--text);
            font-size: 14px;
            margin-bottom: 15px;
        }
        input:focus, textarea:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
        .btn {
            background: linear-gradient(135deg, var(--primary), #6366f1);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(59, 130, 246, 0.3);
        }
        .btn-success { background: linear-gradient(135deg, var(--success), #34d399); }
        .btn-danger { background: linear-gradient(135deg, var(--danger), #f87171); }
        .terminal {
            background: #000;
            color: #00ff00;
            font-family: 'Courier New', monospace;
            padding: 20px;
            border-radius: 8px;
            height: 300px;
            overflow-y: auto;
            font-size: 14px;
            line-height: 1.5;
        }
        .terminal-line { margin-bottom: 4px; white-space: pre-wrap; }
        .file-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 10px;
            margin-top: 15px;
        }
        .file-item {
            background: rgba(59, 130, 246, 0.1);
            border: 1px solid rgba(59, 130, 246, 0.3);
            border-radius: 8px;
            padding: 12px;
            cursor: pointer;
            transition: all 0.3s;
        }
        .file-item:hover {
            background: rgba(59, 130, 246, 0.2);
            transform: translateY(-2px);
        }
        .alert {
            padding: 12px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid var(--primary);
            background: rgba(59, 130, 246, 0.1);
        }
        .alert-success { border-color: var(--success); background: rgba(16, 185, 129, 0.1); }
        .alert-error { border-color: var(--danger); background: rgba(239, 68, 68, 0.1); }
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0, 0, 0, 0.8);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: var(--card);
            padding: 30px;
            border-radius: 12px;
            width: 90%;
            max-width: 400px;
        }
        .status {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 20px;
            font-size: 14px;
        }
        .status-dot {
            width: 8px; height: 8px;
            background: var(--success);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        @media (max-width: 768px) {
            .container { padding: 15px; }
            .header { flex-direction: column; gap: 15px; text-align: center; }
        }
    </style>
</head>
<body>
    {% if not session.logged_in %}
    <div class="container" style="display: flex; justify-content: center; align-items: center; min-height: 100vh;">
        <div class="card" style="max-width: 400px; width: 100%;">
            <h2 style="text-align: center; margin-bottom: 25px; display: flex; align-items: center; justify-content: center; gap: 10px;">
                <i data-lucide="lock"></i> CyberIDE Access
            </h2>
            <form method="POST">
                <input type="password" name="password" placeholder="Enter password" required>
                <button type="submit" class="btn" style="width: 100%;">
                    <i data-lucide="key"></i> Unlock IDE
                </button>
            </form>
            {% with messages = get_flashed_messages() %}
                {% if messages %}
                    <div class="alert alert-error" style="margin-top: 20px;">
                        <i data-lucide="alert-circle"></i> {{ messages[0] }}
                    </div>
                {% endif %}
            {% endwith %}
            <div style="text-align: center; margin-top: 25px; color: #64748b; font-size: 12px;">
                <div>Deployed on Railway</div>
                <div style="margin-top: 5px;">Secure Web IDE v1.0</div>
            </div>
        </div>
    </div>
    {% else %}
    <div class="container">
        <!-- Header -->
        <header class="header">
            <div class="logo">
                <i data-lucide="cpu"></i> CyberIDE
            </div>
            <div style="display: flex; align-items: center; gap: 15px;">
                <div class="status">
                    <div class="status-dot"></div>
                    <span id="connection-status">Online</span>
                </div>
                <button onclick="toggleTheme()" class="btn" style="background: #475569;">
                    <i data-lucide="sun-moon"></i> Theme
                </button>
                <a href="/logout" class="btn btn-danger">
                    <i data-lucide="log-out"></i> Logout
                </a>
            </div>
        </header>

        <!-- Main Layout -->
        <div style="display: grid; grid-template-columns: 250px 1fr; gap: 20px;">
            <!-- Sidebar -->
            <div class="card">
                <h3 style="margin-bottom: 20px; display: flex; align-items: center; gap: 10px;">
                    <i data-lucide="folder"></i> Files
                </h3>
                <button onclick="showNewFileModal()" class="btn" style="width: 100%; margin-bottom: 20px;">
                    <i data-lucide="file-plus"></i> New File
                </button>
                <div id="file-list" class="file-list">
                    <!-- Files will load here -->
                </div>
            </div>

            <!-- Main Content -->
            <div>
                <!-- Editor -->
                <div class="card">
                    <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                        <input type="text" id="filename" placeholder="main.py" value="main.py" style="flex: 1;">
                        <select id="file-type" style="width: 150px;">
                            <option value="python">Python</option>
                            <option value="javascript">JavaScript</option>
                            <option value="html">HTML</option>
                            <option value="css">CSS</option>
                        </select>
                    </div>
                    <textarea id="code" rows="18" placeholder="# Welcome to CyberIDE
# Write your code here...
print('Hello from Railway!')"></textarea>
                    <div style="display: flex; gap: 10px; margin-top: 20px;">
                        <button onclick="saveFile()" class="btn" style="flex: 1;">
                            <i data-lucide="save"></i> Save
                        </button>
                        <button onclick="runCode()" class="btn btn-success" style="flex: 1;">
                            <i data-lucide="play-circle"></i> Run
                        </button>
                        <button onclick="downloadFile()" class="btn" style="flex: 1; background: #475569;">
                            <i data-lucide="download"></i> Download
                        </button>
                    </div>
                </div>

                <!-- Terminal -->
                <div class="card">
                    <h3 style="margin-bottom: 15px; display: flex; align-items: center; gap: 10px;">
                        <i data-lucide="terminal"></i> Terminal
                    </h3>
                    <div class="terminal" id="terminal-output">
                        <div class="terminal-line">$ CyberIDE Terminal Ready</div>
                        <div class="terminal-line">$ Type commands below...</div>
                    </div>
                    <div style="display: flex; gap: 10px; margin-top: 15px;">
                        <input type="text" id="command-input" placeholder="Enter command (e.g., python --version)" style="flex: 1;">
                        <button onclick="sendCommand()" class="btn">
                            <i data-lucide="send"></i> Send
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Modals -->
        <div class="modal" id="new-file-modal">
            <div class="modal-content">
                <h3 style="margin-bottom: 20px; display: flex; align-items: center; gap: 10px;">
                    <i data-lucide="file-plus"></i> New File
                </h3>
                <input type="text" id="new-filename" placeholder="example.py" style="width: 100%;">
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 15px;">
                    <button onclick="createTemplate('main.py', 'python')" class="btn" style="background: #475569;">main.py</button>
                    <button onclick="createTemplate('script.js', 'javascript')" class="btn" style="background: #475569;">script.js</button>
                    <button onclick="createTemplate('index.html', 'html')" class="btn" style="background: #475569;">index.html</button>
                    <button onclick="createTemplate('style.css', 'css')" class="btn" style="background: #475569;">style.css</button>
                </div>
                <div style="display: flex; gap: 10px; margin-top: 20px;">
                    <button onclick="closeModal()" class="btn" style="background: #64748b; flex: 1;">Cancel</button>
                    <button onclick="createFile()" class="btn" style="flex: 1;">Create File</button>
                </div>
            </div>
        </div>

        <footer style="text-align: center; padding: 40px 0; color: #64748b; font-size: 14px; margin-top: 40px; border-top: 1px solid #334155;">
            <div>CyberIDE v1.0 • Deployed on Railway • Powered by Flask & Socket.IO</div>
            <div style="font-size: 12px; margin-top: 10px;">© 2024 All rights reserved • Secure Web IDE</div>
        </footer>
    </div>
    {% endif %}

    <script>
        // Initialize icons
        lucide.createIcons();
        
        // Global variables
        let socket = null;
        let currentFile = 'main.py';
        let isDarkMode = true;
        
        // Initialize when logged in
        {% if session.logged_in %}
        document.addEventListener('DOMContentLoaded', function() {
            initializeApp();
        });
        
        function initializeApp() {
            // Connect to Socket.IO
            socket = io();
            
            // Socket event handlers
            socket.on('connect', () => {
                console.log('Connected to server');
                showAlert('Connected to server', 'success');
                loadFiles();
                loadFile(currentFile);
            });
            
            socket.on('disconnect', () => {
                console.log('Disconnected from server');
                showAlert('Disconnected from server', 'error');
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
            
            socket.on('file_saved', (data) => {
                showAlert('File saved successfully: ' + data.filename, 'success');
                loadFiles();
            });
            
            socket.on('file_created', (data) => {
                showAlert('File created: ' + data.filename, 'success');
                closeModal();
                loadFiles();
                loadFile(data.filename);
            });
            
            socket.on('file_deleted', (data) => {
                showAlert('File deleted: ' + data.filename, 'success');
                loadFiles();
                if (data.filename === currentFile) {
                    document.getElementById('code').value = '';
                    document.getElementById('filename').value = '';
                    currentFile = '';
                }
            });
            
            socket.on('error', (data) => {
                showAlert('Error: ' + data.message, 'error');
            });
            
            // Enter key for command input
            document.getElementById('command-input')?.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') sendCommand();
            });
            
            // Load theme preference
            const savedTheme = localStorage.getItem('theme');
            if (savedTheme === 'light') {
                toggleTheme();
            }
            
            // Auto-save
            let saveTimeout;
            document.getElementById('code').addEventListener('input', function() {
                clearTimeout(saveTimeout);
                saveTimeout = setTimeout(autoSave, 3000);
            });
        }
        
        // File management
        function loadFiles() {
            if (socket) {
                socket.emit('get_files');
            }
        }
        
        function loadFile(filename) {
            if (socket) {
                currentFile = filename;
                document.getElementById('filename').value = filename;
                socket.emit('get_file', { filename: filename });
            }
        }
        
        function saveFile() {
            if (!socket) return;
            
            const filename = document.getElementById('filename').value.trim();
            const content = document.getElementById('code').value;
            
            if (!filename) {
                showAlert('Please enter a filename', 'error');
                return;
            }
            
            socket.emit('save_file', {
                filename: filename,
                content: content
            });
        }
        
        function autoSave() {
            if (!socket || !currentFile) return;
            
            const content = document.getElementById('code').value;
            socket.emit('save_file', {
                filename: currentFile,
                content: content
            });
        }
        
        function runCode() {
            if (!socket) return;
            
            const filename = document.getElementById('filename').value.trim();
            const content = document.getElementById('code').value;
            
            if (!filename) {
                showAlert('Please enter a filename', 'error');
                return;
            }
            
            if (!filename.endsWith('.py')) {
                showAlert('Only Python files can be executed', 'error');
                return;
            }
            
            addTerminalLine(`$ Running ${filename}...`);
            socket.emit('run_code', {
                filename: filename,
                content: content
            });
        }
        
        function downloadFile() {
            const content = document.getElementById('code').value;
            const filename = document.getElementById('filename').value || 'code.txt';
            
            const blob = new Blob([content], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }
        
        function deleteFile(filename) {
            if (!confirm('Delete ' + filename + '?')) return;
            
            if (socket) {
                socket.emit('delete_file', { filename: filename });
            }
        }
        
        // Terminal functions
        function sendCommand() {
            const input = document.getElementById('command-input');
            const command = input.value.trim();
            
            if (!command) return;
            
            addTerminalLine(`$ ${command}`);
            input.value = '';
            
            if (socket) {
                socket.emit('execute_command', { command: command });
            }
        }
        
        function addTerminalLine(text) {
            const terminal = document.getElementById('terminal-output');
            const line = document.createElement('div');
            line.className = 'terminal-line';
            line.textContent = text;
            terminal.appendChild(line);
            terminal.scrollTop = terminal.scrollHeight;
        }
        
        // Modal functions
        function showNewFileModal() {
            document.getElementById('new-file-modal').classList.add('active');
        }
        
        function closeModal() {
            document.getElementById('new-file-modal').classList.remove('active');
        }
        
        function createFile() {
            const filename = document.getElementById('new-filename').value.trim();
            if (!filename) {
                showAlert('Please enter a filename', 'error');
                return;
            }
            
            if (socket) {
                socket.emit('create_file', { filename: filename });
            }
        }
        
        function createTemplate(filename, type) {
            document.getElementById('new-filename').value = filename;
            
            const templates = {
                'python': 'print("Hello from CyberIDE!")',
                'javascript': 'console.log("Hello from CyberIDE!")',
                'html': '<!DOCTYPE html>\n<html>\n<head>\n    <title>CyberIDE</title>\n</head>\n<body>\n    <h1>Hello from CyberIDE!</h1>\n</body>\n</html>',
                'css': 'body {\n    font-family: Arial, sans-serif;\n    margin: 0;\n    padding: 20px;\n}'
            };
            
            if (socket) {
                socket.emit('create_file', {
                    filename: filename,
                    content: templates[type] || ''
                });
            }
        }
        
        // UI functions
        function updateFileList(files) {
            const container = document.getElementById('file-list');
            container.innerHTML = '';
            
            files.forEach(file => {
                const div = document.createElement('div');
                div.className = 'file-item';
                div.innerHTML = `
                    <div style="font-weight: 500; margin-bottom: 5px;">${file.name}</div>
                    <div style="font-size: 12px; color: #94a3b8;">${formatFileSize(file.size)}</div>
                    <div style="display: flex; gap: 5px; margin-top: 8px;">
                        <button onclick="loadFile('${file.name}')" style="background: #3b82f6; color: white; border: none; padding: 4px 8px; border-radius: 4px; font-size: 12px; cursor: pointer;">Open</button>
                        <button onclick="deleteFile('${file.name}')" style="background: #ef4444; color: white; border: none; padding: 4px 8px; border-radius: 4px; font-size: 12px; cursor: pointer;">Delete</button>
                    </div>
                `;
                container.appendChild(div);
            });
        }
        
        function formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }
        
        function showAlert(message, type = 'info') {
            const alert = document.createElement('div');
            alert.className = `alert alert-${type}`;
            alert.innerHTML = `
                <i data-lucide="${type === 'success' ? 'check-circle' : 'alert-circle'}"></i>
                ${message}
            `;
            
            document.body.appendChild(alert);
            lucide.createIcons();
            
            setTimeout(() => {
                alert.remove();
            }, 3000);
        }
        
        function toggleTheme() {
            isDarkMode = !isDarkMode;
            document.body.style.backgroundColor = isDarkMode ? '#0f172a' : '#f1f5f9';
            document.body.style.color = isDarkMode ? '#f1f5f9' : '#0f172a';
            
            const cards = document.querySelectorAll('.card');
            cards.forEach(card => {
                card.style.backgroundColor = isDarkMode ? '#1e293b' : '#ffffff';
                card.style.color = isDarkMode ? '#f1f5f9' : '#0f172a';
            });
            
            localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
        }
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
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle disconnect"""
    print(f"Client disconnected: {request.sid}")

@socketio.on('get_files')
def handle_get_files():
    """Get list of files"""
    try:
        files = []
        for f in project_path.iterdir():
            if f.is_file():
                stats = f.stat()
                files.append({
                    'name': f.name,
                    'size': stats.st_size,
                    'modified': stats.st_mtime
                })
        emit('file_list', files)
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('get_file')
def handle_get_file(data):
    """Get file content"""
    try:
        filename = secure_filename(data.get('filename', ''))
        filepath = project_path / filename
        
        if filepath.exists() and filepath.is_file():
            content = filepath.read_text(encoding='utf-8', errors='ignore')
            emit('file_content', {
                'filename': filename,
                'content': content
            })
        else:
            emit('error', {'message': 'File not found'})
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('save_file')
def handle_save_file(data):
    """Save file"""
    try:
        filename = secure_filename(data.get('filename', ''))
        content = data.get('content', '')
        
        if not filename:
            emit('error', {'message': 'Filename is required'})
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
        content = data.get('content', '')
        
        if not filename:
            emit('error', {'message': 'Filename is required'})
            return
        
        filepath = project_path / filename
        if filepath.exists():
            emit('error', {'message': 'File already exists'})
            return
        
        filepath.write_text(content or '', encoding='utf-8')
        emit('file_created', {'filename': filename})
        
        # Update file list for all clients
        handle_get_files()
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('delete_file')
def handle_delete_file(data):
    """Delete file"""
    try:
        filename = secure_filename(data.get('filename', ''))
        filepath = project_path / filename
        
        if not filepath.exists():
            emit('error', {'message': 'File not found'})
            return
        
        filepath.unlink()
        emit('file_deleted', {'filename': filename})
        
        # Update file list for all clients
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
    dangerous = ['rm -rf', 'sudo', 'shutdown', 'reboot', 'mkfs', 'dd', '> /', '>> /', '|', '&', '`']
    if any(danger in cmd.lower() for danger in dangerous):
        emit('command_output', {'output': 'Error: Command blocked for security reasons'})
        return
    
    try:
        # Execute command with timeout
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=project_path,
            bufsize=1,
            universal_newlines=True
        )
        
        # Read output in real-time
        for line in process.stdout:
            emit('command_output', {'output': line.rstrip()})
        
        process.wait()
        
    except Exception as e:
        emit('command_output', {'output': f'Error: {str(e)}'})

@socketio.on('run_code')
def handle_run_code(data):
    """Run Python code"""
    if not session.get('logged_in'):
        return
    
    filename = secure_filename(data.get('filename', ''))
    code = data.get('content', '')
    
    if not filename.endswith('.py'):
        emit('command_output', {'output': 'Error: Only Python files can be executed'})
        return
    
    try:
        # Save file first
        filepath = project_path / filename
        filepath.write_text(code, encoding='utf-8')
        
        # Execute Python file
        process = subprocess.Popen(
            ['python', str(filepath)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=project_path,
            bufsize=1,
            universal_newlines=True
        )
        
        # Read output in real-time
        for line in process.stdout:
            emit('command_output', {'output': line.rstrip()})
        
        process.wait()
        
    except Exception as e:
        emit('command_output', {'output': f'Error: {str(e)}'})

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 CyberIDE Starting on Railway")
    print(f"🔐 Password: {Config.PASSWORD}")
    print(f"📁 Project Directory: {project_path.absolute()}")
    print(f"🌐 Server will run on: http://{Config.HOST}:{Config.PORT}")
    print("=" * 60)
    
    # Create default file if it doesn't exist
    default_file = project_path / 'main.py'
    if not default_file.exists():
        default_file.write_text('''# Welcome to CyberIDE on Railway!
# This is a Python file that runs on Railway cloud

print("🚀 Hello from CyberIDE!")
print("🌐 Running on Railway cloud platform")

# Simple example
numbers = [1, 2, 3, 4, 5]
print(f"\\nList of numbers: {numbers}")
print(f"Sum: {sum(numbers)}")

# Run Python code directly from browser!
''', encoding='utf-8')
    
    # Start the server
    socketio.run(app, host=Config.HOST, port=Config.PORT, debug=False)
