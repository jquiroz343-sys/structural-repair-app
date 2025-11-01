# --- audit_log.py (CÓDIGO COMPLETO) ---

import os
import json
from datetime import datetime

# Definición del archivo de historial centralizado
AUDIT_LOG_FILE = 'data/audit_log.json'

def initialize_audit_log():
    """Asegura que el archivo de log existe."""
    if not os.path.exists('data'):
        os.makedirs('data')
        
    if not os.path.exists(AUDIT_LOG_FILE):
        with open(AUDIT_LOG_FILE, 'w') as f:
            json.dump([], f)

def log_event(msn, repair_id, operation, user_info, data_changed=None):
    """
    Registra un evento de auditoría en el archivo centralizado.
    user_info debe ser un dict que contenga 'role', 'ip', y 'name'.
    """
    initialize_audit_log()
    
    new_event = {
        "timestamp": datetime.now().isoformat(),
        "msn": msn,
        "repair_id": repair_id,
        "operation": operation,
        "user_role": user_info.get('role', 'UNKNOWN'),
        "user_ip": user_info.get('ip', 'N/A'),
        "user_name": user_info.get('name', 'N/A'), # IMPLEMENTADO: Nombre del Funcionario
        "changes": data_changed if data_changed else {}
    }

    try:
        with open(AUDIT_LOG_FILE, 'r+') as f:
            logs = json.load(f)
            logs.append(new_event)
            f.seek(0)
            json.dump(logs, f, indent=4)
            f.truncate()
        return True
    except Exception as e:
        print(f"ERROR logging event: {e}") 
        return False

def get_audit_trail(msn, repair_id=None):
    """Retorna todos los logs o filtra por MSN y Repair ID."""
    initialize_audit_log()
    try:
        with open(AUDIT_LOG_FILE, 'r') as f:
            logs = json.load(f)
            
            filtered_logs = [log for log in logs if log['msn'] == msn]

            if repair_id:
                filtered_logs = [log for log in filtered_logs if log['repair_id'] == repair_id]
                
            return filtered_logs
    except Exception:
        return []

initialize_audit_log()