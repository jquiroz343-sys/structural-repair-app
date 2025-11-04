# app.py - FINAL VERSION: AIRCRAFT, NO PHYSICAL AUDIT, OIL UNIFIED
from flask import Flask, render_template, jsonify, request, redirect, url_for, make_response, session, send_from_directory
import data_manager
import audit_log
import os
import re
import csv
from werkzeug.utils import secure_filename
from datetime import datetime
import io
import zipfile
from io import StringIO
import tempfile

app = Flask(__name__)
app.secret_key = 'structural_repair_2025_secure_key'

# --- JINJA FILTER: STRPTIME ---
@app.template_filter('strptime')
def _jinja2_filter_strptime(date_string, fmt='%Y-%m-%d'):
    try:
        return datetime.strptime(date_string, fmt)
    except:
        return datetime.now()

# --- UPLOAD CONFIG ---
BASE_DIR = tempfile.gettempdir()
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tif', 'tiff', 'dwg', 'dxf', 'doc', 'docx', 'xls', 'xlsx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- DATA VALIDATION ---
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

# =============================
# API ENDPOINTS
# =============================

@app.route('/api/projects/create', methods=['POST'])
def create_project_api():
    project_data = request.json
    msn = project_data.pop('msn', '').strip().upper()
    if not msn:
        return jsonify({"success": False, "message": "MSN is required."}), 400
    project_data['Aircraft_Type'] = project_data.get('Aircraft_Type', 'N/A')
    success, message = data_manager.create_new_project(msn, project_data)
    if success:
        audit_log.log_event(msn, "PROJECT", "CREATE", {'role': 'SETUP'}, project_data)
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

# --- EXPORT ALL ---
@app.route('/api/export/all/<msn>', methods=['GET'])
def export_all_to_zip(msn):
    repairs = data_manager.get_all_repairs(msn)
    audit_logs = audit_log.get_audit_trail(msn)
    
    total = len(repairs)
    oil_open = len([r for r in repairs if r.get('OIL_Status') == 'Open'])
    oil_closed = len([r for r in repairs if r.get('OIL_Status') == 'Closed'])
    non_conforming = len([r for r in repairs if r.get('OIL_Type') == 'Physical' and r.get('OIL_Status') != 'Closed'])
    progress = round((oil_closed / total * 100), 1) if total > 0 else 0

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        if repairs:
            output = StringIO()
            filtered_repairs = [{k: r.get(k, '') for k in data_manager.COLUMNS} for r in repairs]
            writer = csv.DictWriter(output, fieldnames=data_manager.COLUMNS)
            writer.writeheader()
            writer.writerows(filtered_repairs)
            zf.writestr(f'{msn}_Repairs.csv', output.getvalue())
        
        summary = StringIO()
        summary.write("Metric,Value\n")
        summary.write(f"Total Repairs,{total}\n")
        summary.write(f"OIL Open,{oil_open}\n")
        summary.write(f"OIL Closed,{oil_closed}\n")
        summary.write(f"Progress %,{progress}\n")
        summary.write(f"Non-Conforming (Physical),{non_conforming}\n")
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

# =============================
# WEB ROUTES
# =============================

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

# --- DASHBOARD: CONSISTENT DATA ---
@app.route('/dashboard/<msn>')
def dashboard(msn):
    if 'role' not in session or session.get('msn') != msn:
        return redirect(url_for('role_select_web', msn=msn))
    
    details = data_manager.get_project_details(msn)
    if not details:
        return redirect(url_for('index'))
    
    repairs = data_manager.get_all_repairs(msn)

    total_repairs = len(repairs)
    oil_open = len([r for r in repairs if r.get('OIL_Status') == 'Open'])
    oil_closed = len([r for r in repairs if r.get('OIL_Status') == 'Closed'])
    non_conforming = len([r for r in repairs if r.get('OIL_Type') == 'Physical' and r.get('OIL_Status') != 'Closed'])

    return render_template(
        'dashboard.html',
        msn=msn,
        details=details,
        repairs=repairs,
        role=session['role'],
        total_repairs=total_repairs,
        oil_open=oil_open,
        oil_closed=oil_closed,
        non_conforming=non_conforming
    )

@app.route('/edit/<msn>/<repair_id>', methods=['GET'])
def edit_repair_web(msn, repair_id):
    if session.get('role') != 'operator':
        return redirect(url_for('dashboard', msn=msn))
    repair = data_manager.get_repair_record_by_id(msn, repair_id) if repair_id != 'NEW' else {}
    return render_template('edit_repair.html', msn=msn, repair=repair, repair_id=repair_id)

@app.route('/view/<msn>')
def view_repairs_web(msn):
    repairs = data_manager.get_all_repairs(msn)
    return render_template('view_repairs.html', msn=msn, repairs=repairs)

# =============================
# OIL CONTROL (UNIFIED)
# =============================

@app.route('/oil/<msn>')
def oil_control(msn):
    if 'role' not in session or session.get('msn') != msn:
        return redirect(url_for('role_select_web', msn=msn))
    
    repairs = data_manager.get_all_repairs(msn)
    oil_items = [r for r in repairs if r.get('OIL_ID')]
    all_repairs = [r for r in repairs if not r.get('OIL_ID')]
    today = datetime.now().date()
    
    return render_template(
        'oil.html',
        msn=msn,
        oil_items=oil_items,
        all_repairs=all_repairs,
        role=session['role'],
        today=today
    )

@app.route('/api/oil/add/<msn>', methods=['POST'])
def oil_add_discrepancy(msn):
    if session.get('role') not in ['auditor', 'lessor']:
        return "Forbidden: Only Auditor or Lessor", 403
    
    repair_id = request.form['repair_id']
    oil_type = request.form['oil_type']
    audit_note = request.form['audit_note']
    file = request.files.get('audit_file')

    repair = data_manager.get_repair_record_by_id(msn, repair_id)
    if not repair or repair.get('OIL_ID'):
        return "Repair already has OIL", 400

    data_manager.create_oil_item(msn, repair_id, oil_type)
    update = {
        "OIL_Audit_Note": audit_note,
        "OIL_Type": oil_type
    }
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{repair_id}_audit_evidence.{ext}"
        path = os.path.join(app.config['UPLOAD_FOLDER'], msn, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        file.save(path)
        update["Doc_Audit_File"] = filename

    data_manager.update_repair_record(msn, repair_id, update)
    audit_log.log_event(msn, repair_id, "OIL_CREATED", session, update)
    return redirect(url_for('oil_control', msn=msn))

@app.route('/api/oil/response/<msn>/<repair_id>', methods=['POST'])
def oil_operator_response(msn, repair_id):
    if session.get('role') != 'operator':
        return "Forbidden: Only Operator", 403
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
        return "Forbidden: Only Auditor or Lessor can close", 403

    repair = data_manager.get_repair_record_by_id(msn, repair_id)
    if not repair or repair.get('OIL_Status') != 'In Progress':
        return "Cannot close: Item not in progress", 400

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

# =============================
# OTHER ROUTES
# =============================

@app.route('/signed_oil_report/<msn>')
def signed_oil_report(msn):
    if session.get('role') not in ['auditor', 'lessor']:
        return redirect(url_for('dashboard', msn=msn))
    repairs = data_manager.get_all_repairs(msn)
    closed_oil = [r for r in repairs if r.get('OIL_Status') == 'Closed']
    return render_template('signed_oil_report.html', msn=msn, closed_oil=closed_oil, role=session['role'])

@app.route('/api/audit_trail/<msn>/<repair_id>')
def get_audit_trail_by_repair(msn, repair_id):
    logs = audit_log.get_audit_trail(msn)
    repair_logs = [log for log in logs if log.get('repair_id') == repair_id]
    return jsonify(repair_logs)

@app.route('/logout/<msn>')
def logout(msn):
    session.pop('role', None)
    session.pop('msn', None)
    return redirect(url_for('role_select_web', msn=msn))

@app.route('/api/documents/download/<msn>/<filename>')
def download_file(msn, filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], msn, filename)
    if os.path.exists(file_path):
        return send_from_directory(os.path.dirname(file_path), filename, as_attachment=True)
    return "File not found", 404

# =============================
# RUN APP
# =============================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
