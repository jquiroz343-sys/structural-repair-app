# audit_log.py
import json
import os
from datetime import datetime

def log_action(action, description):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "description": description
    }
    # Ruta del log en Render (usa la misma carpeta temporal)
    base_dir = os.path.dirname(__file__)
    log_path = os.path.join(base_dir, '..', 'audit.json')  # Sube un nivel desde el archivo
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    
    try:
        with open(log_path, 'r+') as f:
            logs = json.load(f)
            logs.append(log_entry)
            f.seek(0)
            json.dump(logs, f, indent=2)
    except (FileNotFoundError, json.JSONDecodeError):
        with open(log_path, 'w') as f:
            json.dump([log_entry], f, indent=2)