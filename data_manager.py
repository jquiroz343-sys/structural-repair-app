# data_manager.py
import sqlite3
import json
import os
from datetime import datetime
import uuid

class DataManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS repairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')

    def add_repair(self, data):
        data['created_at'] = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('INSERT INTO repairs (data, created_at, updated_at) VALUES (?, ?, ?)',
                                (json.dumps(data), data['created_at'], data['created_at']))
            return cursor.lastrowid

    def update_repair(self, repair_id, data):
        data['updated_at'] = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('UPDATE repairs SET data = ?, updated_at = ? WHERE id = ?',
                        (json.dumps(data), data['updated_at'], repair_id))

    def get_repair(self, repair_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT data FROM repairs WHERE id = ?', (repair_id,))
            row = cursor.fetchone()
            return json.loads(row[0]) if row else None

    def get_all_repairs(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT id, data FROM repairs ORDER BY id DESC')
            return [{'id': r[0], **json.loads(r[1])} for r in cursor.fetchall()]

    def save_photos(self, files, existing=None):
        upload_dir = os.path.join(os.path.dirname(self.db_path), 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        paths = existing or []
        for file in files:
            if file and file.filename:
                ext = os.path.splitext(file.filename)[1]
                filename = f"{uuid.uuid4().hex}{ext}"
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)
                paths.append(filepath)
        return paths

    def get_audit_logs(self):
        log_path = os.path.join(os.path.dirname(self.db_path), 'audit.json')
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                return json.load(f)
        return []