# --- app.py (COMPLETO - CON RUTA ROLE_SELECT) ---
from flask import Flask, render_template, jsonify, request, redirect, url_for, send_from_directory, make_response
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
app.secret_key = 'your_strong_secret_key' 

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
        return False, "Validation Error: Repair ID is mandatory."
    ata_chapter = record_data.get('ATA_Chapter', '')
    if ata_chapter and not ata_chapter.upper().startswith('ATA '):
        return False, "Validation Error: ATA Chapter format must start with 'ATA ' (or be left empty)."
    date_val = record_data.get('Date_Completed', '')
    if date_val and not re.match(r'^\d{4}-\d{2}-\d{2}$', date_val):
        return False, "Validation Error: Date Completed must be in YYYY-MM-DD format (or left empty)."

    numeric_fields = [
        ('FH_Completed', r'^\d+$', "non-negative integer"), 
        ('FC_Completed', r'^\d+$', "non-negative integer"),
        ('Dim_Length_Width', r'^\d+([.,]\d+)?$', "positive number"), 
        ('Dim_Depth', r'^\d+([.,]\d+)?$', "positive number"), 
        ('Dim_Remaining_Thk', r'^\d+([.,]\d+)?$', "positive number"), 
        ('Ext_Repair_Area_SqIn', r'^\d+([.,]\d+)?$', "positive number"),
        ('Threshold_Limit', r'^\d+([.,]\d+)?$', "positive number"),
        ('Repeat_Interval', r'^\d+([.,]\d+)?$', "positive number")
    ]
    for field, pattern, expected_format in numeric_fields:
        value = str(record_data.get(field, '')).strip().replace(',', '.')
        if value and not re.match(pattern, value):
            return False, f"Validation Error: '{field}' must be a {expected_format} (or left empty)."
    status = record_data.get('Repair_Status')
    if status in ["Time-Limited", "Repetitive", "Interim", "Allowable Damage (Cat B)"]:
        threshold = str(record_data.get('Threshold_Limit', '')).strip()
        interval = str(record_data.get('Repeat_Interval', '')).strip()
        if not threshold and not interval:
             return False, f"Validation Error: Threshold or Interval is mandatory for the selected Repair Status ('{status}')."
    return True, None

@app.route('/api/projects/create', methods=['POST'])
def create_project_api():
    project_data = request.json
    msn = project_data.pop('msn', '').strip().upper()
    if not msn:
        return jsonify({"success": False, "message": "Aircraft MSN is mandatory."}), 400
    if 'Aircraft_Type' not in project_data:
        project_data['Aircraft_Type'] = 'N/A'
    success, message = data_manager.create_new_project(msn, project_data)
    if success:
        audit_log.log_event(msn, "PROJECT_SETUP", "CREATE_PROJECT", {'role': 'SETUP', 'ip': request.remote_addr, 'name': 'N/A'}, data_changed=project_data)
    return jsonify({"success": success, "message": message})

@app.route('/api/repairs/<msn>', methods=['GET'])
def get_repairs(msn):
    records = data_manager.get_all_repairs(msn)
    return jsonify(records)

@app.route('/api/repairs/<msn>/<repair_id>', methods=['GET'])
def get_repair(msn, repair_id):
    record = data_manager.get_repair_record_by_id(msn, repair_id)
    if record:
        return jsonify(record)
    return jsonify({"error": f"Repair ID {repair_id} not found."}), 404

@app.route('/api/repairs/add/<msn>', methods=['POST'])
def add_repair(msn):
    record_data = request.json
    is_valid, validation_message = validate_repair_data(record_data)
    if not is_valid:
        return jsonify({"success": False, "message": validation_message}), 400
    success, message = data_manager.add_repair_record(msn, record_data)
    if success:
        audit_log.log_event(msn, record_data['Repair_ID'], "ADD_RECORD", {'role': 'OPERATOR', 'ip': request.remote_addr, 'name': 'N/A'}, data_changed=record_data)
    return jsonify({"success": success, "message": message})

@app.route('/api/repairs/update/<msn>/<repair_id>', methods=['PUT'])
def update_repair(msn, repair_id):
    update_data = request.json
    current_data = data_manager.get_repair_record_by_id(msn, repair_id)
    if not current_data:
        return jsonify({"success": False, "message": f"Repair ID {repair_id} not found for update."}), 404
    merged_data = {**current_data, **update_data}
    is_valid, validation_message = validate_repair_data(merged_data)
    if not is_valid:
        return jsonify({"success": False, "message": validation_message}), 400
    success, message = data_manager.update_repair_record(msn, repair_id, update_data)
    if success:
        audit_log.log_event(msn, repair_id, "UPDATE_RECORD", {'role': 'OPERATOR', 'ip': request.remote_addr, 'name': 'N/A'}, data_changed=update_data)
    return jsonify({"success": success, "message": message})

@app.route('/api/report/oil_summary/<msn>', methods=['GET'])
def get_oil_summary(msn):
    records = data_manager.get_all_repairs(msn)
    total_records = len(records)
    oil_open = len([r for r in records if r['Audit_OIL_Status'] == 'Open'])
    oil_closed = len([r for r in records if r['Audit_OIL_Status'] == 'Closed'])
    phys_non_conforming = len([r for r in records if r['Audit_Physical_Status'] == 'Non-Conforming'])
    audit_log_data = audit_log.get_audit_trail(msn)
    user_activity = {}
    for log in audit_log_data:
        user_name = log.get('user_name', 'N/A')
        user_activity[user_name] = user_activity.get(user_name, 0) + 1
    return jsonify({
        "msn": msn, "total_records": total_records,
        "oil_status": {"open": oil_open, "closed": oil_closed, "progress_percent": total_records > 0 and round((oil_closed / total_records) * 100, 1) or 0},
        "inspection_status": {"phys_non_conforming": phys_non_conforming},
        "staff_activity": user_activity
    })

@app.route('/api/export/status_report/<msn>', methods=['GET'])
def export_status_report(msn):
    records = data_manager.get_all_repairs(msn)
    if not records:
        return "No data to export", 404
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data_manager.COLUMNS)
    writer.writeheader()
    writer.writerows(records)
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={msn}_SRR_Status_Report_{datetime.now().strftime('%Y%m%d')}.csv"
    response.headers["Content-type"] = "text/csv"
    return response

@app.route('/api/audit_trail/<msn>/<repair_id>', methods=['GET'])
@app.route('/api/audit_trail/<msn>', methods=['GET'])
def get_audit_trail_api(msn, repair_id=None):
    logs = audit_log.get_audit_trail(msn, repair_id)
    return jsonify(logs)

@app.route('/api/documents/upload/<msn>/<repair_id>/<doc_field>', methods=['POST'])
def upload_document(msn, repair_id, doc_field):
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file part in the request."}), 400
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"success": False, "message": "No file selected or extension not allowed."}), 400
    project_doc_dir = os.path.join(data_manager.BASE_DIR, msn, 'docs')
    if not os.path.exists(project_doc_dir):
        os.makedirs(project_doc_dir)
    original_ext = file.filename.rsplit('.', 1)[1].lower()
    new_filename = f"{secure_filename(repair_id)}_{doc_field}.{original_ext}"
    save_path = os.path.join(project_doc_dir, new_filename)
    try:
        file.save(save_path)
        update_data = {doc_field: new_filename}
        success, message = data_manager.update_repair_record(msn, repair_id, update_data)
        if success:
            audit_log.log_event(msn, repair_id, "UPLOAD_DOC", {'role': 'OPERATOR', 'ip': request.remote_addr, 'name': 'N/A'}, data_changed={doc_field: new_filename})
            return jsonify({"success": True, "message": "File uploaded and record updated.", "stored_filename": new_filename})
        else:
            os.remove(save_path)
            return jsonify({"success": False, "message": f"File uploaded but failed to update record: {message}"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": f"Server error during file saving: {str(e)}"}), 500

@app.route('/api/documents/download/<msn>/<filename>', methods=['GET'])
def download_document(msn, filename):
    doc_dir = os.path.join(data_manager.BASE_DIR, msn, 'docs')
    return send_from_directory(doc_dir, secure_filename(filename), as_attachment=True)

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

@app.route('/dashboard/<msn>')
def dashboard(msn):
    project_details = data_manager.get_project_details(msn)
    if not project_details:
        return redirect(url_for('index'))
    return render_template('dashboard.html', msn=msn, details=project_details)

@app.route('/view/<msn>')
def view_repairs_web(msn):
    return render_template('view_repairs.html', msn=msn) 

@app.route('/edit/<msn>/<repair_id>', methods=['GET'])
def edit_repair_web(msn, repair_id):
    repair = data_manager.get_repair_record_by_id(msn, repair_id)
    return render_template('edit_repair.html', msn=msn, repair_id=repair_id, repair=repair)

@app.route('/audit/<msn>')
def audit_dashboard_web(msn):
    return render_template('audit.html', msn=msn)

# --- RUTA QUE FALTABA ---
@app.route('/role_select/<msn>')
def role_select_web(msn):
    return redirect(url_for('dashboard', msn=msn))

# --- ARRANQUE ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
