# --- data_manager.py (CÓDIGO COMPLETO - MIGRADO A SQLITE) ---

import sqlite3
import os
import json
from datetime import datetime

# --- CONFIGURACIÓN DE LA BASE DE DATOS ---
BASE_DIR = r'G:\Mi unidad\Structural_Repair_App_Data' # aca esta la pepa que debes cambiar si usas otro computador
PROJECT_CONFIG_FILE = os.path.join(BASE_DIR, 'projects_data.json')
# Usaremos una única base de datos para toda la aplicación
DATABASE_FILE = os.path.join(BASE_DIR, 'srf_database.db')

# --- DEFINICIÓN FINAL DE COLUMNAS (55 CAMPOS) ---
# Incluye los 47 originales + 8 campos de la auditoría IATA
COLUMNS = [
    # A. General Identification (7)
    'Repair_ID', 'Record_Type', 'Date_Completed', 'FH_Completed', 'FC_Completed', 
    'Evaluation_SRM_Ref', 'Fatigue_Life_Data', 
    
    # B. Location (7) - Añadido Zone/Stringer/Frame
    'ATA_Chapter', 'Position_Lateral', 'Position_Vertical', 'Location_Desc', 
    'Adjacent_Damage_ID', 'Component_Details',
    'Zone_Stringer_Frame', # NUEVO (Auditoría)
    
    # C. Dimensions & Effects (9) - Añadido ETOPS/RVSM Impact
    'Dim_Length_Width', 'Dim_Depth', 'Dim_Post_Repair_Depth', 
    'Dim_Remaining_Thk', 'Ext_Repair_Area_SqIn', 'Aero_Performance_Effect', 
    'NDT_Required_Performed', 'Design_Org_Ref', 
    'ETOPS_RVSM_Impact', # NUEVO (Auditoría)
    
    # D. Certification & Limits (13) - Añadidos AD/SB, CPCP, Due_Date, Inspector_License
    'Classification', 'Approval_Basis', 'Repair_MRO_Ref', 'Repair_Status', 
    'Threshold_Limit', 'Repeat_Interval', 'CRS_Ref', 'Logbook_Ref', 'Repair_Notes',
    'AD_SB_Reference', # NUEVO (Auditoría)
    'CPCP_Reference', # NUEVO (Auditoría)
    'Inspector_License', # NUEVO (Auditoría)
    'Due_Date_Repetitive', # NUEVO (Auditoría)
    
    # E. Material Traceability (3)
    'Material_PN', 'Material_Trace_Ref', 'Material_Cert_Ref',
    
    # F. Documentation Paths (10)
    'Doc_CRS_Path', 'Doc_Approval_Path', 'Doc_Photo_Pre', 'Doc_Photo_Post', 
    'Doc_Drawing_Pre', 'Doc_Drawing_Post', 'Doc_Material_Cert_Path', 
    'Doc_Work_Order_Path', 'Doc_Correspondence_Path', 'Doc_NDT_Report_Path', 
    
    # G. Audit/OIL Fields (7) - Añadido OIL Priority
    'Audit_Physical_Status', 'Audit_OIL_Status', 'Audit_Physical_Note', 
    'Audit_Documentation_Note', 'OIL_Closure_Note', 'Operator_Response_Note',
    'OIL_Priority', # NUEVO (Auditoría)
    
    # CAMPO DE CONTROL (1)
    'MSN' # Clave foránea para vincular al proyecto
]

def get_db_connection():
    """Crea una conexión a la base de datos."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    """Crea la tabla de reparaciones si no existe, incluyendo los 55 campos."""
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)
        
    # Crear el JSON de configuración de proyectos si no existe
    if not os.path.exists(PROJECT_CONFIG_FILE):
        with open(PROJECT_CONFIG_FILE, 'w') as f:
            json.dump({}, f)

    # Crear la tabla SQL
    # Genera dinámicamente "fieldname TEXT" para todos los 55 campos
    fields_sql = ", ".join([f'"{col}" TEXT' for col in COLUMNS])
    
    # Repair_ID y MSN son claves para la búsqueda
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

# Inicializar la base de datos al cargar el módulo
initialize_database()

# --- Project Management (Sigue usando JSON para metadatos) ---

def get_all_projects():
    try:
        with open(PROJECT_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def create_new_project(msn, project_data):
    """Crea un nuevo proyecto en el JSON. La tabla SQL ya está lista."""
    msn = msn.strip().upper()
    projects = get_all_projects()
    if msn in projects:
        return False, f"Error: Aircraft MSN '{msn}' already exists."

    # Crea la carpeta de documentos (si no existe)
    project_doc_dir = os.path.join(BASE_DIR, msn, 'docs')
    if not os.path.exists(project_doc_dir):
        os.makedirs(project_doc_dir)

    projects[msn] = project_data
    with open(PROJECT_CONFIG_FILE, 'w') as f:
        json.dump(projects, f, indent=4)
        
    return True, f"Project '{msn}' created successfully."

def get_project_details(msn):
    return get_all_projects().get(msn, None)

# --- Repair Log Management (Ahora usa SQLITE) ---

def add_repair_record(msn, record_data):
    """Añade un nuevo registro de reparación a la base de datos SQL."""
    ref_num = record_data.get('Repair_ID', '').strip()
    if not ref_num:
        return False, "Error: Repair ID cannot be empty."

    # Asegurar que todos los campos (55) estén presentes, defaulting a ''
    processed_data = {col: record_data.get(col, '') for col in COLUMNS}
    processed_data['MSN'] = msn # Añadir la clave foránea del MSN

    # Crear la consulta SQL dinámicamente
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
    """Actualiza un registro existente en la base de datos SQL."""
    
    # Filtrar solo los campos que están en la definición de la tabla
    valid_update_data = {k: v for k, v in update_data.items() if k in COLUMNS}
    
    if not valid_update_data:
        return False, "Error: No valid fields provided for update."

    # Crear la parte SET de la consulta
    set_clause = ", ".join([f'"{key}" = ?' for key in valid_update_data.keys()])
    values = list(valid_update_data.values())
    
    # Añadir los filtros WHERE
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
    """Obtiene todos los registros para un MSN específico."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM repairs WHERE MSN = ?", (msn,))
        rows = cursor.fetchall()
        # Convertir las filas (sqlite3.Row) a diccionarios
        return [dict(row) for row in rows]

def get_repair_record_by_id(msn, repair_id):
    """Obtiene un solo registro por MSN y Repair_ID."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM repairs WHERE MSN = ? AND Repair_ID = ?", (msn, repair_id))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def search_repairs(msn, column, value):
    """Busca registros que coincidan parcialmente (LIKE) en una columna."""
    if column not in COLUMNS:
        return []
        
    # Usar LIKE para búsqueda parcial
    sql = f'SELECT * FROM repairs WHERE MSN = ? AND "{column}" LIKE ?'
    search_value = f"%{value}%"
    
    with get_db_connection() as conn:
        cursor = conn.execute(sql, (msn, search_value))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
# --- FUNCIÓN FALTANTE: CREAR PROYECTO ---
def create_project(msn, project_data):
    """Crea un nuevo proyecto (MSN) en JSON y DB SQLite."""
    try:
        # Crear carpetas
        os.makedirs(BASE_DIR, exist_ok=True)
        os.makedirs(os.path.join(BASE_DIR, msn), exist_ok=True)
        os.makedirs(os.path.join(BASE_DIR, msn, 'docs'), exist_ok=True)
        
        # Guardar proyecto en JSON
        projects = {}
        if os.path.exists(PROJECT_CONFIG_FILE):
            with open(PROJECT_CONFIG_FILE, 'r') as f:
                projects = json.load(f)
        
        projects[msn] = {
            'Aircraft_Reg': project_data.get('Aircraft_Reg', 'N/A'),
            'Date_Initiated': project_data.get('Date_Initiated', datetime.now().strftime('%Y-%m-%d')),
            'FH_Initiated': project_data.get('FH_Initiated', ''),
            'FC_Initiated': project_data.get('FC_Initiated', ''),
            'Lease_Agreement_Ref': project_data.get('Lease_Agreement_Ref', '')
        }
        
        with open(PROJECT_CONFIG_FILE, 'w') as f:
            json.dump(projects, f, indent=4)
        
        # Inicializar tabla REPAIRS con TODOS los 55 campos
        with get_db_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS repairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    MSN TEXT NOT NULL,
                    Repair_ID TEXT NOT NULL,
                    UNIQUE(MSN, Repair_ID)
                )
            ''')
            
            # Añadir todas las columnas (55 campos IATA)
            for col in COLUMNS:
                try:
                    conn.execute(f'ALTER TABLE repairs ADD COLUMN "{col}" TEXT')
                except sqlite3.OperationalError:
                    pass  # Columna ya existe
            conn.commit()
        
        return True, f"Proyecto {msn} creado correctamente."
    
    except Exception as e:
        return False, f"Error: {str(e)}"

# --- FUNCIÓN FALTANTE: OBTENER DETALLES DEL PROYECTO ---
def get_project_details(msn):
    """Obtiene detalles del proyecto desde JSON."""
    if os.path.exists(PROJECT_CONFIG_FILE):
        with open(PROJECT_CONFIG_FILE, 'r') as f:
            projects = json.load(f)
            return projects.get(msn, {})
    return {}

def get_all_projects():
    """Obtiene todos los proyectos."""
    if os.path.exists(PROJECT_CONFIG_FILE):
        with open(PROJECT_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

# --- FUNCIÓN DE CONEXIÓN DB (AGREGAR SI NO EXISTE) ---
def get_db_connection():
    """Crea conexión a SQLite."""
    os.makedirs(BASE_DIR, exist_ok=True)
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn