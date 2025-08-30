import sys, os, cv2, time, json, sqlite3, subprocess
import numpy as np
import pyttsx3
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QAction, QFileDialog, QToolBar, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QMessageBox
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QTimer
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort

DB_PATH = "people.db"
CAMERA_CONFIG = "cameras.json"

class CCTVApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CCTV Inteligente — Dashboard")
        self.resize(1280, 720)

        self.model = YOLO("yolov8n.pt")
        self.tracker = DeepSort(max_age=30)
        self.tts = pyttsx3.init()

        self.conn = sqlite3.connect(DB_PATH)
        self.cur = self.conn.cursor()

        # Layout
        self.label = QLabel("Esperando cámaras...")
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # ToolBar
        toolbar = QToolBar("Herramientas")
        self.addToolBar(toolbar)

        crud_action = QAction("Personas (CRUD)", self)
        crud_action.triggered.connect(self.open_persons_editor)
        toolbar.addAction(crud_action)

        events_action = QAction("Eventos (Excel)", self)
        events_action.triggered.connect(self.open_events_editor)
        toolbar.addAction(events_action)

        export_action = QAction("Exportar CSV", self)
        export_action.triggered.connect(self.export_events_csv)
        toolbar.addAction(export_action)

        refresh_action = QAction("Refrescar DB", self)
        refresh_action.triggered.connect(self.reload_db)
        toolbar.addAction(refresh_action)

        # Cámara
        self.load_cameras()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(50)

    def load_cameras(self):
        with open(CAMERA_CONFIG, "r") as f:
            self.cameras = json.load(f)
        # solo usamos la primera cámara por demo
        self.cap = cv2.VideoCapture(self.cameras["1"])

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return
        results = self.model(frame)
        detections = []
        for r in results:
            boxes = r.boxes.xyxy.cpu().numpy()
            scores = r.boxes.conf.cpu().numpy()
            classes = r.boxes.cls.cpu().numpy()
            for (x1,y1,x2,y2), sc, cl in zip(boxes, scores, classes):
                if int(cl) == 0 and sc > 0.5:  # persona
                    detections.append([x1,y1,x2,y2,sc, int(cl)])
        tracks = self.tracker.update_tracks(detections, frame=frame)
        for t in tracks:
            if not t.is_confirmed(): continue
            x1,y1,x2,y2 = map(int, t.to_ltrb())
            tid = t.track_id
            label = self.get_person_label(tid)
            cv2.rectangle(frame,(x1,y1),(x2,y2),(0,255,0),2)
            cv2.putText(frame,label,(x1,y1-10),cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,255,0),2)
            self.log_event("1", tid, label)
            if label=="Desconocido":
                self.tts.say(f"Alerta, persona desconocida en cámara 1")
                self.tts.runAndWait()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h,w,ch = rgb.shape
        qimg = QImage(rgb.data, w,h, ch*w, QImage.Format_RGB888)
        self.label.setPixmap(QPixmap.fromImage(qimg))

    def get_person_label(self, track_id):
        return "Desconocido"  # simplificado, se liga con DB

    def log_event(self, camera_id, track_id, label):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self.cur.execute("INSERT INTO events (timestamp,camera_id,person_id,details) VALUES (?,?,?,?)",(ts,camera_id,track_id,label))
        self.conn.commit()

    def open_persons_editor(self):
        self.editor = TableEditor("persons")
        self.editor.show()

    def open_events_editor(self):
        self.editor = TableEditor("events")
        self.editor.show()

    def export_events_csv(self):
        import pandas as pd
        df = pd.read_sql("SELECT * FROM events", self.conn)
        df.to_csv("events.csv", index=False)
        QMessageBox.information(self,"Exportación","Eventos exportados a events.csv")

    def reload_db(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.cur = self.conn.cursor()
        QMessageBox.information(self,"DB","Conexión recargada")

class TableEditor(QWidget):
    def __init__(self, table_name):
        super().__init__()
        self.setWindowTitle(f"Editor: {table_name}")
        self.conn = sqlite3.connect(DB_PATH)
        self.cur = self.conn.cursor()
        self.table = table_name
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.load_table()

    def load_table(self):
        rows = self.cur.execute(f"SELECT * FROM {self.table}").fetchall()
        cols = [d[0] for d in self.cur.description]
        table = QTableWidget(len(rows), len(cols))
        table.setHorizontalHeaderLabels(cols)
        for i,r in enumerate(rows):
            for j,v in enumerate(r):
                table.setItem(i,j,QTableWidgetItem(str(v)))
        self.layout.addWidget(table)

if __name__=="__main__":
    app = QApplication(sys.argv)
    win = CCTVApp()
    win.show()
    sys.exit(app.exec_())