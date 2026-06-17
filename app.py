from flask import Flask, render_template, request, send_from_directory, jsonify
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import os
import datetime
import pytz

# ─────────────────────────────────────────
#  App Configuration
# ─────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max file size

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25
)


# ─────────────────────────────────────────
#  Allowed File Types
# ─────────────────────────────────────────
ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'webp',
    'mp4', 'mkv', 'avi', 'mov',
    'pdf', 'docx', 'xlsx', 'pptx', 'txt',
    'zip', 'rar', '7z'
}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ─────────────────────────────────────────
#  Track Online Users
# ─────────────────────────────────────────
online_users = {}  # { session_id: username }

def get_online_count():
    return len(online_users)

def get_online_names():
    return list(online_users.values())

def get_ist_time():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.datetime.now(ist).strftime('%I:%M %p')

# ─────────────────────────────────────────
#  Ensure Upload Folder Exists
# ─────────────────────────────────────────
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# ─────────────────────────────────────────
#  Routes
# ─────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'}), 400

    file = request.files['file']
    username = request.form.get('username', 'Anonymous')

    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No file selected'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        file_url = f'/uploads/{filename}'
        file_ext = filename.rsplit('.', 1)[1].lower()

        if file_ext in {'png', 'jpg', 'jpeg', 'gif', 'webp'}:
            file_type = 'image'
        elif file_ext in {'mp4', 'mkv', 'avi', 'mov'}:
            file_type = 'video'
        else:
            file_type = 'file'

        now = get_ist_time()

        socketio.emit('file_shared', {
            'username': username,
            'filename': file.filename,
            'url': file_url,
            'file_type': file_type,
            'time': now
        })

        return jsonify({'status': 'ok', 'url': file_url})

    return jsonify({'status': 'error', 'message': 'File type not allowed'}), 400


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ─────────────────────────────────────────
#  Socket Events
# ─────────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    print(f'[+] Client connected: {request.sid}')
    online_users[request.sid] = 'Anonymous'

    emit('receive_message', {
        'username': 'System',
        'message': 'A new user joined the chat.',
        'time': '',
        'type': 'system'
    }, broadcast=True)

    emit('online_update', {
        'count': get_online_count(),
        'names': get_online_names()
    }, broadcast=True)


@socketio.on('disconnect')
def handle_disconnect():
    username = online_users.pop(request.sid, 'Someone')
    print(f'[-] Client disconnected: {request.sid} ({username})')

    emit('receive_message', {
        'username': 'System',
        'message': f'{username} left the chat.',
        'time': '',
        'type': 'system'
    }, broadcast=True)

    emit('online_update', {
        'count': get_online_count(),
        'names': get_online_names()
    }, broadcast=True)


@socketio.on('set_username')
def handle_set_username(data):
    old_name = online_users.get(request.sid, 'Anonymous')
    new_name = data.get('username', 'Anonymous').strip() or 'Anonymous'
    online_users[request.sid] = new_name

    if old_name != new_name and old_name != 'Anonymous':
        emit('receive_message', {
            'username': 'System',
            'message': f'{old_name} is now known as {new_name}.',
            'time': '',
            'type': 'system'
        }, broadcast=True)

    emit('online_update', {
        'count': get_online_count(),
        'names': get_online_names()
    }, broadcast=True)


@socketio.on('send_message')
def handle_message(data):
    username = data.get('username', 'Anonymous')
    message = data.get('message', '').strip()

    if not message:
        return

    online_users[request.sid] = username
    now = get_ist_time()

    emit('receive_message', {
        'username': username,
        'message': message,
        'time': now,
        'type': 'message'
    }, broadcast=True)


# ─────────────────────────────────────────
#  Run
# ─────────────────────────────────────────
if __name__ == '__main__':
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print("=" * 45)
    print("  LAN Chat App is running!")
    print(f"  Local:   http://localhost:5000")
    print(f"  Network: http://{local_ip}:5000")
    print("=" * 45)
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)