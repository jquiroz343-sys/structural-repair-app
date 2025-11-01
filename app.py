# --- app.py (COMPLETO - COPIA Y PEGA TODO) ---
from flask import Flask, render_template, jsonify, request, redirect, url_for, send_file, session
import data_manager
import audit_log
import os
import re
import csv
from werkzeug.utils import secure_filename
from datetime import datetime
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# --- CONFIGURACIÓN ---
app = Flask(__name__)
app.secret_key = 'super_secure_key_2025_change_in_production'
UPLOAD_FOLDER = 'data/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tif', 'tiff', 'dwg', 'dxf', 'doc', 'docx', 'xls', 'xlsx'}

# --- UTILITARIOS ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_user_context():
    return {
        'role': request.headers.get('X-User-Role', session.get('user_role', 'UNKNOWN')),
        'name': request.headers.get('X-User-Name', session.get('user_name', 'N/A')),
        'ip': request.remote_addr
    }

# --- VALIDACIÓN ---
def validate_repair_data(record_data):
    if not record_data.get('Repair_ID'):
        return False, "Repair ID is mandatory."
    return True, "Valid"

# --- RUTAS API ---
@app.route('/api/projects/create', methods=['POST'])
def create_project_api():
    data = request.json
    msn = data.get('msn')
    if not msn:
        return jsonify({"success": False, "message": "MSN is required"}), 400
    try:
        success, message = data_manager.create_project(msn, data)
        if success:
            audit_log.log_event(msn, None, "CREATE_PROJECT", get_user_context(), data)
            return jsonify({"success": True, "message": f"Project {msn} created!"})
        return jsonify({"success": False, "message": message}), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# --- LISTAR TODOS LOS REPAIRS ---
@app.route('/api/repairs/<msn>', methods=['GET'])
def get_repairs_api(msn):
    repairs = data_manager.get_all_repairs(msn)
    return jsonify(repairs)

# --- OBTENER UN REPAIR ESPECÍFICO ---
@app.route('/api/repairs/<msn>/<repair_id>', methods=['GET'])
def get_repair_api(msn, repair_id):
    repair = data_manager.get_repair_record_by_id(msn, repair_id)
    if repair:
        return jsonify(repair)
    return jsonify({"error": "Repair not found"}), 404

# --- AÑADIR NUEVO REPAIR ---
@app.route('/api/repairs/add/<msn>', methods=['POST'])
def add_repair_api(msn):
    data = request.json
    success, message = validate_repair_data(data)
    if not success:
        return jsonify({"success": False, "message": message}), 400
    success, message = data_manager.add_repair_record(msn, data)
    if success:
        audit_log.log_event(msn, data['Repair_ID'], "ADD_REPAIR", get_user_context(), data)
    return jsonify({"success": success, "message": message})

# --- ACTUALIZAR REPAIR ---
@app.route('/api/repairs/update/<msn>/<repair_id>', methods=['PUT'])
def update_repair_api(msn, repair_id):
    data = request.json
    success, message = validate_repair_data({**data_manager.get_repair_record_by_id(msn, repair_id), **data})
    if not success:
        return jsonify({"success": False, "message": message}), 400
    success, message = data_manager.update_repair_record(msn, repair_id, data)
    if success:
        audit_log.log_event(msn, repair_id, "UPDATE_REPAIR", get_user_context(), data)
    return jsonify({"success": success, "message": message})

# --- RESUMEN OIL ---
@app.route('/api/report/oil_summary/<msn>', methods=['GET'])
def oil_summary_api(msn):
    records = data_manager.get_all_repairs(msn)
    total = len(records)
    open_oil = len([r for r in records if r.get('Audit_OIL_Status') == 'Open'])
    closed_oil = len([r for r in records if r.get('Audit_OIL_Status') == 'Closed'])
    progress = round((closed_oil / total * 100), 1) if total else 0
    return jsonify({
        "total_records": total,
        "oil_status": {"open": open_oil, "closed": closed_oil, "progress_percent": progress}
    })

# --- SUBIR DOCUMENTO ---
@app.route('/api/documents/upload/<msn>/<repair_id>/<doc_field>', methods=['POST'])
def upload_document(msn, repair_id, doc_field):
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file"}), 400
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"success": False, "message": "Invalid file"}), 400
    filename = secure_filename(file.filename)
    doc_dir = os.path.join(app.config['UPLOAD_FOLDER'], msn, repair_id)
    os.makedirs(doc_dir, exist_ok=True)
    filepath = os.path.join(doc_dir, filename)
    file.save(filepath)
    update_data = {doc_field: f"uploads/{msn}/{repair_id}/{filename}"}
    data_manager.update_repair_record(msn, repair_id, update_data)
    return jsonify({"success": True, "stored_filename": filename})

# --- AUDIT TRAIL ---
@app.route('/api/audit_trail/<msn>/<repair_id>', methods=['GET'])
def get_audit_trail_api(msn, repair_id):
    return jsonify(audit_log.get_audit_trail(msn, repair_id))

# --- EXPORT PDF OIL ---
@app.route('/export/oil_pdf/<msn>')
def export_oil_pdf(msn):
    records = data_manager.get_all_repairs(msn)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph(f"<b>OIL Report - MSN {msn}</b>", styles['Title']))
    elements.append(Spacer(1, 12))
    details = data_manager.get_project_details(msn)
    elements.append(Paragraph(f"<b>Reg:</b> {details.get('Aircraft_Reg', 'N/A')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%Y-%m-%d')}", styles['Normal']))
    elements.append(Spacer(1, 20))

    data = [['ID', 'ATA', 'Loc', 'OIL', 'Phys', 'Note']]
    for r in records:
        data.append([
            r.get('Repair_ID', 'N/A'),
            r.get('ATA_Chapter', 'N/A'),
            r.get('Location_Desc', 'N/A')[:15],
            r.get('Audit_OIL_Status', 'N/A'),
            r.get('Audit_Physical_Status', 'N/A'),
            (r.get('Audit_Physical_Note', '') or '')[:30]
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#004c99')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND',(0,1),(-1,-1),colors.beige),
        ('GRID',(0,0),(-1,-1),0.5,colors.black)
    ]))
    elements.append(table)
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("___________________________", styles['Normal']))
    elements.append(Paragraph("Auditor Signature", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, 
                     download_name=f"OIL_{msn}_{datetime.now().strftime('%Y%m%d')}.pdf", 
                     mimetype='application/pdf')

# --- RUTAS WEB ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/project/select')
def project_select_page():
    projects = data_manager.get_all_projects()
    return render_template('project_setup_select.html', projects=projects)

@app.route('/project/create')
def project_create_page():
    return render_template('project_setup_create.html')

@app.route('/role_select/<msn>')
def role_select_web(msn):
    return render_template('role_select.html', msn=msn)

@app.route('/dashboard/<msn>')
def dashboard(msn):
    details = data_manager.get_project_details(msn)
    if not details:
        return redirect(url_for('index'))
    return render_template('dashboard.html', msn=msn, details=details)

@app.route('/view/<msn>')
def view_repairs_web(msn):
    return render_template('view_repairs.html', msn=msn)

@app.route('/edit/<msn>/<repair_id>')
def edit_repair_web(msn, repair_id):
    return render_template('edit_repair.html', msn=msn, repair_id=repair_id)

@app.route('/audit/<msn>')
def audit_dashboard_web(msn):
    return render_template('audit.html', msn=msn)
# Vercel necesita esto
if __name__ == "__main__":
    app.run()

# --- INICIAR SERVIDOR ---
if __name__ == '__main__':
    print("\nFLASK SERVER INICIADO")
    print("URL: http://127.0.0.1:5000")
    print("-------------------------------------------------")
    app.run(host='127.0.0.1', port=5000, debug=True)