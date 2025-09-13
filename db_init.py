import sqlite3
import os
import shutil

DB = "people.db"

if os.path.exists(DB):
    print("⚠️  people.db ya existe — renombrando a people.db.bak")
    os.rename(DB, DB + ".bak")

conn = sqlite3.connect(DB)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS persons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    role TEXT CHECK(role IN ('Empleado','Cliente','Proveedor','Invitado','Desconocido')) NOT NULL DEFAULT 'Desconocido',
    face_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    camera TEXT NOT NULL,
    track_id TEXT,
    person_name TEXT,
    role TEXT,
    confidence REAL,
    bbox TEXT,
    evidence TEXT
)
""")

# table to bind track -> person temporarily
c.execute("""
CREATE TABLE IF NOT EXISTS track_bindings (
    cam_id TEXT,
    track_id TEXT,
    person_name TEXT,
    bound_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    PRIMARY KEY (cam_id, track_id)
)
""")

# Ejemplos iniciales (sin imágenes)
examples = [
    ("Juan Perez","Empleado", None),
    ("Maria Lopez","Empleado", None),
    ("Proveedor S.A.","Proveedor", None),
    ("Cliente VIP","Cliente", None)
]
for name, role, face in examples:
    try:
        c.execute("INSERT INTO persons (name, role, face_path) VALUES (?, ?, ?)", (name, role, face))
    except sqlite3.IntegrityError:
        pass

conn.commit()
conn.close()
print("✅ Base de datos creada: people.db (ejemplos insertados).")
print("Coloca imágenes en ./faces/ y usa register_face.py para enrollar embeddings.")