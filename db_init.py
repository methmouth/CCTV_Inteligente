import sqlite3
import os

DB_PATH = "people.db"

def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("🔄 BD anterior eliminada.")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Tabla de personas
    c.execute("""
    CREATE TABLE persons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT CHECK(role IN ('Empleado','Cliente','Proveedor','Invitado','Desconocido')) NOT NULL,
        face_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Tabla de eventos
    c.execute("""
    CREATE TABLE events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        camera TEXT NOT NULL,
        person TEXT NOT NULL,
        role TEXT NOT NULL
    )
    """)

    # Insertar ejemplos
    c.executemany("""
    INSERT INTO persons (name, role, face_path) VALUES (?, ?, ?)
    """, [
        ("Juan Pérez", "Empleado", "faces/juan.jpg"),
        ("María López", "Empleado", "faces/maria.jpg"),
        ("Proveedor S.A.", "Proveedor", None),
        ("Cliente VIP", "Cliente", None),
        ("Visita", "Invitado", None)
    ])

    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada con ejemplos.")

if __name__ == "__main__":
    os.makedirs("faces", exist_ok=True)
    init_db()