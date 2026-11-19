from datetime import datetime
from random import randint

from app.models import db, AuditLog, StockRequirement


class ProcurementService:
    @staticmethod
    def next_number(prefix, model, field):
        for _ in range(50):
            number = f"{prefix}-{datetime.utcnow().strftime('%Y%m%d')}-{randint(1000, 9999)}"
            if not model.query.filter(getattr(model, field) == number).first():
                return number
        raise RuntimeError("Unable to generate a unique procurement number")

    @staticmethod
    def log(user_id, action, module, details):
        db.session.add(AuditLog(
            user_id=user_id,
            action=action,
            module=module,
            details=details
        ))
