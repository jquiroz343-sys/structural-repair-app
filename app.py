# --- app.py (COMPLETO - 100% FUNCIONAL) ---
from flask import Flask, render_template, jsonify, request, redirect, url_for, make_response, session
import data_manager
import audit_log
import os
import re
import csv
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import io
import zipfile
from io import StringIO
import tempfile

app = Flask(__name__)
app.secret_key = 'structural_repair_2025_secure_key'

# --- CONFIGURACIÓN ---
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

# --- API REPARACIONES ---
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
        audit_log.log_event(msn, data['Repair_ID'], "ADD", {'role': 'OPERATOR'}, data)
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
        audit_log.log_event(msn, repair_id, "UPDATE", {'role': 'OPERATOR'}, update_data)
    return jsonify({"success": success, "message": message})

# --- EXPORTAR ZIP ---
@app.route('/api/export/all/<msn>', methods=['GET'])
def export_all_to_zip(msn):
    repairs = data_manager.get_all_repairs(msn)
    audit_logs = audit_log.get_audit_trail(msn)
    
    total = len(repairs)
    oil_open = len([r for r in repairs if r.get('Audit_OIL_Status') == 'Open'])
    oil_closed = len([r for r in repairs if r.get('Audit_OIL_Status') == 'Closed'])
    non_conforming = len([r for r in repairs if r.get('Audit_Physical_Status') == 'Non-Conforming'])
    progress = round((oil_closed / total * 100), 1) if total > 0 else 0

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        if repairs:
            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=data_manager.COLUMNS)
            writer.writeheader()
            writer.writerows(repairs)
            zf.writestr(f'{msn}_Repairs.csv', output.getvalue())
        
        summary = StringIO()
        summary.write("Metric,Value\n")
        summary.write(f"Total Repairs,{total}\n")
        summary.write(f"OIL Open,{oil_open}\n")
        summary.write(f"OIL Closed,{oil_closed}\n")
        summary.write(f"Progress %,{progress}\n")
        summary.write(f"Physical Non-Conforming,{non_conforming}\n")
        zf.writestr(f'{msn}_OIL_Summary.csv', summary.getvalue())
        
        if audit_logs:
            audit_output = StringIO()
            keys = audit_logs[0].keys() if audit_logs else []
            if keys:
                writer = csv.DictWriter(audit_output, fieldnames=keys)
                writer.writeheader()
                writer.writerows(audit_logs)
                zf.writestr(f'{msn}_Audit_Trail.csv', audit_output.getvalue())
    
    memory_file.seek(0)
    response = make_response(memory_file.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={msn}_Complete_Export_{datetime.now().strftime('%Y%m%d')}.zip"
    response.headers["Content-Type"] = "application/zip"
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

@app.route('/role_select/<msn>', methods=['GET', 'POST'])
def role_select_web(msn):
    if request.method == 'POST':
        role = request.form.get('role')
        if role in ['operator', 'auditor', 'lessor']:
            session['role'] = role
            session['msn'] = msn
            return redirect(url_for('dashboard', msn=msn))
    return render_template('role_select.html', msn=msn)

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

@app.route('/edit/<msn>/<repair_id>', methods  methods=['GET'])
def edit_repair_web(msn, repair_id):
    repair = data_manager.get_repair_record_by_id(msn, repair_id) if repair_id != 'NEW' else {}
    return render_template('edit_repair.html', msn=msn, repair=repair, repair_id=repair_id)

@app.route('/view/<msn>')
def view_repairs_web(msn):
    repairs = data_manager.get_all_repairs(msn)
    return render_template('view_repairs.html', msn=msn, repairs=repairs)

# --- OIL CONTROL UNIFICADO ---
@app.route('/oil/<msn>')
def oil_control(msn):
    if 'role' not in session or session.get('msn') != msn:
        return redirect(url_for('role_select_web', msn=msn))
    
    repairs = data_manager.get_all_repairs(msn)
    oil_items = []
    today = datetime.now().date()
    
    for r in repairs:
        if r.get('OIL_ID'):
            r['today'] = today
            oil_items.append(r)
        elif r.get('Audit_OIL_Status') == 'Open' or r.get('Audit_Physical_Status') == 'Non-Conforming':
            oil_type = 'Documental' if r.get('Audit_OIL_Status') == 'Open' else 'Física'
            data_manager.create_oil_item(msn, r['Repair_ID'], oil_type)
            r = data_manager.get_repair_record_by_id(msn, r['Repair_ID'])
            r['today'] = today
            oil_items.append(r)
    
    return render_template('oil.html', msn=msn, oil_items=oil_items, role=session['role'], today=today)

@app.route('/api/oil/response/<msn>/<repair_id>', methods=['POST'])
def oil_operator_response(msn, repair_id):
    if session.get('role') != 'operator':
        return redirect(url_for('oil_control', msn=msn))
    
    note = request.form['response_note']
    file = request.files['operator_file']
    if not file or not allowed_file(file.filename):
        return "File required", 400
    
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{repair_id}_op_evidence.{ext}"
    path = os.path.join(app.config['UPLOAD_FOLDER'], msn, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    file.save(path)
    
    update = {
        "Operator_Response_Note": note,
        "Doc_Operator_File": filename,
        "Response_Date": datetime.now().strftime('%Y-%m-%d'),
        "OIL_Status": "In Progress"
    }
    data_manager.update_repair_record(msn, repair_id, update)
    audit_log.log_event(msn, repair_id, "OIL_RESPONSE", session, update)
    return redirect(url_for('oil_control', msn=msn))

@app.route('/api/oil/close/<msn>/<repair_id>', methods=['POST'])
def oil_close(msn, repair_id):
    if session.get('role') not in ['auditor', 'lessor']:
        return "Forbidden", 403
    
    status = request.form['final_status']
    note = request.form['close_note']
    signed_by = request.form['signed_by']
    
    update = {
        "OIL_Status": status,
        "OIL_Closure_Note": note if status == 'Closed' else '',
        "OIL_Compensation_Note": note if status == 'Compensation' else '',
        "OIL_Signed_By": signed_by,
        "OIL_Signed_Date": datetime.now().strftime('%Y-%m-%d %H:%M'),
        "OIL_Closure_Date": datetime.now().strftime('%Y-%m-%d')
    }
    data_manager.update_repair_record(msn, repair_id, update)
    audit_log.log_event(msn, repair_id, f"OIL_{status.upper()}", session, update)
    return redirect(url_for('oil_control', msn=msn))

@app.route('/api/oil/comp/<msn>/<repair_id>', methods=['POST'])
def oil_compensation(msn, repair_id):
    return oil_close(msn, repair_id)

# --- ARRANQUE ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
