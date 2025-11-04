# data_manager.py
import os
import json
from datetime import datetime, timedelta

BASE_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(BASE_DIR, exist_ok=True)

COLUMNS = [
    'Repair_ID', 'ATA_Chapter', 'Location', 'Damage_Type', 'Dim_Length_Width', 'Dim_Depth',
    'Dim_Remaining_Thk', 'Material', 'SRM_Ref', 'SRM_Chapter', 'SRM_Page', 'Repair_Description',
    'Doubler_Material', 'Doubler_Thickness', 'Fastener_Type', 'Fastener_Spacing', 'Sealant_Type',
    'Corrosion_Prevention', 'NDT_Required_Performed', 'Date_Initiated', 'Date_Completed',
    'Operator_Name', 'Inspector_Name', 'Doc_Drawing', 'Doc_Photo_Pre', 'Doc_Photo_Post',
    'Doc_NDT_Report', 'Audit_OIL_Status', 'Audit_Physical_Status', 'Audit_Date',
    'OIL_ID', 'OIL_Type', 'OIL_Category', 'OIL_Reference', 'OIL_Priority', 'OIL_Due_Date',
    'OIL_Audit_Note', 'Doc_Audit_File', 'Operator_Response_Note', 'Doc_Operator_File',
    'Response_Date', 'OIL_Status', 'OIL_Closure_Note', 'OIL_Compensation_Note',
    'OIL_Signed_By', 'OIL_Signed_Date', 'OIL_Closure_Date'
]

def get_project_path(msn):
    return os.path.join(BASE_DIR, f"{msn}.json")

def get_all_projects():
    projects = []
    for f in os.listdir(BASE_DIR):
        if f.endswith('.json'):
            path = os.path.join(BASE_DIR, f)
            with open(path, 'r') as file:
                data = json.load(file)
                projects.append({
                    'msn': data['msn'],
                    'Aircraft_Type': data.get('Aircraft_Type', 'N/A'),
                    'Registration': data.get('Registration', 'N/A')
                })
    return projects

def get_project_details(msn):
    path = get_project_path(msn)
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f)

def create_new_project(msn, project_data):
    path = get_project_path(msn)
    if os.path.exists(path):
        return False, "Project already exists."
    data = {
        'msn': msn,
        'repairs': [],
        **project_data
    }
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    return True, "Project created."

def get_all_repairs(msn):
    details = get_project_details(msn)
    return details['repairs'] if details else []

def get_repair_record_by_id(msn, repair_id):
    repairs = get_all_repairs(msn)
    for r in repairs:
        if r['Repair_ID'] == repair_id:
            return r
    return None

def add_repair_record(msn, data):
    path = get_project_path(msn)
    if not os.path.exists(path):
        return False, "Project not found."
    with open(path, 'r') as f:
        project = json.load(f)
    project['repairs'].append(data)
    with open(path, 'w') as f:
        json.dump(project, f, indent=2)
    return True, "Repair added."

def update_repair_record(msn, repair_id, update_data):
    path = get_project_path(msn)
    if not os.path.exists(path):
        return False, "Project not found."
    with open(path, 'r') as f:
        project = json.load(f)
    for r in project['repairs']:
        if r['Repair_ID'] == repair_id:
            r.update(update_data)
            break
    else:
        return False, "Repair not found."
    with open(path, 'w') as f:
        json.dump(project, f, indent=2)
    return True, "Repair updated."

# --- FUNCIÓN OIL (NUEVA) ---
def create_oil_item(msn, repair_id, oil_type):
    repair = get_repair_record_by_id(msn, repair_id)
    if not repair or repair.get('OIL_ID'):
        return

    oil_id = f"OIL-{repair_id.split('-')[0]}-{datetime.now().strftime('%y%m%d')}"
    due_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    
    update = {
        'OIL_ID': oil_id,
        'OIL_Type': oil_type,
        'OIL_Category': 'Structural',
        'OIL_Reference': repair.get('SRM_Ref', 'N/A'),
        'OIL_Priority': 'High',
        'OIL_Due_Date': due_date,
        'OIL_Status': 'Open'
    }
    update_repair_record(msn, repair_id, update)
