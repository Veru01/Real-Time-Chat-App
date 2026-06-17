from flask import Flask, render_template, request, send_from_directory, jsonify
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import os
import datetime

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
    async_mode='eventlet'
)

# ─────────────────────────────────────────
#  Allowed File Types
# ─────────────────────────────────────────
ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'webp',   # images
    'mp4', 'mkv', 'avi', 'mov',             # videos
    'pdf', 'docx', 'xlsx', 'pptx', 'txt',  # documents
    'zip', 'rar', '7z'                      # archives
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

        # Avoid overwriting — prefix with timestamp
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        file_url = f'/uploads/{filename}'
        file_ext = filename.rsplit('.', 1)[1].lower()

        # Determine file type for the frontend
        if file_ext in {'png', 'jpg', 'jpeg', 'gif', 'webp'}:
            file_type = 'image'
        elif file_ext in {'mp4', 'mkv', 'avi', 'mov'}:
            file_type = 'video'
        else:
            file_type = 'file'

        now = datetime.datetime.now().strftime('%I:%M %p')

        socketio.emit('file_shared', {
            'username': username,
            'filename': file.filename,   # original name for display
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

    # Notify everyone someone joined
    emit('receive_message', {
        'username': 'System',
        'message': 'A new user joined the chat.',
        'time': '',
        'online': get_online_count()
    }, broadcast=True)

    # Send current online count to everyone
    emit('online_count', {'count': get_online_count()}, broadcast=True)


@socketio.on('disconnect')
def handle_disconnect():
    username = online_users.pop(request.sid, 'Someone')
    print(f'[-] Client disconnected: {request.sid} ({username})')

    emit('receive_message', {
        'username': 'System',
        'message': f'{username} left the chat.',
        'time': '',
        'online': get_online_count()
    }, broadcast=True)

    emit('online_count', {'count': get_online_count()}, broadcast=True)


@socketio.on('set_username')
def handle_set_username(data):
    """Called when a user sets or changes their name."""
    old_name = online_users.get(request.sid, 'Anonymous')
    new_name = data.get('username', 'Anonymous').strip() or 'Anonymous'
    online_users[request.sid] = new_name

    if old_name != new_name:
        emit('receive_message', {
            'username': 'System',
            'message': f'{old_name} is now known as {new_name}.',
            'time': ''
        }, broadcast=True)


@socketio.on('send_message')
def handle_message(data):
    username = data.get('username', 'Anonymous')
    message = data.get('message', '').strip()

    if not message:
        return  # ignore empty messages

    # Update tracked username
    online_users[request.sid] = username

    now = datetime.datetime.now().strftime('%I:%M %p')

    emit('receive_message', {
        'username': username,
        'message': message,
        'time': now
    }, broadcast=True)


# ─────────────────────────────────────────
#  Run
# ─────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 45)
    print("  LAN Chat App is running!")
    print("  Local:   http://localhost:5000")
    print("  Network: http://<your-ip>:5000")
    print("  Run 'ipconfig' to find your IP")
    print("=" * 45)
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)