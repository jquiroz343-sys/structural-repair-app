# pdf_generator.py
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import os

def generate_pdf(repair, base_dir):
    pdf_filename = f"SRF_{repair['id']}.pdf"
    pdf_path = os.path.join(base_dir, pdf_filename)
    
    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Título
    story.append(Paragraph(f"<b>Structural Repair Log - SRF {repair['id']}</b>", styles['Title']))
    story.append(Spacer(1, 12))

    # Tabla de datos
    data = [["Campo", "Valor"]]
    for key, value in repair.items():
        if key != 'photos' and key != 'id':
            data.append([key.replace('_', ' ').title(), str(value)[:200]])
    
    table = Table(data, colWidths=[150, 350])
    table.setStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)
    ])
    story.append(table)
    story.append(Spacer(1, 20))

    # Fotos
    if 'photos' in repair and repair['photos']:
        story.append(Paragraph("<b>Fotos:</b>", styles['Heading3']))
        for photo_path in repair['photos']:
            if os.path.exists(photo_path):
                try:
                    img = Image(photo_path, width=200, height=150)
                    story.append(img)
                    story.append(Spacer(1, 10))
                except:
                    story.append(Paragraph(f"[Foto no disponible]", styles['Normal']))
            else:
                story.append(Paragraph(f"[Foto no encontrada]", styles['Normal']))

    # Generar PDF
    doc.build(story)
    return pdf_path