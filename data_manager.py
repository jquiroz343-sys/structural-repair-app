# --- data_manager.py (LISTO PARA RENDER - SIN CAMBIOS EN FUNCIONALIDAD) ---
import sqlite3
import os
import json
from datetime import datetime
import tempfile  # NUEVO: Para Render

# --- CONFIGURACIÓN DE LA BASE DE DATOS (PARA RENDER) ---
BASE_DIR = tempfile.gettempdir()  # Render usa /tmp
PROJECT_CONFIG_FILE = os.path.join(BASE_DIR, 'projects_data.json')
DATABASE_FILE = os.path.join(BASE_DIR, 'srf_database.db')

# --- DEFINICIÓN FINAL DE COLUMNAS (55 CAMPOS) ---
COLUMNS = [
    'Repair_ID', 'Record_Type', 'Date_Completed', 'FH_Completed', 'FC_Completed', 
    'Evaluation_SRM_Ref', 'Fatigue_Life_Data', 
    'ATA_Chapter', 'Position_Lateral', 'Position_Vertical', 'Location_Desc', 
    'Adjacent_Damage_ID', 'Component_Details', 'Zone_Stringer_Frame', 
    'Dim_Length_Width', 'Dim_Depth', 'Dim_Post_Repair_Depth', 
    'Dim_Remaining_Thk', 'Ext_Repair_Area_SqIn', 'Aero_Performance_Effect', 
    'NDT_Required_Performed', 'Design_Org_Ref', 'ETOPS_RVSM_Impact', 
    'Classification', 'Approval_Basis', 'Repair_MRO_Ref', 'Repair_Status', 
    'Threshold_Limit', 'Repeat_Interval', 'CRS_Ref', 'Logbook_Ref', 'Repair_Notes',
    'AD_SB_Reference', 'CPCP_Reference', 'Inspector_License', 'Due_Date_Repetitive', 
    'Material_PN', 'Material_Trace_Ref', 'Material_Cert_Ref',
    'Doc_CRS_Path', 'Doc_Approval_Path', 'Doc_Photo_Pre', 'Doc_Photo_Post', 
    'Doc_Drawing_Pre', 'Doc_Drawing_Post', 'Doc_Material_Cert_Path', 
    'Doc_Work_Order_Path', 'Doc_Correspondence_Path', 'Doc_NDT_Report_Path', 
    'Audit_Physical_Status', 'Audit_OIL_Status', 'Audit_Physical_Note', 
    'Audit_Documentation_Note', 'OIL_Closure_Note', 'Operator_Response_Note',
    'OIL_Priority', 'MSN'
]

def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)
    if not os.path.exists(PROJECT_CONFIG_FILE):
        with open(PROJECT_CONFIG_FILE, 'w') as f:
            json.dump({}, f)

    fields_sql = ", ".join([f'"{col}" TEXT' for col in COLUMNS])
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS repairs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        {fields_sql},
        UNIQUE(MSN, Repair_ID)
    );
    """
    with get_db_connection() as conn:
        conn.execute(create_table_sql)
        conn.commit()

initialize_database()

# --- Project Management ---
def get_all_projects():
    try:
        with open(PROJECT_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def create_new_project(msn, project_data):
    msn = msn.strip().upper()
    projects = get_all_projects()
    if msn in projects:
        return False, f"Error: Aircraft MSN '{msn}' already exists."
    project_doc_dir = os.path.join(BASE_DIR, msn, 'docs')
    if not os.path.exists(project_doc_dir):
        os.makedirs(project_doc_dir)
    projects[msn] = project_data
    with open(PROJECT_CONFIG_FILE, 'w') as f:
        json.dump(projects, f, indent=4)
    return True, f"Project '{msn}' created successfully."

def get_project_details(msn):
    return get_all_projects().get(msn, None)

# --- Repair Log Management ---
def add_repair_record(msn, record_data):
    ref_num = record_data.get('Repair_ID', '').strip()
    if not ref_num:
        return False, "Error: Repair ID cannot be empty."
    processed_data = {col: record_data.get(col, '') for col in COLUMNS}
    processed_data['MSN'] = msn
    col_names = ", ".join([f'"{col}"' for col in processed_data.keys()])
    placeholders = ", ".join(["?"] * len(processed_data))
    values = list(processed_data.values())
    sql = f"INSERT INTO repairs ({col_names}) VALUES ({placeholders})"
    try:
        with get_db_connection() as conn:
            conn.execute(sql, values)
            conn.commit()
        return True, "Repair record added successfully."
    except sqlite3.IntegrityError:
        return False, f"Error: Repair ID '{ref_num}' already exists in project {msn}."
    except Exception as e:
        return False, f"An error occurred: {e}"

def update_repair_record(msn, repair_id, update_data):
    valid_update_data = {k: v for k, v in update_data.items() if k in COLUMNS}
    if not valid_update_data:
        return False, "Error: No valid fields provided for update."
    set_clause = ", ".join([f'"{key}" = ?' for key in valid_update_data.keys()])
    values = list(valid_update_data.values())
    sql = f"UPDATE repairs SET {set_clause} WHERE MSN = ? AND Repair_ID = ?"
    values.extend([msn, repair_id])
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, values)
            conn.commit()
            if cursor.rowcount == 0:
                return False, f"Error: Repair ID '{repair_id}' not found in project {msn}."
        return True, f"Repair record '{repair_id}' updated successfully."
    except Exception as e:
        return False, f"An error occurred during update: {e}"

def get_all_repairs(msn):
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM repairs WHERE MSN = ?", (msn,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_repair_record_by_id(msn, repair_id):
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM repairs WHERE MSN = ? AND Repair_ID = ?", (msn, repair_id))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def search_repairs(msn, column, value):
    if column not in COLUMNS:
        return []
    sql = f'SELECT * FROM repairs WHERE MSN = ? AND "{column}" LIKE ?'
    search_value = f"%{value}%"
    with get_db_connection() as conn:
        cursor = conn.execute(sql, (msn, search_value))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
