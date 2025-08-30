import sys, os, cv2, time, json, sqlite3, threading, subprocess
import numpy as np
import pyttsx3
import face_recognition
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort
from PyQt5 import QtWidgets, QtCore, QtGui
import pandas as pd
from flask import Flask, jsonify, request

# --------------------
# Configuración global
# --------------------
DB_PATH = "people.db"
CAMERA_CONFIG = "cameras.json"
UPLOAD_ENABLED = False  # activar si quieres rclone/boto3
ALERT_COOLDOWN = 10     # seg entre alertas de un desconocido

# --------------------
# Detector YOLOv8 + tracker
# --------------------
model = YOLO("yolov8n.pt")
tracker = DeepSort(max_age=30)

# --------------------
# Text-to-Speech
# --------------------
engine = pyttsx3.init()
engine.setProperty("rate", 170)

def speak_alert(msg):
    engine.say(msg)
    engine.runAndWait()

# --------------------
# Reconocimiento facial
# --------------------
def load_known_faces():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, role, face_path FROM persons WHERE face_path IS NOT NULL")
    rows = c.fetchall()
    conn.close()

    known_encodings, known_meta = [], []
    for pid, name, role, face_path in rows:
        if os.path.exists(face_path):
            img = face_recognition.load_image_file(face_path)
            encs = face_recognition.face_encodings(img)
            if encs:
                known_encodings.append(encs[0])
                known_meta.append((pid, name, role))
    return known_encodings, known_meta

known_encodings, known_meta = load_known_faces()

def identify_face(frame, box):
    # box formato xyxy
    x1, y1, x2, y2 = [int(v) for v in box]
    face_img = frame[y1:y2, x1:x2]
    rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
    encs = face_recognition.face_encodings(rgb)
    if encs:
        matches = face_recognition.compare_faces(known_encodings, encs[0], tolerance=0.45)
        if True in matches:
            idx = matches.index(True)
            return known_meta[idx][1]  # nombre
    return "Desconocido"

# --------------------
# DB utils
# --------------------
def log_event(camera_id, person_name, role):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO events (timestamp, camera, person, role) VALUES (?,?,?,?)",
              (time.strftime("%Y-%m-%d %H:%M:%S"), camera_id, person_name, role))
    conn.commit()
    conn.close()

# --------------------
# Cámara Worker
# --------------------
class CameraWorker(QtCore.QThread):
    frame_ready = QtCore.pyqtSignal(np.ndarray)

    def __init__(self, cam_id, url):
        super().__init__()
        self.cam_id = cam_id
        self.url = url
        self.running = True
        self.last_alert = 0

    def run(self):
        cap = cv2.VideoCapture(self.url)
        while self.running:
            ret, frame = cap.read()
            if not ret: break

            # YOLO detecciones
            results = model(frame)
            detections = []
            for r in results:
                for box, score, cls in zip(r.boxes.xyxy, r.boxes.conf, r.boxes.cls):
                    if int(cls) == 0 and score > 0.5:  # persona
                        x1,y1,x2,y2 = map(int, box.tolist())
                        detections.append([x1,y1,x2,y2,float(score), int(cls)])

            # Tracking
            tracks = tracker.update_tracks(detections, frame=frame)
            for t in tracks:
                if not t.is_confirmed(): continue
                x1,y1,x2,y2 = map(int, t.to_ltrb())
                person_name = identify_face(frame, (x1,y1,x2,y2))
                role = "Desconocido"
                if person_name != "Desconocido":
                    role = "Empleado"
                else:
                    # alerta sonora con cooldown
                    if time.time() - self.last_alert > ALERT_COOLDOWN:
                        threading.Thread(target=speak_alert, args=(f"Alerta: persona desconocida en cámara {self.cam_id}",)).start()
                        self.last_alert = time.time()

                # Log
                log_event(self.cam_id, person_name, role)

                # Dibujo hitbox
                cv2.rectangle(frame, (x1,y1), (x2,y2), (0,255,0), 2)
                cv2.putText(frame, f"{person_name} ({role})", (x1,y1-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)

            self.frame_ready.emit(frame)

        cap.release()

    def stop(self):
        self.running = False

# --------------------
# Dashboard PyQt5
# --------------------
class CCTVApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CCTV Inteligente")
        self.resize(1200, 800)

        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        # Carga cámaras
        with open(CAMERA_CONFIG) as f:
            self.cameras = json.load(f)

        for cid, url in self.cameras.items():
            lbl = QtWidgets.QLabel()
            lbl.setScaledContents(True)
            self.tabs.addTab(lbl, f"Cámara {cid}")

            worker = CameraWorker(cid, url)
            worker.frame_ready.connect(lambda f, l=lbl: self.update_frame(l, f))
            worker.start()

    def update_frame(self, label, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h,w,ch = rgb.shape
        img = QtGui.QImage(rgb.data, w,h,ch*w, QtGui.QImage.Format_RGB888)
        label.setPixmap(QtGui.QPixmap.fromImage(img))

# --------------------
# API Flask para dashboard web
# --------------------
app_flask = Flask(__name__)

@app_flask.route("/api/events")
def api_events():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM events ORDER BY id DESC LIMIT 100", conn)
    conn.close()
    return df.to_json(orient="records")

def run_flask():
    app_flask.run(host="0.0.0.0", port=5000)

# --------------------
# Main
# --------------------
if __name__ == "__main__":
    # Levantar Flask en hilo aparte
    threading.Thread(target=run_flask, daemon=True).start()

    app = QtWidgets.QApplication(sys.argv)
    win = CCTVApp()
    win.show()
    sys.exit(app.exec_())