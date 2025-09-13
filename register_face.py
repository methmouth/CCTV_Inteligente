import cv2
import sqlite3
import json
import time
import os
from pathlib import Path
import face_recognition

BASE = Path(__file__).parent
FACES = BASE / "faces"
FACES.mkdir(exist_ok=True)
DB = BASE / "people.db"

def enroll_cli():
    name = input("Nombre (ej: Juan Perez): ").strip()
    role = input("Rol (Empleado/Cliente/Proveedor/Invitado): ").strip() or "Empleado"
    cam = int(input("Cam index (0 para webcam): ") or "0")
    cap = cv2.VideoCapture(cam)
    print("Presiona SPACE para capturar, ESC para salir")
    while True:
        ret, frame = cap.read()
        if not ret: break
        cv2.imshow("Captura", frame)
        k = cv2.waitKey(1) & 0xFF
        if k == 27:
            break
        if k == 32:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            boxes = face_recognition.face_locations(rgb)
            if not boxes:
                print("No se detectó rostro. Intenta otra captura.")
                continue
            filename = FACES / f"{name.replace(' ','_')}_{int(time.time())}.jpg"
            cv2.imwrite(str(filename), frame)
            conn = sqlite3.connect(DB)
            conn.execute("INSERT OR REPLACE INTO persons (name, role, face_path) VALUES (?,?,?)", (name, role, str(filename)))
            conn.commit(); conn.close()
            print("Rostro guardado:", filename)
            break
    cap.release(); cv2.destroyAllWindows()

if __name__ == "__main__":
    enroll_cli()