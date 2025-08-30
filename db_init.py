import sqlite3

conn = sqlite3.connect("people.db")
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS persons")
cur.execute("DROP TABLE IF EXISTS events")

cur.execute("""
CREATE TABLE persons (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  role TEXT
)
""")

cur.execute("""
CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT,
  camera_id TEXT,
  person_id TEXT,
  details TEXT
)
""")

# ejemplos
cur.execute("INSERT INTO persons (name,role) VALUES ('Juan Perez','Empleado')")
cur.execute("INSERT INTO persons (name,role) VALUES ('Cliente A','Cliente')")
cur.execute("INSERT INTO persons (name,role) VALUES ('Proveedor X','Proveedor')")

conn.commit()
conn.close()
print("BD inicializada con ejemplos")