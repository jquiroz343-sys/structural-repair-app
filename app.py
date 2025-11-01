from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
import os
import tempfile
import secrets
from data_manager import DataManager
from pdf_generator import generate_pdf
from audit_log import log_action

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# === CONFIGURACIÓN PARA RENDER: Puerto dinámico ===
port = int(os.environ.get('PORT', 5000))  # Render usa PORT, local usa 5000

# Carpeta temporal para datos en Render (persiste durante la sesión)
BASE_DIR = tempfile.gettempdir()
os.makedirs(BASE_DIR, exist_ok=True)
db_path = os.path.join(BASE_DIR, 'repairs.db')
dm = DataManager(db_path)

# Login simple
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
        flash("Contraseña o rol incorrecto")
    return render_template('login.html')

@app.route('/logout')
def logout():
    log_action("LOGOUT", f"{ROLES.get(session['role'], 'Unknown')} logged out")
    session.pop('role', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    repairs = dm.get_all_repairs()
    return render_template('dashboard.html', repairs=repairs, role=session['role'])

@app.route('/add', methods=['GET', 'POST'])
def add_repair():
    if session['role'] != 'operator':
        flash("Solo el Operador puede añadir reparaciones")
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        data = request.form.to_dict()
        files = request.files.getlist('photos')
        photo_paths = dm.save_photos(files)
        data['photos'] = photo_paths
        repair_id = dm.add_repair(data)
        log_action("ADD_REPAIR", f"ID {repair_id} por {ROLES[session['role']]}")
        return redirect(url_for('dashboard'))
    return render_template('repair_form.html', action="Añadir")

@app.route('/edit/<int:repair_id>', methods=['GET', 'POST'])
def edit_repair(repair_id):
    if session['role'] not in ['operator', 'auditor']:
        flash("Acceso denegado")
        return redirect(url_for('dashboard'))
    repair = dm.get_repair(repair_id)
    if not repair:
        flash("Reparación no encontrada")
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        data = request.form.to_dict()
        files = request.files.getlist('photos')
        photo_paths = dm.save_photos(files, existing=repair.get('photos', []))
        data['photos'] = photo_paths
        dm.update_repair(repair_id, data)
        log_action("EDIT_REPAIR", f"ID {repair_id} por {ROLES[session['role']]}")
        return redirect(url_for('dashboard'))
    return render_template('repair_form.html', action="Editar", repair=repair)

@app.route('/audit')
def audit_trail():
    if session['role'] not in ['auditor', 'lessor']:
        flash("Acceso denegado")
        return redirect(url_for('dashboard'))
    logs = dm.get_audit_logs()
    return render_template('audit_trail.html', logs=logs)

@app.route('/pdf/<int:repair_id>')
def download_pdf(repair_id):
    if session['role'] == 'lessor':
        repair = dm.get_repair(repair_id)
        if repair:
            pdf_path = generate_pdf(repair, BASE_DIR)
            log_action("DOWNLOAD_PDF", f"ID {repair_id} por Lessor")
            return send_file(pdf_path, as_attachment=True)
    flash("Solo el Lessor puede descargar PDFs")
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    # ¡CLAVE PARA RENDER! Bind a 0.0.0.0 y puerto dinámico
    app.run(host='0.0.0.0', port=port, debug=False)