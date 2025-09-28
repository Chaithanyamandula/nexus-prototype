from email.mime.image import MIMEImage
import uuid
import eel
import mysql.connector
import datetime
import smtplib
import random
import string
import hashlib
import cv2
import face_recognition
import pickle
import eel
import os
import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import numpy as np
from mtcnn import MTCNN

eel.init('web')
# Add this near the start of your main.py
import os

# Create required directories
directories = ['criminal_captures', 'criminal_images', 'temp']
for directory in directories:
    os.makedirs(directory, exist_ok=True)

@eel.expose
def init_detection():
    """Initialize detection system and required resources"""
    try:
        # Reset tracking dictionaries
        global criminal_tracking, last_detected_criminals
        criminal_tracking = {}
        last_detected_criminals = {}
        
        # Initialize any required resources
        print("Initializing detection system...")
        
        # Test database connection
        conn = get_db_connection()
        if not conn:
            raise Exception("Failed to connect to database")
        conn.close()
        
        return {"status": "success", "message": "Detection system initialized"}
    except Exception as e:
        print(f"Error initializing detection: {str(e)}")
        return {"status": "error", "message": str(e)}

# MySQL Database setup
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Raja@29282',
    'database': 'cfd'
}


def get_db_connection():
    try:
        print("Connecting to database...")
        conn = mysql.connector.connect(**db_config)
        print("Database connection successful!")
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

# Allowed user IDs for signup
allowed_user_ids = ['user261','user253', 'user254', 'user241','user231','abc']

# Email configuration
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USER = 'criminaldetected@gmail.com'
SMTP_PASSWORD = 'ituo zobk hmuz mgso'

def send_email(to_email, subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SMTP_USER
    msg['To'] = to_email

    try:
        print("Sending email...")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print("Email sent successfully!")
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False

@eel.expose
def check_login(username, password):
    print(f"Checking login for user: {username}")
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and hashlib.sha256(password.encode()).hexdigest() == user['password']:
            print("Login successful!")
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO login_history (user_id, login_time) VALUES (%s, %s)", (username, now))
                conn.commit()
                cursor.close()
                conn.close()
                return True
        else:
            print("Login failed: Invalid credentials")
            return False
    else:
        print("Login failed: Database connection error")
        return False

@eel.expose
def register_user(user_id, name, email, password, re_password):
    print(f"Registering user: {user_id}")
    if user_id not in allowed_user_ids:
        return "Invalid User ID"
    if password != re_password:
        return "Passwords do not match"
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return "User ID already exists"
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute("INSERT INTO users (user_id, name, email, password, signup_time) VALUES (%s, %s, %s, %s, %s)",
                       (user_id, name, email, hashed_password, now))
        conn.commit()
        cursor.close()
        conn.close()
        print("User registered successfully!")
        return True
    else:
        print("User registration failed: Database connection error")
        return "Database connection error"

@eel.expose
def reset_password_request(username_email):
    print(f"Resetting password for: {username_email}")
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM users WHERE user_id = %s OR email = %s", (username_email, username_email))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            email = user[0]
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
            expiry = (datetime.datetime.now() + datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO reset_tokens (email, token, expiry) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE token = %s, expiry = %s", (email, token, expiry, token, expiry))
                conn.commit()
                cursor.close()
                conn.close()

            reset_link = f"http://yourdomain.com/reset_password.html?token={token}"
            body = f"Click this link to reset your password: {reset_link}"

            if send_email(email, "Password Reset Request", body):
                print("Password reset email sent successfully.")
                return "Password reset email sent successfully."
            else:
                print("Failed to send password reset email.")
                return "Failed to send password reset email."
        else:
            print("Invalid username or email.")
            return "Invalid username or email."
    else:
        print("Database connection error.")
        return "Database connection error."

@eel.expose
def reset_password(token, new_password):
    print(f"Resetting password with token: {token}")
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT email, expiry FROM reset_tokens WHERE token = %s", (token,))
        reset_data = cursor.fetchone()

        if reset_data:
            email, expiry = reset_data
            if datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") > expiry:
                cursor.execute("DELETE FROM reset_tokens WHERE token = %s", (token,))
                conn.commit()
                cursor.close()
                conn.close()
                print("Password reset link expired.")
                return "Password reset link expired."

            hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
            cursor.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_password, email))
            cursor.execute("DELETE FROM reset_tokens WHERE token = %s", (token,))
            conn.commit()
            cursor.close()
            conn.close() 
            print("Password reset successfully.")
            return "Password reset successfully."
        else:
            cursor.close()
            conn.close()
            print("Invalid password reset link.")
            return "Invalid password reset link."
    else:
        print("Database connection error.")
        return "Database connection error."

@eel.expose
def logout():
    print("User logged out")
    return True


 
 
@eel.expose
def encode_webcam_faces_to_mysql_eel(images_data, name, crime_details, aadhaar_number):
    """
    Processes multiple images, extracts face encodings, and stores them in MySQL.
    """
    if not aadhaar_number:
        return {"status": "error", "message": "Aadhaar number is required"}

    if not isinstance(aadhaar_number, str) or not aadhaar_number.isdigit() or len(aadhaar_number) != 12:
        return {"status": "error", "message": "Invalid Aadhaar number format"}

    db_config = {
        'host': 'localhost',
        'user': 'root',
        'password': 'Raja@29282',
        'database': 'cfd',
    }

    connection = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        total_faces_stored = 0

        for i, image_data in enumerate(images_data):
            # Decode Base64 to an image
            header, encoded = image_data.split(",", 1)
            image_bytes = base64.b64decode(encoded)

            # Save the image temporarily
            temp_image_path = f"temp_uploaded_image_{i}.jpg"
            with open(temp_image_path, "wb") as f:
                f.write(image_bytes)

            print(f"📸 Processing image {i+1}/{len(images_data)}")

            # Process the image
            image = cv2.imread(temp_image_path)
            if image is None:
                print(f"❌ Error reading image {temp_image_path}")
                continue

            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_image)
            encodings = face_recognition.face_encodings(rgb_image, face_locations)

            if not encodings:
                print(f"⚠️ No face detected in image {i+1}")
                continue

            # Store only the first face encoding
            encoding_bytes = pickle.dumps(encodings[0])

            try:
                # Insert into database with all required fields
                insert_query = """
                INSERT INTO criminals (name, crime_details, encodings, aadhaar_number) 
                VALUES (%s, %s, %s, %s)
                """
                cursor.execute(insert_query, (name, crime_details, encoding_bytes, aadhaar_number))
                total_faces_stored += 1
                print(f"✅ Face {i+1} encoded and stored successfully")
            except mysql.connector.Error as err:
                print(f"❌ Database error while storing face {i+1}: {err}")
                continue
            finally:
                # Clean up temp file
                if os.path.exists(temp_image_path):
                    os.remove(temp_image_path)

        connection.commit()

        if total_faces_stored > 0:
            print(f"✅ Successfully stored {total_faces_stored} face(s) in database")
            return {
                "status": "success", 
                "message": f"Stored {total_faces_stored} face(s) in database"
            }
        else:
            return {
                "status": "error", 
                "message": "No faces were successfully stored"
            }

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {"status": "error", "message": str(e)}

    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


#upload webcam

# ... (Previous imports and code remain unchanged until encode_upload_webcam_faces_to_mysql_eel)
 

 # image criminal search
@eel.expose
def recognize_faces_from_image(image_data):
    """
    Searches for a matching face in the criminal database and returns name, crime details, and photo.
    """
    db_config = {
        'host': 'localhost',
        'user': 'root',
        'password': 'Raja@29282',
        'database': 'cfd',
    }

    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        # Decode Base64 image
        header, encoded = image_data.split(",", 1)
        image_bytes = base64.b64decode(encoded)

        # Save the image temporarily
        temp_image_path = "temp_search_image.jpg"
        with open(temp_image_path, "wb") as f:
            f.write(image_bytes)

        print(f"📸 Processing search image...")

        # Process the image
        image = cv2.imread(temp_image_path)
        if image is None:
            print("❌ Error reading image")
            return {"status": "error", "message": "Error reading image"}

        # Resize image for better face detection
        height, width = image.shape[:2]
        max_dimension = 800  # Maximum dimension for processing
        scale = max_dimension / max(height, width)
        if scale < 1:
            new_width = int(width * scale)
            new_height = int(height * scale)
            image = cv2.resize(image, (new_width, new_height))

        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_image)
        face_encodings = face_recognition.face_encodings(rgb_image, face_locations)

        if not face_encodings:
            print("⚠️ No face detected in search image")
            return {"status": "error", "message": "No face detected in image"}

        # Set recognition threshold
        recognition_threshold = 0.5  # Adjust as needed

        # Retrieve stored encodings from MySQL
        cursor.execute("SELECT name, crime_details, encodings, aadhaar_number FROM criminals")
        records = cursor.fetchall()

        # Initialize best match variables
        best_match_name = None
        best_match_crime_details = None
        best_match_aadhaar_number = None
        best_match_photo_base64 = None
        best_match_confidence = -1.0  # Initialize with a low value

        for row in records:
            stored_name, crime_details, stored_encodings_blob, aadhaar_number = row
            try:
                stored_encoding = pickle.loads(stored_encodings_blob)

                # Ensure stored_encoding is a numpy array with correct shape
                if isinstance(stored_encoding, list):
                    stored_encoding = np.array(stored_encoding)
                if stored_encoding.ndim == 1:
                    stored_encoding = np.array([stored_encoding])

                # Calculate face distances
                face_distances = face_recognition.face_distance(face_encodings, stored_encoding)

                # Check if any face distance is within the threshold
                if len(face_distances) > 0:
                    min_distance = np.min(face_distances)  # Find the smallest distance
                    confidence = 1.0 - min_distance

                    if confidence > best_match_confidence and min_distance <= recognition_threshold:
                        # Update best match
                        best_match_confidence = confidence
                        best_match_name = stored_name
                        best_match_crime_details = crime_details
                        best_match_aadhaar_number = aadhaar_number

                        # Save the matched face without color conversion
                        top, right, bottom, left = face_locations[0]
                        face_image = image[top:bottom, left:right]
                        photo_path = f"criminal_images/{stored_name}.jpg"
                        cv2.imwrite(photo_path, face_image)

                        # Convert the image to base64
                        with open(photo_path, "rb") as img_file:
                            best_match_photo_base64 = base64.b64encode(img_file.read()).decode('utf-8')

            except Exception as e:
                print(f"⚠️ Error processing record for {stored_name}: {e}")
                continue

        if best_match_name and best_match_confidence > 0:  # Ensure a match was found and confidence is above 0
            print(f"✅ Best match found: {best_match_name} with confidence {best_match_confidence}")
            return {
                "status": "success",
                "name": best_match_name,
                "crime": best_match_crime_details,
                "aadhaar_number": best_match_aadhaar_number,
                "photo": best_match_photo_base64,
                "confidence": best_match_confidence
            }

        print("❌ No match found in database")
        return {"status": "error", "message": "No match found"}

    except Exception as e:
        print(f"❌ Error during face recognition: {str(e)}")
        return {"status": "error", "message": f"Error during face recognition: {str(e)}"}

    finally:
        if os.path.exists(temp_image_path):
            os.remove(temp_image_path)
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


 # real time detection    SMTP_SERVER = "smtp.gmail.com"
 


 



# Ensure necessary directories exist
os.makedirs("criminal_captures", exist_ok=True)
os.makedirs("criminal_images", exist_ok=True)

# Initialize MTCNN detector
mtcnn_detector = MTCNN()

# Email Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587  # For TLS
sender_email = "criminaldetected@gmail.com"
sender_password = "ituo zobk hmuz mgso"
receiver_email = "hemanth28292@gmail.com"

# Database Configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Raja@29282',
    'database': 'cfd',
}

# Global Tracking Dictionaries
criminal_tracking = {}
last_detected_criminals = {}

def send_email_with_capture(subject, body, capture_image_path):
    """
    Sends an email with the captured criminal image.
    
    Args:
        subject (str): Email subject
        body (str): Email body text
        capture_image_path (str): Path to the captured image
    """
    try:
        # Create a multipart message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject

        # Attach body text
        msg.attach(MIMEText(body, 'plain'))

        # Attach captured image
        if os.path.exists(capture_image_path):
            with open(capture_image_path, 'rb') as img_file:
                img = MIMEImage(img_file.read(), name=os.path.basename(capture_image_path))
                msg.attach(img)

        # Create SMTP session
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls() #transport layer security
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        print(f" Email sent successfully for {os.path.basename(capture_image_path)}")
        return True
    
    except Exception as e:
        print(f" Email sending failed: {e}")
        return False

def get_db_connection():
    """
    Establishes a connection to the MySQL database.
    
    Returns:
        mysql.connector.connection: Database connection object or None
    """
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

def recognize_faces(frame_rgb, recognition_threshold=0.48, min_matches=1):
    """
    Recognizes faces in the given frame by comparing with criminal database.
    This function has been modified to use MTCNN for more robust face detection
    at various angles.
    """
    # Use the MTCNN detector to find faces at any angle
    mtcnn_results = mtcnn_detector.detect_faces(frame_rgb)
    
    # Check if any faces were detected
    if not mtcnn_results:
        return None, None, None, None, {}

    # Convert MTCNN results to the format face_recognition expects
    face_locations = []
    for result in mtcnn_results:
        x, y, width, height = result['box']
        # The face_recognition library uses (top, right, bottom, left)
        face_locations.append((y, x + width, y + height, x)) 

    face_encodings = face_recognition.face_encodings(frame_rgb, face_locations)

    if not face_encodings:
        return None, None, None, None, {}

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, crime_details, encodings, aadhaar_number FROM criminals")
        records = cursor.fetchall()

        now = datetime.datetime.now()
        
        best_match = None
        best_distance = 1.0
        
        # Iterate through each detected face in the current frame
        for encoding_index, encoding in enumerate(face_encodings):
            
            # Compare the current face encoding to all stored criminal encodings
            for row in records:
                stored_name, crime_details, stored_encodings_blob, aadhaar_number = row
                try:
                    stored_encoding = pickle.loads(stored_encodings_blob)
                    
                    # Ensure stored_encoding is a numpy array with correct shape
                    if isinstance(stored_encoding, list):
                        stored_encoding = np.array(stored_encoding)
                    if stored_encoding.ndim == 1:
                        stored_encoding = np.array([stored_encoding])
                    
                    # Calculate face distance
                    distances = face_recognition.face_distance(stored_encoding, encoding)
                    
                    if len(distances) > 0:
                        min_distance = np.min(distances)
                        if min_distance < recognition_threshold and min_distance < best_distance:
                            best_distance = min_distance
                            best_match = (stored_name, crime_details, face_locations[encoding_index], best_distance, aadhaar_number)
                
                except Exception as e:
                    print(f"Error processing encoding for {stored_name}: {e}")
                    continue

        if best_match:
            stored_name, crime_details, face_location, distance, aadhaar_number = best_match
            timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

            # Capture criminal's image
            top, right, bottom, left = face_location
            criminal_capture = frame_rgb[top:bottom, left:right]
            capture_filename = f"criminal_captures/{stored_name}_{timestamp.replace(':', '-')}.jpg"
            cv2.imwrite(capture_filename, cv2.cvtColor(criminal_capture, cv2.COLOR_RGB2BGR))

            # Convert capture to base64
            photo_base64 = ""
            if os.path.exists(capture_filename):
                with open(capture_filename, "rb") as img_file:
                    photo_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            
            cursor.close()
            conn.close()
            return stored_name, crime_details, photo_base64, face_location, str(uuid.uuid4()), aadhaar_number

        cursor.close()
        conn.close()
    return None, None, None, None, {}

# Add these globals at the top of the file
criminal_timeouts = {}
TIMEOUT_THRESHOLD = 5  # seconds

@eel.expose
def process_camera_frame(image_data):
    try:
        header, encoded = image_data.split(",", 1)
        image_bytes = base64.b64decode(encoded)
        image_np = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
        current_time = datetime.datetime.now()

        if frame is None:
            print("Failed to decode image")
            return {"status": "error", "message": "Failed to decode image."}

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = recognize_faces(frame_rgb)
        
        if len(result) == 6:
            name, crime, photo, face_location, session_id, aadhaar_number = result
            
            # Check if criminal was previously detected
            if name in criminal_timeouts:
                last_detection = criminal_timeouts[name]["last_detection"]
                time_diff = (current_time - last_detection).total_seconds()
                
                # If more than 5 seconds have passed, treat as new detection
                if time_diff > TIMEOUT_THRESHOLD:
                    # Record exit time for previous session
                    exit_time = criminal_timeouts[name]["last_detection"]
                    old_session_id = criminal_timeouts[name]["session_id"]
                    update_tracking_session_exit(name, old_session_id, exit_time)
                    
                    # Create new session for re-entry
                    new_session_id = str(uuid.uuid4())
                    spotted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
                    capture_filename = f"criminal_captures/{name}_{spotted_time.replace(':', '-')}_reentry.jpg"
                    cv2.imwrite(capture_filename, frame)
                    
                    # Create new tracking session
                    create_tracking_session(name, crime, aadhaar_number, current_time, capture_filename, new_session_id)
                    
                    # Update tracking dictionary
                    criminal_timeouts[name] = {
                        "last_detection": current_time,
                        "session_id": new_session_id
                    }
                    
                    # Send new alert
                    alert_data = {
                        "status": "success",
                        "name": name,
                        "crime": crime,
                        "photo": photo,
                        "aadhaar_number": aadhaar_number,
                        "face_location": {
                            "top": face_location[0],
                            "right": face_location[1],
                            "bottom": face_location[2],
                            "left": face_location[3]
                        },
                        "spotted_time": spotted_time,
                        "previous_exit_time": exit_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "session_id": new_session_id,
                        "alert_type": "re-entry"
                    }
                    
                    # Send email notification for re-entry
                    threading.Thread(target=send_email_notification, 
                                  args=(name, crime, aadhaar_number, spotted_time, capture_filename, "Re-entry")).start()
                    
                    return alert_data
                
                else:
                    # Update last detection time
                    criminal_timeouts[name]["last_detection"] = current_time
                    return {"status": "tracking", "name": name}
                
            else:
                # First time detection
                new_session_id = str(uuid.uuid4())
                spotted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
                capture_filename = f"criminal_captures/{name}_{spotted_time.replace(':', '-')}.jpg"
                cv2.imwrite(capture_filename, frame)
                
                # Create new tracking session
                create_tracking_session(name, crime, aadhaar_number, current_time, capture_filename, new_session_id)
                
                criminal_timeouts[name] = {
                    "last_detection": current_time,
                    "session_id": new_session_id
                }
                
                alert_data = {
                    "status": "success",
                    "name": name,
                    "crime": crime,
                    "photo": photo,
                    "aadhaar_number": aadhaar_number,
                    "face_location": {
                        "top": face_location[0],
                        "right": face_location[1],
                        "bottom": face_location[2],
                        "left": face_location[3]
                    },
                    "spotted_time": spotted_time,
                    "session_id": new_session_id,
                    "alert_type": "first_detection"
                }
                
                # Send initial detection email
                threading.Thread(target=send_email_notification, 
                              args=(name, crime, aadhaar_number, spotted_time, capture_filename, "Initial Detection")).start()
                
                return alert_data
        
        # Check for exits (criminals no longer in frame)
        current_criminals = set([name for name in criminal_timeouts.keys()])
        for criminal in list(current_criminals):
            if criminal not in [result[0]] if result and len(result) >= 1 else []:
                time_diff = (current_time - criminal_timeouts[criminal]["last_detection"]).total_seconds()
                if time_diff > TIMEOUT_THRESHOLD:
                    exit_time = criminal_timeouts[criminal]["last_detection"]
                    session_id = criminal_timeouts[criminal]["session_id"]
                    
                    # Update exit time for this session
                    update_tracking_session_exit(criminal, session_id, exit_time)
                    
                    del criminal_timeouts[criminal]
                    return {
                        "status": "exit",
                        "name": criminal,
                        "exit_time": exit_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "session_id": session_id
                    }

        return {"status": "no_match"}

    except Exception as e:
        print(f"Error in process_camera_frame: {str(e)}")
        return {"status": "error", "message": f"Detection error: {str(e)}"}

def send_email_notification(name, crime, aadhaar_number, detection_time, capture_filename, alert_type):
    email_subject = f"⚠️ Criminal Alert: {name} {alert_type}!"
    email_body = f"""
URGENT: Criminal {alert_type}!

Details:
- Name: {name}
- Crime: {crime}
- Aadhaar Number: {aadhaar_number}
- Detection Time: {detection_time}
- Location: Security Camera 1

This is an automated alert. Please take immediate action.
"""
    send_email_with_capture(email_subject, email_body, capture_filename)

# Add near your other eel.expose functions
@eel.expose
def cleanup_detection():
    """Cleanup detection resources"""
    try:
        # Reset tracking dictionaries
        global criminal_tracking, last_detected_criminals
        criminal_tracking = {}
        last_detected_criminals = {}
        
        # Release any opencv windows if they exist
        cv2.destroyAllWindows()
        return {"status": "success", "message": "Detection cleanup successful"}
    except Exception as e:
        print(f"Error during cleanup: {str(e)}")
        return {"status": "error", "message": str(e)}

@eel.expose
def start_detection():
    return True

@eel.expose
def get_detected_records():
    """
    Fetches detected criminal records from the database, grouped by date.
    """
    conn = get_db_connection()
    if not conn:
        return {"status": "error", "message": "Database connection error"}

    cursor = conn.cursor(dictionary=True)
    try:
        query_dates = """
        SELECT DISTINCT DATE(start) AS detection_date
        FROM criminal_tracking_sessions
        ORDER BY detection_date DESC
        """
        cursor.execute(query_dates)
        dates = cursor.fetchall()

        records_by_date = {}
        for date_data in dates:
            detection_date = date_data['detection_date'].strftime('%Y-%m-%d')
            query_records = """
            SELECT 
                id,
                name, 
                crime_details, 
                aadhaar_number, 
                start, 
                end, 
                photo_path,
                session_id
            FROM criminal_tracking_sessions
            WHERE DATE(start) = %s
            ORDER BY start DESC
            """
            cursor.execute(query_records, (detection_date,))
            records = cursor.fetchall()

            processed_records = []
            for record in records:
                # Process photo
                photo_data = None
                if record['photo_path'] and os.path.exists(record['photo_path']):
                    try:
                        with open(record['photo_path'], 'rb') as img_file:
                            photo_bytes = img_file.read()
                            photo_data = f"data:image/jpeg;base64,{base64.b64encode(photo_bytes).decode('utf-8')}"
                    except Exception as e:
                        print(f"Error reading image {record['photo_path']}: {e}")

                # Format entry/exit times
                processed_record = {
                    'id': record['id'],
                    'name': record['name'],
                    'crime_details': record['crime_details'],
                    'aadhaar_number': record['aadhaar_number'],
                    'start_time': record['start'].strftime('%Y-%m-%d %H:%M:%S') if record['start'] else None,
                    'end_time': record['end'].strftime('%Y-%m-%d %H:%M:%S') if record['end'] else 'Still Active',
                    'photo_data': photo_data,
                    'session_id': record['session_id']
                }
                processed_records.append(processed_record)

            records_by_date[detection_date] = processed_records

        return {"status": "success", "data": records_by_date}

    except Exception as e:
        print(f"Error fetching detected records: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def create_tracking_session(name, crime, aadhaar_number, start_time, photo_path, session_id):
    """
    Creates a new criminal tracking session in the database.
    """
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            insert_query = """
            INSERT INTO criminal_tracking_sessions 
            (name, crime_details, aadhaar_number, start, photo_path, session_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (name, crime, aadhaar_number, start_time, photo_path, session_id))
            conn.commit()
            print(f"✅ Created new tracking session for {name}")
            return True
        except Exception as e:
            print(f"❌ Error creating tracking session: {e}")
            return False
        finally:
            cursor.close()
            conn.close()

def update_tracking_session_exit(name, session_id, exit_time):
    """
    Updates the exit time for a specific tracking session of a criminal.
    """
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            update_query = """
            UPDATE criminal_tracking_sessions 
            SET end = %s 
            WHERE name = %s 
            AND session_id = %s
            """
            cursor.execute(update_query, (exit_time, name, session_id))
            conn.commit()
            print(f"✅ Updated exit time for {name} session {session_id}")
            return True
        except Exception as e:
            print(f"❌ Error updating exit time: {e}")
            return False
        finally:
            cursor.close()
            conn.close()

# Start the Eel application
 
 

eel.init('web')

# Start the application with a single window
eel.start('login.html', 
    size=(1200, 800),
    port=8000,
    mode='chrome',
    block=True  # This ensures only one window is used
)
