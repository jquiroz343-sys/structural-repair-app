# --- app.py (COMPLETO - FLUJO ORIGINAL + ROLES) ---
from flask import Flask, render_template, jsonify, request, redirect, url_for, send_from_directory, make_response, session
import data_manager
import audit_log
import os
import re
import csv 
from werkzeug.utils import secure_filename
from datetime import datetime
import io
import tempfile

app = Flask(__name__)
app.secret_key = 'structural_repair_2025_secure_key'

# --- CONFIGURACIÓN PARA RENDER ---
BASE_DIR = tempfile.gettempdir()
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tif', 'tiff', 'dwg', 'dxf', 'doc', 'docx', 'xls', 'xlsx'} 

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_repair_data(record_data):
    if not record_data.get('Repair_ID'):
        return False, "Repair ID is mandatory."
    ata_chapter = record_data.get('ATA_Chapter', '')
    if ata_chapter and not ata_chapter.upper().startswith('ATA '):
        return False, "ATA Chapter must start with 'ATA '."
    date_val = record_data.get('Date_Completed', '')
    if date_val and not re.match(r'^\d{4}-\d{2}-\d{2}$', date_val):
        return False, "Date Completed must be YYYY-MM-DD."
    return True, None

# --- API ---
@app.route('/api/projects/create', methods=['POST'])
def create_project_api():
    project_data = request.json
    msn = project_data.pop('msn', '').strip().upper()
    if not msn:
        return jsonify({"success": False, "message": "MSN is required."}), 400
    project_data['Aircraft_Type'] = project_data.get('Aircraft_Type', 'N/A')
    success, message = data_manager.create_new_project(msn, project_data)
    if success:
        audit_log.log_event(msn, "PROJECT", "CREATE", {'role': 'SETUP', 'ip': request.remote_addr}, project_data)
    return jsonify({"success": success, "message": message})

@app.route('/api/repairs/<msn>', methods=['GET'])
def get_repairs(msn):
    return jsonify(data_manager.get_all_repairs(msn))

@app.route('/api/repairs/<msn>/<repair_id>', methods=['GET'])
def get_repair(msn, repair_id):
    record = data_manager.get_repair_record_by_id(msn, repair_id)
    return jsonify(record) if record else (jsonify({"error": "Not found"}), 404)

@app.route('/api/repairs/add/<msn>', methods=['POST'])
def add_repair(msn):
    data = request.json
    valid, msg = validate_repair_data(data)
    if not valid:
        return jsonify({"success": False, "message": msg}), 400
    success, message = data_manager.add_repair_record(msn, data)
    if success:
        audit_log.log_event(msn, data['Repair_ID'], "ADD", {'role': 'OPERATOR', 'ip': request.remote_addr}, data)
    return jsonify({"success": success, "message": message})

@app.route('/api/repairs/update/<msn>/<repair_id>', methods=['PUT'])
def update_repair(msn, repair_id):
    update_data = request.json
    current = data_manager.get_repair_record_by_id(msn, repair_id)
    if not current:
        return jsonify({"success": False, "message": "Not found"}), 404
    merged = {**current, **update_data}
    valid, msg = validate_repair_data(merged)
    if not valid:
        return jsonify({"success": False, "message": msg}), 400
    success, message = data_manager.update_repair_record(msn, repair_id, update_data)
    if success:
        audit_log.log_event(msn, repair_id, "UPDATE", {'role': 'OPERATOR', 'ip': request.remote_addr}, update_data)
    return jsonify({"success": success, "message": message})

@app.route('/api/report/oil_summary/<msn>', methods=['GET'])
def oil_summary(msn):
    repairs = data_manager.get_all_repairs(msn)
    open_oil = len([r for r in repairs if r.get('Audit_OIL_Status') == 'Open'])
    closed_oil = len([r for r in repairs if r.get('Audit_OIL_Status') == 'Closed'])
    non_conf = len([r for r in repairs if r.get('Audit_Physical_Status') == 'Non-Conforming'])
    return jsonify({
        "open": open_oil, "closed": closed_oil, "non_conforming": non_conf,
        "progress": round((closed_oil / len(repairs) * 100), 1) if repairs else 0
    })

@app.route('/api/export/status_report/<msn>', methods=['GET'])
def export_report(msn):
    records = data_manager.get_all_repairs(msn)
    if not records:
        return "No data", 404
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data_manager.COLUMNS)
    writer.writeheader()
    writer.writerows(records)
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={msn}_report_{datetime.now().strftime('%Y%m%d')}.csv"
    response.headers["Content-type"] = "text/csv"
    return response

# --- RUTAS WEB ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/project/create')
def project_create_page():
    return render_template('project_create.html')

@app.route('/project/select')
def project_select_page():
    projects = data_manager.get_all_projects()
    return render_template('project_select.html', projects=projects)

# --- SELECCIÓN DE ROL ---
@app.route('/role_select/<msn>', methods=['GET', 'POST'])
def role_select_web(msn):
    if request.method == 'POST':
        role = request.form.get('role')
        if role in ['operator', 'auditor', 'lessor']:
            session['role'] = role
            session['msn'] = msn
            return redirect(url_for('dashboard', msn=msn))
    return render_template('role_select.html', msn=msn)

# --- DASHBOARD CON MENÚ POR ROL ---
@app.route('/dashboard/<msn>')
def dashboard(msn):
    if 'role' not in session or session.get('msn') != msn:
        return redirect(url_for('role_select_web', msn=msn))
    
    details = data_manager.get_project_details(msn)
    if not details:
        return redirect(url_for('index'))
    
    repairs = data_manager.get_all_repairs(msn)
    oil_open = len([r for r in repairs if r.get('Audit_OIL_Status') == 'Open'])
    oil_closed = len([r for r in repairs if r.get('Audit_OIL_Status') == 'Closed'])
    non_conforming = len([r for r in repairs if r.get('Audit_Physical_Status') == 'Non-Conforming'])
    
    return render_template(
        'dashboard.html',
        msn=msn, details=details, repairs=repairs,
        role=session['role'],
        oil_open=oil_open, oil_closed=oil_closed, non_conforming=non_conforming
    )

@app.route('/edit/<msn>/<repair_id>', methods=['GET'])
def edit_repair_web(msn, repair_id):
    repair = data_manager.get_repair_record_by_id(msn, repair_id) if repair_id != 'NEW' else {}
    return render_template('edit_repair.html', msn=msn, repair=repair, repair_id=repair_id)

@app.route('/view/<msn>')
def view_repairs_web(msn):
    repairs = data_manager.get_all_repairs(msn)
    return render_template('view_repairs.html', msn=msn, repairs=repairs)

@app.route('/audit/<msn>')
def audit_dashboard_web(msn):
    return render_template('audit.html', msn=msn)

# --- RUTAS FALTANTES (PARA MENÚS) ---
@app.route('/oil_response/<msn>')
def oil_response(msn):
    return render_template('oil_response.html', msn=msn)

@app.route('/oil_audit/<msn>')
def oil_audit(msn):
    return render_template('oil_audit.html', msn=msn)

@app.route('/physical_audit/<msn>')
def physical_audit(msn):
    return render_template('physical_audit.html', msn=msn)

@app.route('/signed_reports/<msn>')
def signed_reports(msn):
    return render_template('signed_reports.html', msn=msn)

# --- ARRANQUE ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
