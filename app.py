import os
import sys
import json
import time
import sqlite3
import threading
import subprocess
from pathlib import Path
from collections import deque
import cv2
import numpy as np
from ultralytics import YOLO
import pyttsx3
import pandas as pd
import requests

# PyQt5 imports
from PyQt5 import QtWidgets, QtGui, QtCore
from flask import Flask, jsonify

# Face recognition
import face_recognition

# Tracker imports (selectable)
TRACKER = os.getenv("TRACKER", "deepsort").lower()  # 'deepsort' or 'bytetrack'

# try to import ByteTrack if requested
bytetrack_available = False
if TRACKER == "bytetrack":
    try:
        # after pip-install from GitHub, module path may vary; try common ones
        from yolox.tracker.byte_tracker import BYTETracker
        from yolox.tracker.tracker_config import TrackerConfig
        bytetrack_available = True
    except Exception:
        try:
            # alternate name
            from bytetrack.byte_tracker import BYTETracker
            bytetrack_available = True
        except Exception:
            bytetrack_available = False

# deep-sort import fallback
try:
    from deep_sort_realtime.deepsort_tracker import DeepSort
    deepsort_available = True
except Exception:
    deepsort_available = False

# Paths
BASE = Path(__file__).parent
DB_PATH = BASE / "people.db"
CAM_CONF = BASE / "cameras.json"
FACES_DIR = BASE / "faces"
EVID_DIR = BASE / "evidencias"
RECORD_DIR = BASE / "recordings"
REPORTS_DIR = BASE / "reports"
for p in (FACES_DIR, EVID_DIR, RECORD_DIR, REPORTS_DIR):
    p.mkdir(parents=True, exist_ok=True)

# Config
ALERT_COOLDOWN = 8
BUFFER_SECONDS = 30
MODEL_WEIGHTS = os.getenv("YOLO_WEIGHTS", "yolov8n.pt")
UPLOAD_METHOD = os.getenv("UPLOAD_METHOD", "")  # 'rclone' or 's3'
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT", "")

# Load model
print("Loading YOLO model:", MODEL_WEIGHTS)
model = YOLO(MODEL_WEIGHTS)

# Tracker wrapper
class TrackerWrapper:
    def __init__(self):
        self.type = TRACKER
        if TRACKER == "bytetrack" and bytetrack_available:
            try:
                # create ByteTrack with default params (user can tune)
                self.tracker = BYTETracker()
                self.mode = "bytetrack"
                print("Tracker: ByteTrack (enabled)")
            except Exception as e:
                print("ByteTrack init error:", e)
                self._fallback_to_deepsort()
        else:
            self._fallback_to_deepsort()

    def _fallback_to_deepsort(self):
        if deepsort_available:
            self.tracker = DeepSort(max_age=30)
            self.mode = "deepsort"
            print("Tracker: DeepSORT (fallback)")
        else:
            raise RuntimeError("No tracker available: install deep-sort-realtime or ByteTrack.")

    def update(self, detections, frame=None):
        """
        detections: list of [x1,y1,x2,y2,score,class_id]
        frame: numpy image (for ByteTrack if required)
        returns list of track objects with attributes:
          - track_id
          - to_ltrb() -> (x1,y1,x2,y2)
          - is_confirmed() -> bool   (for DeepSort)
        For ByteTrack wrapper, we return simplified dicts.
        """
        if self.mode == "deepsort":
            return self.tracker.update_tracks(detections, frame=frame)
        else:
            # ByteTrack: convert detections to expected format and call update
            online_targets = self.tracker.update(detections, (frame.shape[0], frame.shape[1]), (frame.shape[0], frame.shape[1]))
            # wrap in simplified objects
            out = []
            for t in online_targets:
                class Obj:
                    pass
                o = Obj()
                o.track_id = t.track_id
                tlwh = t.tlwh
                o.to_ltrb = lambda tlwh=tlwh: (int(tlwh[0]), int(tlwh[1]), int(tlwh[0]+tlwh[2]), int(tlwh[1]+tlwh[3]))
                o.is_confirmed = lambda : True
                out.append(o)
            return out

tracker = TrackerWrapper()

# TTS
tts = pyttsx3.init()
def speak(msg):
    threading.Thread(target=lambda: (tts.say(msg), tts.runAndWait()), daemon=True).start()

# DB helpers
def get_db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def log_event_row(ts, camera, track_id, person_name, role, conf, bbox, evidence=""):
    conn = get_db_conn()
    conn.execute("""INSERT INTO events (ts,camera,track_id,person_name,role,confidence,bbox,evidence)
                    VALUES (?,?,?,?,?,?,?,?)""", (ts,camera,str(track_id),person_name,role,conf,json.dumps(bbox),evidence))
    conn.commit()
    conn.close()

# load known faces into mem cache for speed
def load_face_db():
    conn = get_db_conn()
    rows = conn.execute("SELECT name, role, face_path FROM persons WHERE face_path IS NOT NULL").fetchall()
    conn.close()
    encs = []
    metas = []
    for r in rows:
        path = r["face_path"]
        if path and Path(path).exists():
            img = face_recognition.load_image_file(path)
            e = face_recognition.face_encodings(img)
            if e:
                encs.append(e[0])
                metas.append({"name": r["name"], "role": r["role"], "path": path})
    return encs, metas

known_encodings, known_meta = load_face_db()

# event buffer (for 30s contextual description)
event_buffer = deque()

def add_buffer(evt):
    event_buffer.append((time.time(), evt))
    cutoff = time.time() - BUFFER_SECONDS
    while event_buffer and event_buffer[0][0] < cutoff:
        event_buffer.popleft()

def summarize_buffer_text():
    # simple summarizer: counts per camera + unknowns
    items = [e for ts,e in event_buffer]
    if not items: return "Sin eventos en los últimos 30s."
    by_cam = {}
    unknown = 0
    for e in items:
        c = e.get("camera")
        by_cam[c] = by_cam.get(c,0) + 1
        if e.get("person_name") in ("Desconocido", None):
            unknown += 1
    parts = [f"{cam}:{n}" for cam,n in by_cam.items()]
    return f"{'; '.join(parts)}; Desconocidos: {unknown}"

# Flask API (background)
api_app = Flask("cctv_api")
@api_app.route("/api/events")
def api_events():
    conn = get_db_conn()
    df = pd.read_sql("SELECT * FROM events ORDER BY id DESC LIMIT 500", conn)
    conn.close()
    return df.to_json(orient="records", force_ascii=False)

@api_app.route("/api/cameras")
def api_cameras():
    if CAM_CONF.exists():
        return CAM_CONF.read_text(encoding="utf-8")
    return jsonify({"cameras":[]})

def run_api():
    api_app.run(host="0.0.0.0", port=5000, threaded=True)

# Camera worker (QThread)
class CameraWorker(QtCore.QThread):
    frame_signal = QtCore.pyqtSignal(object, str)
    alert_signal = QtCore.pyqtSignal(dict)

    def __init__(self, cam_id, source, process_every=3):
        super().__init__()
        self.cam_id = str(cam_id)
        self.source = source
        self.running = True
        self.process_every = process_every
        self.cap = None
        self.last_alert_for = {}
    def run(self):
        self.cap = cv2.VideoCapture(self.source)
        frame_idx = 0
        while self.running:
            if not self.cap.isOpened():
                time.sleep(0.5); self.cap = cv2.VideoCapture(self.source); continue
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.02); continue
            frame_idx += 1
            if frame_idx % self.process_every == 0:
                try:
                    preds = model(frame)
                    # gather person detections
                    dets = []
                    for r in preds:
                        boxes = getattr(r, "boxes").xyxy.cpu().numpy()
                        confs = getattr(r, "boxes").conf.cpu().numpy()
                        clss = getattr(r, "boxes").cls.cpu().numpy()
                        for (x1,y1,x2,y2), conf, clsid in zip(boxes, confs, clss):
                            if int(clsid)==0 and conf>0.35:
                                dets.append([int(x1),int(y1),int(x2),int(y2),float(conf),int(clsid)])
                    # tracker update
                    tracks = tracker.update(dets, frame=frame)
                    for t in tracks:
                        if not getattr(t, "is_confirmed", lambda: True)():
                            continue
                        tid = getattr(t, "track_id", None)
                        ltrb = getattr(t, "to_ltrb", lambda: (0,0,0,0))()
                        x1,y1,x2,y2 = map(int, ltrb)
                        # crop head region for face recognition (top 1/3)
                        h = max(1, y2-y1)
                        y_top = max(0,y1)
                        y_head = min(y2, y1 + max(1, h//3))
                        crop = frame[y_top:y_head, x1:x2] if x2>x1 and y_head>y_top else frame[y1:y2,x1:x2]
                        name = "Desconocido"
                        if crop.size != 0:
                            try:
                                rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                                encs = face_recognition.face_encodings(rgb)
                                if encs and known_encodings:
                                    dists = face_recognition.face_distance(known_encodings, encs[0])
                                    idx = int(np.argmin(dists))
                                    if dists[idx] < 0.45:
                                        name = known_meta[idx]["name"]
                            except Exception as ex:
                                print("face err", ex)
                        role = "Empleado" if name!="Desconocido" else "Desconocido"
                        # create evidence for suspicious or unknown
                        now_ts = int(time.time())
                        evpath = ""
                        if name=="Desconocido":
                            evname = f"{self.cam_id}_{tid}_{now_ts}.jpg"
                            evpath = str(EVID_DIR / evname)
                            cv2.imwrite(evpath, frame)
                        # log
                        evt = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                               "camera": self.cam_id, "track_id": tid, "person_name": name,
                               "role": role, "confidence": 0.0, "bbox":[x1,y1,x2,y2], "evidence": evpath}
                        log_event_row(evt["ts"], self.cam_id, tid, name, role, 0.0, evt["bbox"], evpath)
                        add_to_buffer(evt)
                        self.alert_signal.emit(evt)
                        # TTS + Telegram (cooldown)
                        last = self.last_alert_for.get(tid, 0)
                        if time.time() - last > ALERT_COOLDOWN and name=="Desconocido":
                            self.last_alert_for[tid] = time.time()
                            speak(f"Alerta: persona desconocida en cámara {self.cam_id}")
                            if TELEGRAM_TOKEN and TELEGRAM_CHAT:
                                threading.Thread(target=send_telegram, args=(f"Alerta desconocido en {self.cam_id}", evpath)).start()
                except Exception as e:
                    print("Process frame error:", e)
            # emit frame for UI
            self.frame_signal.emit(frame, self.cam_id)
        if self.cap:
            self.cap.release()
    def stop(self):
        self.running = False

# Telegram helper
def send_telegram(text, image_path=None):
    try:
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
            return False
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT, "text": text}, timeout=5)
        if image_path and os.path.exists(image_path):
            url2 = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            with open(image_path,"rb") as f:
                requests.post(url2, data={"chat_id": TELEGRAM_CHAT}, files={"photo": f}, timeout=15)
        return True
    except Exception as e:
        print("tg send err", e)
        return False

# UI: MainWindow
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CCTV Inteligente - Dashboard")
        self.resize(1400, 900)
        # layout: left list cameras, center view area, right controls, bottom logs
        main = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(main)
        top = QtWidgets.QHBoxLayout()
        main_layout.addLayout(top, 8)
        bottom = QtWidgets.QHBoxLayout()
        main_layout.addLayout(bottom, 2)
        # left: camera list
        left = QtWidgets.QWidget(); left_l = QtWidgets.QVBoxLayout(left)
        self.cam_list = QtWidgets.QListWidget()
        left_l.addWidget(QtWidgets.QLabel("<b>Cámaras</b>")); left_l.addWidget(self.cam_list)
        btn_add = QtWidgets.QPushButton("Agregar cámara"); btn_add.clicked.connect(self.add_camera_dialog); left_l.addWidget(btn_add)
        top.addWidget(left, 2)
        # center: stack for Panoptic or Single
        self.stack = QtWidgets.QStackedWidget()
        # panoptic grid
        self.grid_widget = QtWidgets.QWidget(); self.grid_layout = QtWidgets.QGridLayout(self.grid_widget)
        self.stack.addWidget(self.grid_widget)
        # single view
        self.single_label = QtWidgets.QLabel("Selecciona cámara"); self.single_label.setAlignment(QtCore.Qt.AlignCenter)
        self.stack.addWidget(self.single_label)
        top.addWidget(self.stack, 6)
        # right: controls: tracks, persons combo, bind button, export
        right = QtWidgets.QWidget(); right_l = QtWidgets.QVBoxLayout(right)
        right_l.addWidget(QtWidgets.QLabel("<b>Tracks activos</b>"))
        self.tracks_list = QtWidgets.QListWidget(); right_l.addWidget(self.tracks_list)
        right_l.addWidget(QtWidgets.QLabel("<b>Personas registradas</b>"))
        self.persons_combo = QtWidgets.QComboBox(); right_l.addWidget(self.persons_combo)
        self.bind_btn = QtWidgets.QPushButton("Asignar persona al track"); self.bind_btn.clicked.connect(self.bind_selected)
        right_l.addWidget(self.bind_btn)
        self.export_btn = QtWidgets.QPushButton("Exportar events.csv"); self.export_btn.clicked.connect(self.export_events)
        right_l.addWidget(self.export_btn)
        top.addWidget(right, 2)
        # bottom: logs
        self.log_console = QtWidgets.QTextEdit(); self.log_console.setReadOnly(True)
        bottom.addWidget(self.log_console)
        self.setCentralWidget(main)
        # state
        self.workers = {}  # cam_name -> worker
        self.labels = {}   # cam_name -> QLabel
        # load cameras
        self.load_cameras(initial=True)
        # start flask API thread
        threading.Thread(target=run_api, daemon=True).start()
        # start reporter thread (calls reporter.py once each interval)
        threading.Thread(target=self.reporter_loop, daemon=True).start()

    def reporter_loop(self):
        from subprocess import Popen
        while True:
            try:
                subprocess.run([sys.executable, str(Path(__file__).parent/"reporter.py"), "once"], check=False)
            except Exception as e:
                print("reporter loop err", e)
            time.sleep(8*3600)

    def add_camera_dialog(self):
        name, ok = QtWidgets.QInputDialog.getText(self,"Agregar cámara","Nombre")
        if not ok or not name: return
        source, ok = QtWidgets.QInputDialog.getText(self,"Agregar cámara","Fuente (0 para webcam o rtsp://... )")
        if not ok or not source: return
        src = int(source) if source.isdigit() else source
        self._add_camera(name, src)
        self.save_cameras()

    def _add_camera(self, name, src):
        if name in self.workers:
            QtWidgets.QMessageBox.warning(self,"Duplicado","Cámara ya existe")
            return
        # list item
        self.cam_list.addItem(name)
        # create label in grid
        lbl = QtWidgets.QLabel(name); lbl.setStyleSheet("background:black;color:white"); lbl.setAlignment(QtCore.Qt.AlignCenter)
        idx = self.grid_layout.count()
        r = idx//2; c = idx%2
        self.grid_layout.addWidget(lbl, r, c); self.labels[name]=lbl
        # start worker
        w = CameraWorker(name, src)
        w.frame_signal.connect(lambda f, cam=name, lbl=lbl: self.on_frame(f, lbl, cam))
        w.alert_signal.connect(self.on_alert)
        w.start()
        self.workers[name] = w
        self.load_persons()

    def load_cameras(self, initial=False):
        if not CAM_CONF.exists():
            CAM_CONF.write_text(json.dumps({"cameras":[]}, indent=2), encoding="utf-8")
        data = json.loads(CAM_CONF.read_text(encoding="utf-8"))
        # stop existing
        for name,info in list(self.workers.items()):
            info.stop()
        self.workers.clear(); self.labels.clear()
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        # add cameras from config
        for cam in data.get("cameras", []):
            name = cam.get("name"); src = cam.get("source")
            src = int(src) if isinstance(src, (str,)) and src.isdigit() else src
            self._add_camera(name, src)
        if not initial:
            QtWidgets.QMessageBox.information(self,"Cámaras","Cargar cámaras terminado")

    def save_cameras(self):
        data = {"cameras":[{"name":k,"source":v["worker"].source if isinstance(v["worker"].source,str) or isinstance(v["worker"].source,int) else v["worker"].source} for k,v in self.workers.items()]}
        CAM_CONF.write_text(json.dumps(data, indent=2), encoding="utf-8")
        QtWidgets.QMessageBox.information(self,"Guardado","cameras.json actualizado")

    def on_frame(self, frame, label, cam):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h,w,ch = rgb.shape
        qimg = QtGui.QImage(rgb.data, w,h, ch*w, QtGui.QImage.Format_RGB888)
        pix = QtGui.QPixmap.fromImage(qimg).scaled(480,320, QtCore.Qt.KeepAspectRatio)
        label.setPixmap(pix)
        # keep console short log
        self.log_console.append(f"[{time.strftime('%H:%M:%S')}] {cam} frame")

    def on_alert(self, alert):
        s = f"[{alert['ts']}] {alert['camera']} - {alert['person_name']} ({alert['role']})"
        self.log_console.append(s)
        # append to events_short
        with open(REPORTS_DIR + "/events_short.log","a",encoding="utf-8") as f:
            f.write(s+"\n")

    def load_persons(self):
        self.persons_combo.clear()
        conn = get_db_conn()
        rows = conn.execute("SELECT name, role FROM persons ORDER BY name").fetchall()
        conn.close()
        for r in rows:
            self.persons_combo.addItem(f"{r['name']} ({r['role']})", r['name'])

    def bind_selected(self):
        item = self.tracks_list.currentItem()
        if not item:
            QtWidgets.QMessageBox.warning(self,"Selecciona track","Selecciona un track primero")
            return
        text = item.text()  # format: Cam - Track 123
        try:
            cam, tid = text.split(" -- ")
            tid = tid.strip()
        except:
            QtWidgets.QMessageBox.warning(self,"Formato","Track formato inesperado")
            return
        idx = self.persons_combo.currentIndex()
        if idx<0:
            QtWidgets.QMessageBox.warning(self,"Persona","Selecciona una persona")
            return
        pname = self.persons_combo.itemData(idx)
        # insert into track_bindings
        conn = get_db_conn(); conn.execute("INSERT OR REPLACE INTO track_bindings (cam_id,track_id,person_name,expires_at) VALUES (?,?,?,?)",
                                           (cam, tid, pname, None)); conn.commit(); conn.close()
        QtWidgets.QMessageBox.information(self,"Vinculado", f"Track {tid} vinculado a {pname}")

    def export_events(self):
        conn = get_db_conn()
        df = pd.read_sql("SELECT * FROM events ORDER BY id DESC LIMIT 1000", conn)
        conn.close()
        csvf = Path(REPORTS_DIR)/"events_export.csv"
        df.to_csv(str(csvf), index=False)
        QtWidgets.QMessageBox.information(self,"Exportado", f"Events exportados a {csvf}")

    def closeEvent(self, event):
        for w in list(self.workers.values()):
            try:
                w.stop()
            except:
                pass
        super().closeEvent(event)

# register face helper (GUI also calls register_face.py)
def enroll_face_from_frame(name, role, frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    boxes = face_recognition.face_locations(rgb)
    if not boxes:
        return False, "No se detectó rostro"
    enc = face_recognition.face_encodings(rgb, boxes)[0]
    # save image
    fname = FACES_DIR / f"{name}_{int(time.time())}.jpg"
    cv2.imwrite(str(fname), frame)
    # insert to DB
    conn = get_db_conn()
    conn.execute("INSERT OR REPLACE INTO persons (name, role, face_path) VALUES (?,?,?)", (name, role, str(fname)))
    conn.commit()
    conn.close()
    # reload known encs
    global known_encodings, known_meta
    known_encodings, known_meta = load_face_db()
    return True, "Enrolamiento correcto"

# main
def ensure_db():
    conn = get_db_conn()
    # make sure tables exist
    conn.execute("""CREATE TABLE IF NOT EXISTS persons (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, role TEXT, face_path TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, camera TEXT, track_id TEXT, person_name TEXT, role TEXT, confidence REAL, bbox TEXT, evidence TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS track_bindings (
                        cam_id TEXT, track_id TEXT, person_name TEXT, bound_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, expires_at TIMESTAMP, PRIMARY KEY(cam_id,track_id))""")
    conn.commit(); conn.close()

if __name__ == "__main__":
    ensure_db()
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    # API thread
    threading.Thread(target=run_api, daemon=True).start()
    sys.exit(app.exec_())