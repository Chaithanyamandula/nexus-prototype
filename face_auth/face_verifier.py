import cv2
import pickle
import face_recognition
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import User, FaceEncoding, db

class FaceVerifier:
    def __init__(self, db_uri, cascade_file="haarcascade_frontalface_default.xml", recognition_threshold=0.45):
        """
        Initialize FaceVerifier with DB and cascade.
        db_uri -> SQLAlchemy DB URI (mysql+pymysql://user:pass@localhost/dbname)
        """
        self.engine = create_engine(db_uri)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.face_cascade = cv2.CascadeClassifier(cascade_file)
        if self.face_cascade.empty():
            raise RuntimeError(f"Could not load cascade file at {cascade_file}")
        self.recognition_threshold = recognition_threshold
        self.dataset_encodings = {}  # {reg_id: (np_encoding, user_obj)}

        self._load_encodings_from_db()

    def _load_encodings_from_db(self):
        """Fetch all user face encodings from DB into memory."""
        self.dataset_encodings.clear()
        records = self.session.query(FaceEncoding).all()
        for record in records:
            try:
                enc = pickle.loads(record.encoding_blob)
                if isinstance(enc, np.ndarray) and enc.size > 0:
                    user = self.session.query(User).filter_by(reg_id=record.reg_id).first()
                    if user:
                        self.dataset_encodings[record.reg_id] = (enc, user)
            except Exception as e:
                print(f"Error loading encoding for {record.reg_id}: {e}")
        print(f"Loaded {len(self.dataset_encodings)} face encodings from database.")

    def capture_face_and_register(self, reg_id):
        """
        Opens webcam, captures the first detected face, stores the encoding in DB for given reg_id.
        Returns True if successful, False otherwise.
        """
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not open webcam.")
            return False

        success = False
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: Could not read frame.")
                break

            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            faces = self.face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            if len(faces) == 0:
                cv2.imshow("Capture Face", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            face_locations = [(y, x+w, y+h, x) for (x, y, w, h) in faces]
            encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            if encodings:
                # Save the first face encoding to DB
                enc_np = encodings[0]

                face_record = FaceEncoding(reg_id=reg_id)
                face_record.set_encoding(enc_np)

                try:
                    self.session.add(face_record)
                    self.session.commit()
                    self.dataset_encodings[reg_id] = (enc_np, self.session.query(User).filter_by(reg_id=reg_id).first())
                    success = True
                    print(f"Face encoding registered for {reg_id}")
                except Exception as e:
                    print(f"Error saving face encoding for {reg_id}: {e}")
                    self.session.rollback()
                break

            cv2.imshow("Capture Face", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()
        return success

    def verify_from_webcam(self):
        """Start webcam and verify faces against database encodings."""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not open webcam.")
            return {}

        recognized_faces = {}

        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: Could not read frame.")
                break

            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            faces = self.face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            face_locations = [(y, x+w, y+h, x) for (x, y, w, h) in faces]
            encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            for i, encoding in enumerate(encodings):
                top, right, bottom, left = face_locations[i]
                best_match_id, best_distance = None, 1.0

                for reg_id, (db_enc, user) in self.dataset_encodings.items():
                    try:
                        distance = face_recognition.face_distance([db_enc], encoding)[0]
                        if distance < best_distance:
                            best_distance = distance
                            best_match_id = reg_id
                    except Exception as e:
                        print(f"Error comparing encoding with {reg_id}: {e}")

                if best_match_id and best_distance < self.recognition_threshold:
                    user = self.dataset_encodings[best_match_id][1]
                    recognized_faces[best_match_id] = user
                    label = f"{user.name} ({user.role})"
                    color = (0, 255, 0)
                else:
                    label = f"Unknown ({best_distance:.2f})"
                    color = (0, 0, 255)

                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(frame, label, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

            cv2.imshow("Face Verifier", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()
        return recognized_faces
