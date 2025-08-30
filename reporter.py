import sqlite3, time
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

conn = sqlite3.connect("people.db")
cur = conn.cursor()
rows = cur.execute("SELECT * FROM events ORDER BY timestamp DESC LIMIT 50").fetchall()

styles = getSampleStyleSheet()
doc = SimpleDocTemplate("reports/report.pdf")
story = [Paragraph("Reporte de eventos", styles["Title"]), Spacer(1,12)]

for r in rows:
    story.append(Paragraph(str(r), styles["Normal"]))
    story.append(Spacer(1,12))

doc.build(story)
print("Reporte generado en reports/report.pdf")