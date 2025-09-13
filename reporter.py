import os
import time
import sqlite3
import pandas as pd
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import matplotlib.pyplot as plt
from jinja2 import Template

BASE = Path(__file__).parent
DB = BASE / "people.db"
OUT = BASE / "reports"
OUT.mkdir(parents=True, exist_ok=True)

def get_events(limit=1000):
    conn = sqlite3.connect(DB)
    df = pd.read_sql("SELECT * FROM events ORDER BY id DESC LIMIT ?", conn, params=(limit,))
    conn.close()
    return df

def gen_pdf(df, outpath):
    doc = SimpleDocTemplate(str(outpath), pagesize=A4)
    styles = getSampleStyleSheet()
    elems = [Paragraph("Reporte CCTV Inteligente", styles['Title']), Spacer(1,12)]
    if df.empty:
        elems.append(Paragraph("No hay eventos", styles['Normal']))
    else:
        # counts per role
        counts = df['role'].fillna('Desconocido').value_counts().to_dict()
        elems.append(Paragraph("Resumen por rol:", styles['Heading2']))
        for k,v in counts.items():
            elems.append(Paragraph(f"{k}: {v}", styles['Normal']))
        elems.append(Spacer(1,8))
        # save plot
        plt.figure(figsize=(6,3))
        pd.Series(counts).plot(kind='bar')
        plt.tight_layout()
        tmp_plot = OUT / "plot_tmp.png"
        plt.savefig(tmp_plot)
        plt.close()
        elems.append(Image(str(tmp_plot), width=450, height=200))
        elems.append(Spacer(1,12))
        # table (first 50 rows)
        sample = df.head(50)
        data = [list(sample.columns)] + sample.values.tolist()
        table = Table(data)
        table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.5,colors.grey),
                                   ('BACKGROUND',(0,0),(-1,0),colors.lightgrey)]))
        elems.append(table)
    doc.build(elems)

def gen_html(df, outpath):
    tpl = Template("""
    <html><head><meta charset="utf-8"><title>Reporte CCTV</title>
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.4/css/jquery.dataTables.min.css"/>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
    </head><body>
    <h1>Reporte CCTV</h1>
    <p>Generado: {{ ts }}</p>
    {{ table|safe }}
    <script>$(document).ready(()=>$('#t').DataTable());</script>
    </body></html>
    """)
    html = tpl.render(ts=time.strftime("%Y-%m-%d %H:%M:%S"), table=df.to_html(index=False))
    outpath.write_text(html, encoding="utf-8")

if __name__ == "__main__":
    df = get_events()
    ts = time.strftime("%Y%m%d_%H%M%S")
    pdfp = OUT / f"report_{ts}.pdf"
    htmlp = OUT / f"report_{ts}.html"
    gen_pdf(df, pdfp)
    gen_html(df, htmlp)
    print("Reportes generados:", pdfp, htmlp)