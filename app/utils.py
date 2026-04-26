from __future__ import annotations
from datetime import date, timedelta
from pathlib import Path
import os, uuid
from flask import current_app
from .extensions import db
from .models import AuditLog, SLA_OPTIONS


def save_uploaded_files(files, entity_type: str, entity_id: int, user_id: int, Attachment):
    saved = []
    upload_folder = Path(current_app.config['UPLOAD_FOLDER'])
    upload_folder.mkdir(parents=True, exist_ok=True)
    for file in files:
        if not file or not file.filename:
            continue
        ext = Path(file.filename).suffix
        stored_name = f"{uuid.uuid4().hex}{ext}"
        file.save(upload_folder / stored_name)
        record = Attachment(
            entity_type=entity_type,
            entity_id=entity_id,
            original_name=file.filename,
            stored_name=stored_name,
            uploaded_by=user_id,
        )
        db.session.add(record)
        saved.append(record)
    return saved


def log_action(user_id, action, entity_type, entity_id, notes=None):
    try:
        log = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            notes=notes or ''
        )
        db.session.add(log)
        db.session.flush()
    except Exception:
        pass


def compute_due_date(sla_key: str, base_date: date | None = None) -> date:
    base = base_date or date.today()
    mapping = {
        '24h': 1,
        '3bd': 3,
        '5bd': 5,
        '7bd': 7,
        '14bd': 14,
        '30d': 30,
    }
    return base + timedelta(days=mapping.get(sla_key, 7))
