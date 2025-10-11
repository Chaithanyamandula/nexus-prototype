import os
import pickle
from tkinter import Image
import bcrypt
import cv2
import numpy as np
import face_recognition
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_socketio import SocketIO, join_room, emit
from models import db, User, FaceEncoding, Attendance
import base64,io
from PIL import Image


# ========== CONFIG ==========
app = Flask(__name__)
app.secret_key = "replace-with-a-strong-secret"
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+mysqlconnector://root:tiger@localhost:3306/face_auth_db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

socketio = SocketIO(app, cors_allowed_origins="*")

with app.app_context():
    db.create_all()

# ========== HELPERS ==========
def hash_password(plain):
    return bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(plain, hashed):
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except:
        return False

def decode_base64_image(base64_str):
    base64_data = base64_str.split(",")[1]
    img_data = base64.b64decode(base64_data)
    np_arr = np.frombuffer(img_data, np.uint8)
    return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

def encode_face(frame):
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    boxes = face_recognition.face_locations(rgb_frame)
    if not boxes:
        return None
    encodings = face_recognition.face_encodings(rgb_frame, boxes)
    return encodings[0] if encodings else None

def verify_face(reg_id, captured_encoding):
    face_record = FaceEncoding.query.get(reg_id)
    if not face_record or face_record.encoding_blob is None:
        return False
    stored_encoding = pickle.loads(face_record.encoding_blob)
    matches = face_recognition.compare_faces([stored_encoding], captured_encoding, tolerance=0.5)
    return matches[0]

# ========== ROUTES ==========
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        role = request.form.get('role')
        name = request.form.get('name')
        reg_id = request.form.get('reg_id')
        email = request.form.get('email')
        mobile = request.form.get('mobile')
        password = request.form.get('password')
        face_image = request.form.get('face_image')

        if not all([role, name, reg_id, email, password, face_image]):
            flash("Please fill all fields and capture your face", "danger")
            return redirect(url_for('signup'))

        if User.query.filter((User.reg_id==reg_id)|(User.email==email)).first():
            flash("User already exists", "danger")
            return redirect(url_for('signup'))

        user = User(
            role=role, name=name, reg_id=reg_id, email=email,
            mobile=mobile, password_hash=hash_password(password),
            created_at=datetime.utcnow()
        )
        db.session.add(user)
        db.session.commit()

        frame = decode_base64_image(face_image)
        enc = encode_face(frame)
        if enc is None:
            flash("No face detected. Signup failed.", "danger")
            db.session.delete(user)
            db.session.commit()
            return redirect(url_for('signup'))

        face_rec = FaceEncoding(reg_id=reg_id, encoding_blob=pickle.dumps(enc))
        db.session.add(face_rec)
        db.session.commit()

        flash("Signup successful! Please login.", "success")
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form.get('role')
        reg_id = request.form.get('reg_id')
        password = request.form.get('password')
        face_image = request.form.get('face_image')

        user = User.query.filter_by(reg_id=reg_id, role=role).first()
        if not user:
            flash("User not found", "danger")
            return redirect(url_for('login'))
        if not check_password(password, user.password_hash):
            flash("Incorrect password", "danger")
            return redirect(url_for('login'))
        if not face_image:
            flash("Please capture your face for verification", "danger")
            return redirect(url_for('login'))

        frame = decode_base64_image(face_image)
        captured_encoding = encode_face(frame)
        if captured_encoding is None or not verify_face(reg_id, captured_encoding):
            flash("Face verification failed", "danger")
            return redirect(url_for('login'))

        session['user_id'] = user.id
        flash("Login successful!", "success")
        return redirect(url_for('dashboard'))

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    uid = session.get('user_id')
    if not uid:
        return redirect(url_for('login'))
    user = User.query.get(uid)
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('login'))

    if user.role == "faculty":
        past_attendance = Attendance.query.filter_by(
            faculty_reg_id=user.reg_id
        ).order_by(Attendance.timestamp.desc()).all()
        return render_template('faculty_dashboard.html', user=user, past_attendance=past_attendance)

    return render_template('student_dashboard.html', user=user)

@app.route('/verify_face_for_qr', methods=['POST'])
def verify_face_for_qr():
    data = request.get_json()
    reg_id = data.get('reg_id')
    face_image = data.get('face_image')
    if not reg_id or not face_image:
        return jsonify({'success': False, 'error': 'Missing fields'})

    frame = decode_base64_image(face_image)
    captured_encoding = encode_face(frame)
    if captured_encoding is None or not verify_face(reg_id, captured_encoding):
        return jsonify({'success': False, 'error': 'Face verification failed'})
    
    return jsonify({'success': True})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ========== SOCKET EVENTS ==========
# ========== SOCKET EVENTS ==========
@socketio.on('join_room')
def handle_join_room(faculty_reg_id):
    print(f"Faculty {faculty_reg_id} joined their room")
    join_room(faculty_reg_id)

# Student sends attendance after scanning QR
@socketio.on('attendance')
def handle_attendance(data):
    print("Attendance received:", data)
    faculty_reg_id = data.get('faculty_reg_id')
    if faculty_reg_id:
        emit('attendance', data, room=faculty_reg_id)

    # Prevent duplicates
    existing = Attendance.query.filter_by(
        student_reg_id=data['student_reg_id'],
        faculty_reg_id=data['faculty_reg_id'],
        subject=data['subject']
    ).first()
    if existing:
        print("Duplicate attendance ignored")
        return

    # Save record
    new_entry = Attendance(
        student_reg_id=data['student_reg_id'],
        faculty_reg_id=data['faculty_reg_id'],
        subject=data['subject'],
        timestamp=datetime.utcnow()
    )
    db.session.add(new_entry)
    db.session.commit()

    # Notify faculty dashboard (send clean data)
    emit('attendance', {
        "student_reg_id": data['student_reg_id'],
        "subject": data['subject'],
        "timestamp": new_entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    }, to=str(data['faculty_reg_id']))






@app.route('/verify_face_for_attendance', methods=['POST'])
def verify_face_for_attendance():
    data = request.json
    reg_id = data['student_reg_id']
    face_image_data = data['face_image']

    # Modern SQLAlchemy 2.x: use Session.get
    face_record = db.session.get(FaceEncoding, reg_id)
    if not face_record or not face_record.encoding_blob:
        return jsonify({'success': False, 'error': 'No face encoding found in DB.'})

    # Convert captured base64 image to numpy array
    image_bytes = base64.b64decode(face_image_data.split(",")[1])
    img = Image.open(io.BytesIO(image_bytes))
    img = np.array(img)
    
    # Get face encodings from captured image
    captured_encodings = face_recognition.face_encodings(img)
    if len(captured_encodings) == 0:
        return jsonify({'success': False, 'error': 'No face detected in image.'})
    
    captured_encoding = captured_encodings[0]

    # Load stored encoding
    stored_encoding = pickle.loads(face_record.encoding_blob)

    # Compare faces
    match = face_recognition.compare_faces([stored_encoding], captured_encoding)[0]

    if match:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Face does not match our records.'})

















    

# ========== RUN ==========
if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
