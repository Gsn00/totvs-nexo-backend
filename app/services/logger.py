from sqlalchemy.orm import Session
from app.models.system_log_model import SystemLog

def log_system_event(
    db: Session,
    level: str,
    source: str,
    message: str,
    detail: str = None
):
    """
    Registra um evento estruturado na tabela system_logs.
    Níveis comuns: 'INFO', 'WARNING', 'ERROR'
    """
    try:
        log_entry = SystemLog(
            level=level,
            source=source,
            message=message,
            detail=detail
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Falha ao gravar log no sistema: {e}")