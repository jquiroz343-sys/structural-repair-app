# --- app.py (COMPLETO - FLUJO ORIGINAL + ROLES) ---
from flask import Flask, render_template, jsonify, request, redirect, url_for, send_from_directory, make_response, session
import data_manager
import audit_log
import os
import re
import csv 
from werkzeug.utils import secure_filename
from datetime import datetime
import tempfile
import io
import zipfile
from io import StringIO
pd.set_option('mode.chained_assignment', None)  # Evita warnings

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
# --- OIL AUDIT PAGE ---
@app.route('/oil_audit/<msn>')
def oil_audit(msn):
    if session.get('role') not in ['auditor', 'lessor']:
        return redirect(url_for('dashboard', msn=msn))
    
    repairs = data_manager.get_all_repairs(msn)
    oil_items = [r for r in repairs if r.get('Audit_OIL_Status') in ['Open', 'In Review']]
    return render_template('oil_audit.html', msn=msn, oil_items=oil_items, role=session['role'])

# --- API: AUDITOR ACTION ON OIL ---
@app.route('/api/oil/audit/<msn>/<repair_id>', methods=['POST'])
def oil_audit_action(msn, repair_id):
    if session.get('role') not in ['auditor', 'lessor']:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    action = request.form.get('action')
    note = request.form.get('audit_note')
    file = request.files.get('audit_doc')
    
    update_data = {}
    if action == 'request_more':
        update_data['Audit_OIL_Status'] = 'Open'
        update_data['OIL_Closure_Note'] = (update_data.get('OIL_Closure_Note', '') + f"\n[Auditor Request {datetime.now().strftime('%Y-%m-%d')}]: {note}").strip()
    elif action == 'close':
        update_data['Audit_OIL_Status'] = 'Closed'
        update_data['OIL_Closure_Note'] = (update_data.get('OIL_Closure_Note', '') + f"\n[Closed {datetime.now().strftime('%Y-%m-%d')}]: {note}").strip()
    
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{repair_id}_audit_doc.{ext}"
        path = os.path.join(data_manager.BASE_DIR, msn, 'docs', filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        file.save(path)
        update_data["Doc_Audit_Path"] = filename
    
    success, msg = data_manager.update_repair_record(msn, repair_id, update_data)
    if success:
        audit_log.log_event(msn, repair_id, f"OIL_AUDIT_{action.upper()}", {'role': session['role']}, {"note": note})
    
    return redirect(url_for('oil_audit', msn=msn))
    # --- PHYSICAL AUDIT PAGE ---
@app.route('/physical_audit/<msn>')
def physical_audit(msn):
    if session.get('role') not in ['auditor', 'lessor']:
        return redirect(url_for('dashboard', msn=msn))
    
    repairs = data_manager.get_all_repairs(msn)
    # Mostrar solo reparaciones con foto post-reparación
    physical_items = [r for r in repairs if r.get('Doc_Photo_Post') and r.get('Audit_Physical_Status') != 'Conforming']
    return render_template('physical_audit.html', msn=msn, physical_items=physical_items, role=session['role'])

# --- API: PHYSICAL AUDIT ACTION ---
@app.route('/api/physical/audit/<msn>/<repair_id>', methods=['POST'])
def physical_audit_action(msn, repair_id):
    if session.get('role') not in ['auditor', 'lessor']:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    action = request.form.get('action')
    note = request.form.get('physical_note')
    file = request.files.get('inspection_photo')
    
    update_data = {
        "Audit_Physical_Note": note,
        "Audit_Physical_Status": "Non-Conforming" if action == "non_conforming" else "Conforming"
    }
    
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{repair_id}_inspection.{ext}"
        path = os.path.join(data_manager.BASE_DIR, msn, 'docs', filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        file.save(path)
        update_data["Doc_Inspection_Photo"] = filename
    
    success, msg = data_manager.update_repair_record(msn, repair_id, update_data)
    if success:
        audit_log.log_event(msn, repair_id, f"PHYSICAL_AUDIT_{action.upper()}", {'role': session['role']}, {"note": note})
    
    return redirect(url_for('physical_audit', msn=msn))
    # --- SIGNED REPORTS PAGE ---
@app.route('/signed_reports/<msn>')
def signed_reports(msn):
    if session.get('role') not in ['auditor', 'lessor']:
        return redirect(url_for('dashboard', msn=msn))
    
    repairs = data_manager.get_all_repairs(msn)
    closed_oil = [r for r in repairs if r.get('Audit_OIL_Status') == 'Closed']
    
    return render_template('signed_reports.html', msn=msn, closed_oil=closed_oil, role=session['role'])
    # --- IMPORTS PARA EXCEL ---
import pandas as pd
from io import BytesIO

import zipfile
from io import StringIO

@app.route('/api/export/all/<msn>', methods=['GET'])
def export_all_to_zip(msn):
    repairs = data_manager.get_all_repairs(msn)
    audit_logs = audit_log.get_audit_trail(msn)
    
    # OIL Summary
    oil_open = len([r for r in repairs if r.get('Audit_OIL_Status') == 'Open'])
    oil_closed = len([r for r in repairs if r.get('Audit_OIL_Status') == 'Closed'])
    non_conforming = len([r for r in repairs if r.get('Audit_Physical_Status') == 'Non-Conforming'])
    total = len(repairs)
    progress = round((oil_closed / total * 100), 1) if total > 0 else 0

    # Crear ZIP en memoria
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        
        # 1. Repairs.csv
        if repairs:
            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=data_manager.COLUMNS)
            writer.writeheader()
            writer.writerows(repairs)
            zf.writestr(f'{msn}_Repairs.csv', output.getvalue())
        
        # 2. OIL_Summary.csv
        summary = StringIO()
        summary.write("Metric,Value\n")
        summary.write(f"Total Repairs,{total}\n")
        summary.write(f"OIL Open,{oil_open}\n")
        summary.write(f"OIL Closed,{oil_closed}\n")
        summary.write(f"Progress %,{progress}\n")
        summary.write(f"Physical Non-Conforming,{non_conforming}\n")
        zf.writestr(f'{msn}_OIL_Summary.csv', summary.getvalue())
        
        # 3. Audit_Trail.csv
        if audit_logs:
            audit_output = StringIO()
            if audit_logs:
                keys = audit_logs[0].keys()
                writer = csv.DictWriter(audit_output, fieldnames=keys)
                writer.writeheader()
                writer.writerows(audit_logs)
                zf.writestr(f'{msn}_Audit_Trail.csv', audit_output.getvalue())
    
    memory_file.seek(0)
    response = make_response(memory_file.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={msn}_Complete_Export_{datetime.now().strftime('%Y%m%d')}.zip"
    response.headers["Content-Type"] = "application/zip"
    return response
    # Obtener datos
    repairs = data_manager.get_all_repairs(msn)
    audit_logs = audit_log.get_audit_trail(msn)
    
    # OIL Summary
    oil_open = len([r for r in repairs if r.get('Audit_OIL_Status') == 'Open'])
    oil_closed = len([r for r in repairs if r.get('Audit_OIL_Status') == 'Closed'])
    non_conforming = len([r for r in repairs if r.get('Audit_Physical_Status') == 'Non-Conforming'])
    oil_data = {
        'Total Repairs': [len(repairs)],
        'OIL Open': [oil_open],
        'OIL Closed': [oil_closed],
        'Progress %': [round((oil_closed / len(repairs) * 100), 1) if repairs else 0],
        'Physical Non-Conforming': [non_conforming]
    }
    oil_df = pd.DataFrame(oil_data)

    # Audit Trail
    audit_df = pd.DataFrame(audit_logs)

    # Crear Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Hoja 1: Repairs (55 campos)
        if repairs:
            repairs_df = pd.DataFrame(repairs)
            repairs_df.to_excel(writer, sheet_name='Repairs', index=False)
        else:
            pd.DataFrame().to_excel(writer, sheet_name='Repairs', index=False)
        
        # Hoja 2: OIL Summary
        oil_df.to_excel(writer, sheet_name='OIL_Summary', index=False)
        
        # Hoja 3: Audit Trail
        if audit_logs:
            audit_df.to_excel(writer, sheet_name='Audit_Trail', index=False)
        else:
            pd.DataFrame().to_excel(writer, sheet_name='Audit_Trail', index=False)

    output.seek(0)
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={msn}_Complete_Export_{datetime.now().strftime('%Y%m%d')}.xlsx"
    response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return response
# --- ARRANQUE ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)






