# --- audit_log.py (COMPLETO Y FUNCIONAL) ---
import json
import os
from datetime import datetime
import tempfile

BASE_DIR = tempfile.gettempdir()
AUDIT_FILE = os.path.join(BASE_DIR, 'audit_trail.json')

def log_event(msn, record_id, action, user_context, data_changed=None):
    """Guarda evento de auditoría en JSON."""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'msn': msn,
        'record_id': record_id,
        'action': action,
        'user_role': user_context.get('role', 'UNKNOWN'),
        'user_name': user_context.get('name', 'N/A'),
        'user_ip': user_context.get('ip', 'N/A'),
        'data_changed': data_changed or {}
    }
    
    # Cargar logs existentes
    logs = []
    if os.path.exists(AUDIT_FILE):
        try:
            with open(AUDIT_FILE, 'r') as f:
                logs = json.load(f)
        except:
            logs = []
    
    logs.append(log_entry)
    
    # Guardar
    try:
        with open(AUDIT_FILE, 'w') as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        print(f"Audit log error: {e}")

def get_audit_trail(msn=None, repair_id=None):
    """Devuelve logs filtrados."""
    if not os.path.exists(AUDIT_FILE):
        return []
    try:
        with open(AUDIT_FILE, 'r') as f:
            logs = json.load(f)
    except:
        return []
    
    filtered = logs
    if msn:
        filtered = [l for l in filtered if l['msn'] == msn]
    if repair_id:
        filtered = [l for l in filtered if l['record_id'] == repair_id]
    
    return filtered
