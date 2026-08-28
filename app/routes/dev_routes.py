import math
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import SessionLocal
from app.models.meeting_model import Meeting
from app.models.analysis_model import Analysis
from app.models.system_log_model import SystemLog
from app.enums.meeting_status import MeetingStatus
from app.enums.role import Role
from app.services.jwt import require_roles

router = APIRouter(prefix="/dev", tags=["developer"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

dev_only = Depends(require_roles(Role.DEVELOPER, Role.ADMIN))

# Métricas da IA / Sistema
@router.get("/metrics", dependencies=[dev_only])
def get_system_metrics(db: Session = Depends(get_db)):
    total_meetings = db.query(Meeting).count()
    completed = db.query(Meeting).filter(Meeting.status == MeetingStatus.COMPLETED).count()
    failed = db.query(Meeting).filter(Meeting.status == MeetingStatus.FAILED).count()
    processing = db.query(Meeting).filter(Meeting.status == MeetingStatus.PROCESSING).count()

    success_rate = round((completed / total_meetings * 100), 1) if total_meetings > 0 else 0.0
    avg_latency = db.query(func.avg(Analysis.execution_time)).scalar() or 0.0

    return {
        "total_meetings": total_meetings,
        "completed_count": completed,
        "failed_count": failed,
        "processing_count": processing,
        "success_rate": success_rate,
        "avg_latency_seconds": round(float(avg_latency), 2)
    }

# Endpoint de Logs Paginado (20 itens por padrão)
@router.get("/logs", dependencies=[dev_only])
def get_system_logs(page: int = 1, limit: int = 20, level: str = None, db: Session = Depends(get_db)):
    query = db.query(SystemLog)
    
    if level and level != "ALL":
        query = query.filter(SystemLog.level == level)
    
    # Contagem total de logs para a paginação
    total_logs = query.count()
    total_pages = math.ceil(total_logs / limit) if total_logs > 0 else 1
    
    # Busca paginada
    offset = (page - 1) * limit
    logs = query.order_by(SystemLog.created_at.desc()).offset(offset).limit(limit).all()
    
    response_logs = []
    for log in logs:
        meeting_title = None
        client_name = None
        
        if "reunião #" in log.message.lower() or "reunião #" in (log.detail or "").lower():
            try:
                import re
                match = re.search(r'reunião #(\d+)', log.message.lower())
                if match:
                    m_id = int(match.group(1))
                    meeting = db.query(Meeting).filter(Meeting.id == m_id).first()
                    if meeting:
                        meeting_title = meeting.title
                        client_name = meeting.client
            except Exception:
                pass

        response_logs.append({
            "id": log.id,
            "level": log.level,
            "source": log.source,
            "message": log.message,
            "detail": log.detail,
            "created_at": log.created_at.isoformat(),
            "client": client_name,
            "meeting_title": meeting_title
        })

    return {
        "logs": response_logs,
        "total_logs": total_logs,
        "total_pages": total_pages,
        "current_page": page,
        "limit": limit
    }