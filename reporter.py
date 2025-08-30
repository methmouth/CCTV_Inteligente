import sqlite3, time, os, sys
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from jinja2 import Template

DB_PATH = "people.db"
REPORTS_DIR = "reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

# -------------------------
# Extraer eventos de la BD
# -------------------------
def get_events():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM events ORDER BY id DESC LIMIT 500", conn)
    conn.close()
    return df

# -------------------------
# Generar PDF
# -------------------------
def generate_pdf(df, filename):
    doc = SimpleDocTemplate(filename, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("📊 Reporte de Eventos CCTV Inteligente", styles['Title']))
    elements.append(Spacer(1, 12))

    # tabla
    data = [df.columns.tolist()] + df.values.tolist()
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.lightgrey),
        ('TEXTCOLOR',(0,0),(-1,0),colors.black),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTSIZE',(0,0),(-1,-1),8)
    ]))
    elements.append(table)

    doc.build(elements)
    print(f"✅ PDF generado: {filename}")

# -------------------------
# Generar HTML interactivo
# -------------------------
def generate_html(df, filename):
    template = Template("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8"/>
        <title>Reporte de Eventos CCTV</title>
        <link rel="stylesheet" href="https://cdn.datatables.net/1.13.4/css/jquery.dataTables.min.css"/>
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
    </head>
    <body>
        <h1>📊 Reporte de Eventos CCTV Inteligente</h1>
        <table id="events" class="display" style="width:100%">
            <thead>
                <tr>
                {% for col in cols %}
                    <th>{{ col }}</th>
                {% endfor %}
                </tr>
            </thead>
            <tbody>
                {% for row in rows %}
                <tr>
                    {% for cell in row %}
                        <td>{{ cell }}</td>
                    {% endfor %}
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <script>
        $(document).ready(function() {
            $('#events').DataTable();
        });
        </script>
    </body>
    </html>
    """)
    html = template.render(cols=df.columns.tolist(), rows=df.values.tolist())
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ HTML generado: {filename}")

# -------------------------
# Generar Reporte Completo
# -------------------------
def generate_reports():
    df = get_events()
    if df.empty:
        print("⚠️ No hay eventos registrados todavía.")
        return
    ts = time.strftime("%Y%m%d_%H%M%S")
    pdf_file = os.path.join(REPORTS_DIR, f"report_{ts}.pdf")
    html_file = os.path.join(REPORTS_DIR, f"report_{ts}.html")
    generate_pdf(df, pdf_file)
    generate_html(df, html_file)

# -------------------------
# Loop (cada 8h)
# -------------------------
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        generate_reports()
    else:
        print("⏳ Iniciando reporter automático cada 8h...")
        while True:
            generate_reports()
            time.sleep(8 * 3600)