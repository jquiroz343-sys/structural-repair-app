from flask import Flask, render_template, jsonify, request, redirect, url_for, send_from_directory, make_response, session
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

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Render configuration
port = int(os.environ.get('PORT', 5000))

# Temporary data dir for Render
BASE_DIR = tempfile.gettempdir()
os.makedirs(BASE_DIR, exist_ok=True)
db_path = os.path.join(BASE_DIR, 'repairs.db')
dm = DataManager(db_path)

# Simple login
PASSWORD = "redelivery2025"
ROLES = {'operator': 'Operator', 'auditor': 'Auditor', 'lessor': 'Lessor'}

@app.before_request
def require_login():
    if request.endpoint not in ['login', 'static'] and 'role' not in session:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['password'] == PASSWORD:
            role = request.form['role']
            if role in ROLES:
                session['role'] = role
                log_action("LOGIN", f"{ROLES[role]} logged in")
                return redirect(url_for('dashboard'))
        flash("Invalid password or role")
    return render_template('login.html')

@app.route('/logout')
def logout():
    log_action("LOGOUT", f"{ROLES.get(session['role'], 'Unknown')} logged out")
    session.pop('role', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('login'))  # Direct to login

@app.route('/dashboard')
def dashboard():
    repairs = dm.get_all_repairs()
    return render_template('dashboard.html', repairs=repairs, role=session['role'])

@app.route('/add', methods=['GET', 'POST'])
def add_repair():
    if session['role'] != 'operator':
        flash("Only Operator can add repairs")
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        data = {k: v for k, v in request.form.items() if k != 'photos'}  # Handle all 55 fields
        files = request.files.getlist('photos')
        photo_paths = dm.save_photos(files)
        data['photos'] = ','.join(photo_paths)  # Store as comma-separated
        repair_id = dm.add_repair(data)
        log_action("ADD_REPAIR", f"ID {repair_id} by {ROLES[session['role']]}")
        return redirect(url_for('dashboard'))
    return render_template('repair_form.html', action="Add", repair=None)

@app.route('/edit/<int:repair_id>', methods=['GET', 'POST'])
def edit_repair(repair_id):
    if session['role'] not in ['operator', 'auditor']:
        flash("Access denied")
        return redirect(url_for('dashboard'))
    repair = dm.get_repair(repair_id)
    if not repair:
        flash("Repair not found")
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        data = {k: v for k, v in request.form.items() if k != 'photos'}
        files = request.files.getlist('photos')
        existing_photos = repair.get('photos', '').split(',') if repair.get('photos') else []
        photo_paths = dm.save_photos(files, existing=existing_photos)
        data['photos'] = ','.join(photo_paths)
        dm.update_repair(repair_id, data)
        log_action("EDIT_REPAIR", f"ID {repair_id} by {ROLES[session['role']]}")
        return redirect(url_for('dashboard'))
    return render_template('repair_form.html', action="Edit", repair=repair)

@app.route('/audit')
def audit_trail():
    if session['role'] not in ['auditor', 'lessor']:
        flash("Access denied")
        return redirect(url_for('dashboard'))
    logs = dm.get_audit_logs()
    return render_template('audit_trail.html', logs=logs)

@app.route('/pdf/<int:repair_id>')
def download_pdf(repair_id):
    if session['role'] == 'lessor':
        repair = dm.get_repair(repair_id)
        if repair:
            pdf_path = generate_pdf(repair, BASE_DIR)
            log_action("DOWNLOAD_PDF", f"ID {repair_id} by Lessor")
            return send_file(pdf_path, as_attachment=True, download_name=f'SRF_{repair_id}.pdf')
    flash("Only Lessor can download PDFs")
    return redirect(url_for('dashboard'))
@app.route('/oil_response/<msn>')
def oil_response(msn):
    if session.get('role') != 'operator':
        return redirect(url_for('dashboard', msn=msn))
    
    repairs = data_manager.get_all_repairs(msn)
    open_repairs = [r for r in repairs if r.get('Audit_OIL_Status') == 'Open']
    closed_repairs = [r for r in repairs if r.get('Audit_OIL_Status') == 'Closed']
    
    return render_template('oil_response.html', msn=msn, open_repairs=open_repairs, closed_repairs=closed_repairs)

# --- RUTA PARA GUARDAR RESPUESTA ---
@app.route('/api/oil/respond/<msn>/<repair_id>', methods=['POST'])
def oil_respond(msn, repair_id):
    if session.get('role') != 'operator':
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    response = request.form.get('response')
    file = request.files.get('evidence')
    
    update_data = {"Operator_Response_Note": response}
    
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{repair_id}_evidence.{ext}"
        path = os.path.join(data_manager.BASE_DIR, msn, 'docs', filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        file.save(path)
        update_data["Doc_Evidence_Path"] = filename
    
    success, msg = data_manager.update_repair_record(msn, repair_id, update_data)
    if success:
        audit_log.log_event(msn, repair_id, "OIL_RESPONSE", {'role': 'OPERATOR'}, {"response": response})
    
    return redirect(url_for('oil_response', msn=msn))
if __name__ == '__main__':

    app.run(host='0.0.0.0', port=port, debug=False)

