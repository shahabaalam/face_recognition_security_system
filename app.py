import os
import cv2
import numpy as np
import streamlit as st
import face_recognition
import pickle
import time
import datetime
import pandas as pd
from io import StringIO

# System Configuration
DATABASE_FILE = "face_database.pkl"
ACCESS_LOG_FILE = "access_log.csv"
ADMIN_PASSWORD = "admin123"
FALLBACK_PIN = "123456"  # Default PIN for fallback access
RFID_DATABASE = {"card1": "Admin", "card2": "Guest"}  # Simulated RFID database

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'appliances' not in st.session_state:
    st.session_state.appliances = {
        "Light": False,
        "Security System": False,
        "Smart TV": False
    }
if 'simulation_mode' not in st.session_state:
    st.session_state.simulation_mode = True  # Start in simulation mode
if 'access_logs' not in st.session_state:
    st.session_state.access_logs = []
if 'alerts' not in st.session_state:
    st.session_state.alerts = []
if 'system_status' not in st.session_state:
    st.session_state.system_status = {
        "uptime": time.time(),
        "battery_backup": False,
        "last_self_heal": None,
        "faults": 0,
        "battery_depletion_time": None  # Track when battery will deplete
    }
if 'clear_db_mode' not in st.session_state:  # NEW: Track clear database state
    st.session_state.clear_db_mode = False

# Initialize face database
def load_database():
    try:
        if os.path.exists(DATABASE_FILE) and os.path.getsize(DATABASE_FILE) > 0:
            with open(DATABASE_FILE, 'rb') as f:
                return pickle.load(f)
    except Exception as e:
        st.error(f"Error loading database: {e}")
        log_event("System Error", f"Database load failed: {str(e)}")
    return {}

def save_database(db):
    try:
        with open(DATABASE_FILE, 'wb') as f:
            pickle.dump(db, f)
    except Exception as e:
        st.error(f"Error saving database: {e}")
        log_event("System Error", f"Database save failed: {str(e)}")

# Event Logging
def log_event(event_type, details, user="System"):
    """Log security events"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{timestamp},{event_type},{user},{details}"
    
    # Add to session state
    st.session_state.access_logs.append(entry)
    
    # Save to file
    try:
        with open(ACCESS_LOG_FILE, "a") as f:
            f.write(entry + "\n")
    except Exception as e:
        st.error(f"Error saving log: {e}")

# Alert System
def send_alert(message, level="warning"):
    """Send real-time alerts"""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    alert = {
        "time": timestamp,
        "message": message,
        "level": level,
        "acknowledged": False
    }
    st.session_state.alerts.append(alert)
    
    # Visual notification
    st.toast(f"ALERT: {message}", icon="⚠️" if level == "warning" else "🚨")

# Battery Backup Simulation - MODIFIED TO WORK IN MAIN THREAD
def simulate_power_outage():
    """Simulate power failure and battery backup"""
    if not st.session_state.system_status["battery_backup"]:
        st.session_state.system_status["battery_backup"] = True
        st.session_state.system_status["battery_depletion_time"] = time.time() + 300  # 5 minutes
        send_alert("Power outage detected! Switching to battery backup", "critical")
        log_event("System Event", "Power failure - battery backup activated")
        
        # Disable non-essential features
        if st.session_state.appliances["Smart TV"]:
            control_tv(False)
            send_alert("Non-essential devices disabled to conserve power", "warning")

# Battery depletion check - CALLED FROM MAIN THREAD
def check_battery_status():
    """Check if battery has depleted"""
    if st.session_state.system_status["battery_backup"]:
        depletion_time = st.session_state.system_status["battery_depletion_time"]
        if depletion_time and time.time() >= depletion_time:
            st.session_state.system_status["battery_backup"] = False
            st.session_state.system_status["battery_depletion_time"] = None
            send_alert("Battery depleted! System shutting down", "critical")
            log_event("System Event", "Battery depleted - system shutdown")
            
            # Disable all appliances
            if st.session_state.appliances["Light"]:
                control_light(False)
            if st.session_state.appliances["Security System"]:
                control_security_system(False)
            if st.session_state.appliances["Smart TV"]:
                control_tv(False)

# Self-Healing System
def self_heal():
    """Simulate self-healing capabilities"""
    log_event("System Event", "Self-healing initiated")
    st.session_state.system_status["faults"] = 0
    st.session_state.system_status["last_self_heal"] = time.time()
    
    # Simulate recovery actions
    if not st.session_state.system_status["battery_backup"]:
        st.session_state.system_status["battery_backup"] = True
        send_alert("System recovered from fault condition", "info")
    
    log_event("System Event", "Self-healing completed successfully")

# Uptime Monitoring
def get_uptime():
    """Calculate and format system uptime"""
    uptime_seconds = time.time() - st.session_state.system_status["uptime"]
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

# Fault Tolerance
def handle_camera_failure():
    """Simulate camera fault recovery"""
    log_event("System Error", "Camera failure detected")
    st.session_state.system_status["faults"] += 1
    
    if st.session_state.system_status["faults"] >= 3:
        send_alert("Critical hardware failure detected", "critical")
        self_heal()

# Fallback Authentication Methods
def pin_authentication():
    st.header("PIN Authentication")
    pin = st.text_input("Enter 6-digit PIN", type="password", max_chars=6)
    
    if st.button("Authenticate with PIN"):
        if pin == FALLBACK_PIN:
            st.session_state.authenticated = True
            st.session_state.current_user = "Fallback User"
            log_event("Access", "PIN authentication successful")
            st.success("Access Granted via PIN!")
        else:
            log_event("Security Alert", "Invalid PIN attempt")
            send_alert("Invalid PIN attempt detected", "warning")
            st.error("Invalid PIN")

def rfid_authentication():
    st.header("RFID Authentication")
    rfid_id = st.selectbox("Select RFID Card", list(RFID_DATABASE.keys()))
    
    if st.button("Authenticate with RFID"):
        user = RFID_DATABASE.get(rfid_id)
        if user:
            st.session_state.authenticated = True
            st.session_state.current_user = user
            log_event("Access", f"RFID authentication successful: {user}")
            st.success(f"Access Granted to {user} via RFID!")
        else:
            log_event("Security Alert", "Invalid RFID card used")
            send_alert("Unauthorized RFID access attempt", "warning")
            st.error("Invalid RFID Card")

# Face Registration with Admin Password
def register_face():
    st.header("Admin Face Registration")
    
    # Admin password check
    admin_pass = st.text_input("Enter Admin Password", type="password")
    if not admin_pass:
        st.warning("Please enter admin password to register")
        return
    
    if admin_pass != ADMIN_PASSWORD:
        st.error("Incorrect admin password. Access denied.")
        log_event("Security Alert", "Admin password verification failed")
        return
    
    user_name = st.text_input("Enter name for registration")
    
    if not user_name:
        st.warning("Please enter the name for registration")
        return
    
    st.markdown("""
    ### Registration Instructions:
    1. Position yourself in good lighting
    2. Look straight at the camera
    3. Keep your face centered in the frame
    4. Hold still for 2 seconds while we scan
    """)
    
    if st.button("Start Face Scan"):
        with st.spinner("Scanning your face..."):
            try:
                video_capture = cv2.VideoCapture(0)
                if not video_capture.isOpened():
                    raise Exception("Camera not available")
            except Exception as e:
                st.error(f"Camera error: {str(e)}")
                log_event("System Error", f"Camera access failed: {str(e)}")
                handle_camera_failure()
                return
                
            frame_count = 0
            best_face_encoding = None
            best_face_score = 0
            scan_complete = False
            
            scan_placeholder = st.empty()
            status_placeholder = st.empty()
            
            while not scan_complete:
                ret, frame = video_capture.read()
                if not ret:
                    st.error("Failed to access camera")
                    log_event("System Error", "Camera frame capture failed")
                    handle_camera_failure()
                    break
                
                # Convert to RGB for face recognition
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Find faces in the frame
                face_locations = face_recognition.face_locations(rgb_frame)
                
                if face_locations:
                    # Get face encodings
                    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
                    
                    for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                        # Draw rectangle around face
                        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                        
                        # Calculate face quality score
                        face_size = (right - left) * (bottom - top)
                        center_x = (left + right) / 2
                        center_y = (top + bottom) / 2
                        frame_center_x = frame.shape[1] / 2
                        frame_center_y = frame.shape[0] / 2
                        distance_to_center = np.sqrt((center_x - frame_center_x)**2 + (center_y - frame_center_y)**2)
                        score = face_size / (distance_to_center + 1)
                        
                        # Keep the best face encoding
                        if score > best_face_score:
                            best_face_score = score
                            best_face_encoding = face_encoding
                        
                        # Display quality score
                        cv2.putText(frame, f"Quality: {score:.1f}", (left, bottom + 30),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Display the frame
                scan_placeholder.image(frame, channels="BGR", use_container_width=True)
                
                frame_count += 1
                
                # Stop after collecting enough good frames
                if frame_count >= 30 and best_face_score > 500:
                    scan_complete = True
            
            # Release resources
            video_capture.release()
            
            # Save the best face encoding
            if best_face_encoding is not None:
                database = load_database()
                database[user_name] = best_face_encoding
                save_database(database)
                status_placeholder.success(f"Successfully registered {user_name}!")
                log_event("Admin Action", f"Registered new user: {user_name}")
            else:
                status_placeholder.error("No good face detected. Please try again with better lighting.")
                log_event("System Event", "Face registration failed - low quality")

# Face Authentication
def authenticate_face():
    st.header("Face Authentication")
    st.markdown("""
    ### Authentication Instructions:
    1. Look straight at the camera
    2. Make sure your face is clearly visible
    3. Hold still for recognition
    """)
    
    if st.button("Start Authentication"):
        with st.spinner("Authenticating..."):
            try:
                video_capture = cv2.VideoCapture(0)
                if not video_capture.isOpened():
                    raise Exception("Camera not available")
            except Exception as e:
                st.error(f"Camera error: {str(e)}")
                log_event("System Error", f"Camera access failed: {str(e)}")
                handle_camera_failure()
                return
                
            database = load_database()
            auth_placeholder = st.empty()
            status_placeholder = st.empty()
            authenticated = False
            recognized_name = None
            
            for _ in range(30):
                ret, frame = video_capture.read()
                if not ret:
                    st.error("Failed to access camera")
                    log_event("System Error", "Camera frame capture failed")
                    handle_camera_failure()
                    break
                
                # Convert to RGB for face recognition
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Find faces in the frame
                face_locations = face_recognition.face_locations(rgb_frame)
                
                if face_locations:
                    # Get face encodings
                    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
                    
                    for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                        # Compare with known faces
                        matches = face_recognition.compare_faces(
                            list(database.values()), 
                            face_encoding,
                            tolerance=0.5
                        )
                        
                        name = "Unknown"
                        if True in matches:
                            first_match_index = matches.index(True)
                            name = list(database.keys())[first_match_index]
                            authenticated = True
                            recognized_name = name
                        
                        # Draw rectangle and label
                        color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
                        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                        cv2.putText(frame, name, (left, top - 10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
                        
                        # Log intruder detection
                        if name == "Unknown":
                            log_event("Security Alert", "Unauthorized face detected")
                            send_alert("Intruder alert! Unknown face detected", "critical")
                
                # Display the frame
                auth_placeholder.image(frame, channels="BGR", use_container_width=True)
                
                if authenticated:
                    st.session_state.authenticated = True
                    st.session_state.current_user = recognized_name
                    status_placeholder.success(f"Access Granted! Welcome {recognized_name}!")
                    log_event("Access", f"Face authentication successful: {recognized_name}")
                    break
            
            video_capture.release()
            
            if not authenticated:
                status_placeholder.error("Access Denied: Face not recognized")
                log_event("Access", "Face authentication failed")
                send_alert("Authentication failed", "warning")

# Appliance Control Functions
def control_light(state):
    """Control light - simulation mode or real GPIO"""
    if st.session_state.system_status["battery_backup"]:
        st.warning("Battery mode: Lighting control disabled")
        return False
        
    if st.session_state.simulation_mode:
        st.info(f"SIMULATION: Light would be {'ON' if state else 'OFF'}")
        log_event("Appliance Control", f"Light turned {'ON' if state else 'OFF'}")
        return True
    else:
        # Real GPIO control would go here
        st.success(f"Light turned {'ON' if state else 'OFF'}")
        log_event("Appliance Control", f"Light turned {'ON' if state else 'OFF'}")
        return True

def control_security_system(state):
    """Control security system - simulation mode or real GPIO"""
    if st.session_state.simulation_mode:
        st.info(f"SIMULATION: Security system would be {'ARMED' if state else 'DISARMED'}")
        log_event("Appliance Control", f"Security system {'ARMED' if state else 'DISARMED'}")
        return True
    else:
        # Real GPIO control would go here
        st.success(f"Security system {'ARMED' if state else 'DISARMED'}")
        log_event("Appliance Control", f"Security system {'ARMED' if state else 'DISARMED'}")
        return True

def control_tv(state):
    """Control TV - simulation mode or real GPIO"""
    if st.session_state.system_status["battery_backup"]:
        st.warning("Battery mode: Non-essential devices disabled")
        return False
        
    if st.session_state.simulation_mode:
        st.info(f"SIMULATION: TV would be {'ON' if state else 'OFF'}")
        log_event("Appliance Control", f"TV turned {'ON' if state else 'OFF'}")
        return True
    else:
        # Real GPIO control would go here
        st.success(f"TV turned {'ON' if state else 'OFF'}")
        log_event("Appliance Control", f"TV turned {'ON' if state else 'OFF'}")
        return True

# Home Control Interface
def home_control():
    st.header("Smart Home Control Panel")
    st.subheader(f"Welcome, {st.session_state.current_user}!")
    
    # Check battery status (main thread safe)
    check_battery_status()
    
    # Display system status
    status_cols = st.columns(3)
    with status_cols[0]:
        st.metric("Uptime", get_uptime())
    with status_cols[1]:
        battery_status = "Active" if st.session_state.system_status["battery_backup"] else "Inactive"
        st.metric("Battery Backup", battery_status)
    with status_cols[2]:
        st.metric("System Faults", st.session_state.system_status["faults"])
    
    # Display mode status
    mode_status = "Simulation Mode" if st.session_state.simulation_mode else "Real Device Mode"
    st.info(f"System Status: {mode_status}")
    
    # Store previous states
    prev_states = st.session_state.appliances.copy()
    
    st.markdown("### Appliance Controls")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Lighting")
        # Disable control during battery backup
        disabled = st.session_state.system_status["battery_backup"]
        st.session_state.appliances["Light"] = st.toggle(
            "Living Room Lights", 
            value=st.session_state.appliances["Light"],
            key="light_toggle",
            disabled=disabled
        )
        
    with col2:
        st.markdown("#### Security")
        st.session_state.appliances["Security System"] = st.toggle(
            "Alarm System", 
            value=st.session_state.appliances["Security System"],
            key="security_toggle"
        )
        
        st.markdown("#### Entertainment")
        # Disable control during battery backup
        disabled = st.session_state.system_status["battery_backup"]
        st.session_state.appliances["Smart TV"] = st.toggle(
            "Smart TV", 
            value=st.session_state.appliances["Smart TV"],
            key="tv_toggle",
            disabled=disabled
        )
    
    # Check for state changes and control devices
    if prev_states["Light"] != st.session_state.appliances["Light"]:
        if not control_light(st.session_state.appliances["Light"]):
            st.session_state.appliances["Light"] = prev_states["Light"]
    
    if prev_states["Security System"] != st.session_state.appliances["Security System"]:
        control_security_system(st.session_state.appliances["Security System"])
    
    if prev_states["Smart TV"] != st.session_state.appliances["Smart TV"]:
        if not control_tv(st.session_state.appliances["Smart TV"]):
            st.session_state.appliances["Smart TV"] = prev_states["Smart TV"]
    
    # Display status panel
    st.divider()
    st.markdown("### Current Status")
    
    # Create visual indicators for appliance status
    status_cols = st.columns(3)
    
    with status_cols[0]:
        st.markdown("#### Lighting")
        if st.session_state.appliances["Light"]:
            st.success("ON")
        else:
            st.error("OFF")
            
    with status_cols[1]:
        st.markdown("#### Security")
        if st.session_state.appliances["Security System"]:
            st.success("ARMED")
        else:
            st.error("DISARMED")
            
    with status_cols[2]:
        st.markdown("#### TV")
        if st.session_state.appliances["Smart TV"]:
            st.success("ON")
        else:
            st.error("OFF")
    
    # Access Logs
    st.divider()
    st.markdown("### Access Logs")
    if st.session_state.access_logs:
        # Create DataFrame from logs
        log_data = [log.split(",", 3) for log in st.session_state.access_logs[-10:]]  # Last 10 entries
        log_df = pd.DataFrame(log_data, columns=["Timestamp", "Event", "User", "Details"])
        st.dataframe(log_df)
    else:
        st.info("No access events recorded")
    
    # Active Alerts
    st.divider()
    st.markdown("### Active Alerts")
    unacknowledged = [alert for alert in st.session_state.alerts if not alert["acknowledged"]]
    
    if unacknowledged:
        for i, alert in enumerate(unacknowledged):
            cols = st.columns([1, 4, 1])
            cols[0].write(alert["time"])
            if alert["level"] == "warning":
                cols[1].warning(alert["message"])
            else:
                cols[1].error(alert["message"])
            if cols[2].button("Ack", key=f"ack_{i}"):
                alert["acknowledged"] = True
                st.rerun()
    else:
        st.success("No active alerts")
    
    # Logout button
    st.divider()
    if st.button("Logout", type="primary"):
        log_event("Access", "User logged out")
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.success("You have been logged out successfully!")
        time.sleep(2)
        st.rerun()

# Main Application
st.title("Smart Security Hub with Face Recognition")

# Navigation
if st.session_state.authenticated:
    home_control()
else:
    mode = st.sidebar.selectbox("Select Mode", 
                               ["Authenticate", 
                                "PIN Access", 
                                "RFID Access",
                                "Register Face (Admin Only)"])
    
    if mode == "Register Face (Admin Only)":
        register_face()
    elif mode == "Authenticate":
        authenticate_face()
    elif mode == "PIN Access":
        pin_authentication()
    elif mode == "RFID Access":
        rfid_authentication()

# Admin Functions
st.sidebar.divider()
st.sidebar.markdown("### Admin Tools")

# Simulation mode toggle
simulation_mode = st.sidebar.toggle(
    "Simulation Mode", 
    value=st.session_state.simulation_mode,
    key="simulation_toggle"
)
st.session_state.simulation_mode = simulation_mode

# System Simulation Controls
st.sidebar.markdown("#### System Simulation")
if st.sidebar.button("Simulate Power Outage"):
    simulate_power_outage()
    st.rerun()

if st.sidebar.button("Restore Power"):
    if st.session_state.system_status["battery_backup"]:
        st.session_state.system_status["battery_backup"] = False
        st.session_state.system_status["battery_depletion_time"] = None
        log_event("System Event", "Power restored")
        send_alert("Main power restored", "info")
        st.rerun()

if st.sidebar.button("Trigger Self-Healing"):
    self_heal()
    st.rerun()

# Clear database button - FIXED SECTION
if st.sidebar.button("Clear Database"):
    st.session_state.clear_db_mode = True

if st.session_state.clear_db_mode:
    admin_pass = st.sidebar.text_input("Confirm Admin Password", type="password", key="clear_db_pass")
    confirm_col, cancel_col = st.sidebar.columns(2)
    
    if confirm_col.button("Confirm Clear"):
        if admin_pass == ADMIN_PASSWORD:
            save_database({})
            log_event("Admin Action", "Database cleared")
            st.sidebar.success("Database cleared successfully")
            st.session_state.clear_db_mode = False
            st.rerun()
        else:
            st.sidebar.error("Incorrect admin password")
            log_event("Security Alert", "Failed database clear attempt")
    
    if cancel_col.button("Cancel"):
        st.session_state.clear_db_mode = False
        st.rerun()

# Export logs button
if st.sidebar.button("Export Access Logs"):
    try:
        with open(ACCESS_LOG_FILE, "r") as f:
            log_content = f.read()
        st.sidebar.download_button(
            label="Download Logs",
            data=log_content,
            file_name="security_logs.csv",
            mime="text/csv"
        )
    except Exception as e:
        st.sidebar.error(f"Error exporting logs: {e}")

# Display current user status
st.sidebar.divider()
if st.session_state.authenticated:
    st.sidebar.success(f"Logged in as: {st.session_state.current_user}")
else:
    st.sidebar.warning("Not authenticated")

# System status summary
st.sidebar.divider()
st.sidebar.markdown("### System Status")
st.sidebar.metric("Uptime", get_uptime())
battery_status = "🟢 Active" if st.session_state.system_status["battery_backup"] else "⚪ Inactive"
st.sidebar.markdown(f"**Battery Backup:** {battery_status}")
st.sidebar.metric("System Faults", st.session_state.system_status["faults"])

# Initialize log file
if not os.path.exists(ACCESS_LOG_FILE):
    with open(ACCESS_LOG_FILE, "w") as f:
        f.write("Timestamp,Event,User,Details\n")
    log_event("System Event", "Log file initialized")