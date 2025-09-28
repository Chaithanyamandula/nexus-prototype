from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# ========== USER TABLE ==========
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), nullable=False)        # 'student' or 'faculty'
    name = db.Column(db.String(100), nullable=False)
    reg_id = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    mobile = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.name} ({self.role})>"

# ========== FACE ENCODING TABLE ==========
class FaceEncoding(db.Model):
    __tablename__ = 'face_encodings'
    reg_id = db.Column(db.String(50), db.ForeignKey('users.reg_id'), primary_key=True)
    encoding_blob = db.Column(db.LargeBinary, nullable=True)  # Store pickled face encoding

    user = db.relationship('User', backref=db.backref('face_encoding', uselist=False))

    def __repr__(self):
        return f"<FaceEncoding {self.reg_id}>"

# ========== ATTENDANCE TABLE ==========
class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    student_reg_id = db.Column(db.String(50), db.ForeignKey('users.reg_id'))
    subject = db.Column(db.String(100))
    faculty_reg_id = db.Column(db.String(50), db.ForeignKey('users.reg_id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('User', foreign_keys=[student_reg_id], backref='attendances')
    faculty = db.relationship('User', foreign_keys=[faculty_reg_id])

    def __repr__(self):
        return f"<Attendance {self.student_reg_id} - {self.subject} - {self.timestamp}>"
