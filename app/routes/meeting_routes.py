from datetime import date
from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session
from app.enums.role import Role
from app.langchain.langchain import NexoEngine
from app.models.analysis_model import Analysis
from app.models.meeting_model import Meeting
from app.database import SessionLocal
from app.services.jwt import require_roles
from app.services.pandas import process_transcription
from app.models.transcription_model import Transcription
from fastapi import BackgroundTasks
from app.enums.meeting_status import MeetingStatus
import time
import traceback
from app.models.system_log_model import SystemLog
import time

router = APIRouter(prefix="/meetings", tags=["meetings"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("", dependencies=[Depends(require_roles(Role.USER, Role.ADMIN, Role.DEVELOPER))])
def get_meetings(page: int = 1, limit: int = 10, db: Session = Depends(get_db)):
    offset = (page - 1) * limit
    meetings = db.query(Meeting).offset(offset).limit(limit).all()
    return meetings

@router.get("/with-analysis", dependencies=[Depends(require_roles(Role.USER, Role.ADMIN, Role.DEVELOPER))])
def get_meetings_with_analysis(page: int = 1, limit: int = 10, db: Session = Depends(get_db)):
    offset = (page - 1) * limit
    meetings = db.query(Meeting).join(Analysis).offset(offset).limit(limit).all()
    analysis = db.query(Analysis).filter(Analysis.meeting_id.in_([meeting.id for meeting in meetings])).all()
    return [{"meeting": meeting, "analysis": next((a for a in analysis if a.meeting_id == meeting.id), None)} for meeting in meetings]

@router.get("/{meeting_id}/with-analysis", dependencies=[Depends(require_roles(Role.USER, Role.ADMIN, Role.DEVELOPER))])
def get_meeting_with_analysis(meeting_id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    analysis = db.query(Analysis).filter(Analysis.meeting_id == meeting_id).first()
    transcript = db.query(Transcription).filter(Transcription.meeting_id == meeting_id).first()
    return {"meeting": meeting, "analysis": analysis, "transcript": transcript.transcript}

@router.get("/{meeting_id}/status", dependencies=[Depends(require_roles(Role.USER, Role.ADMIN, Role.DEVELOPER))])
def get_meeting_status(meeting_id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return {"id": meeting.id, "status": meeting.status}

@router.post("", dependencies=[Depends(require_roles(Role.USER, Role.ADMIN, Role.DEVELOPER))])
def create_meeting(
    background_tasks: BackgroundTasks,
    client: str = Form(...),
    title: str = Form(...),
    date: date = Form(...),
    transcription: str = Form(...),
    db: Session = Depends(get_db)
):
    new_meeting = Meeting(client=client, title=title, date=date)
    db.add(new_meeting)
    db.commit()
    db.refresh(new_meeting)

    background_tasks.add_task(process_meeting, new_meeting.id, transcription, db)

    return {"id": new_meeting.id, "status": new_meeting.status}

def process_meeting(meeting_id: int, transcription: str, db: Session):
    start_time = time.time()
    try:
        # Processa com pandas
        transcription_processed = process_transcription(transcription)

        # Processa com a IA
        engine = NexoEngine()
        analysis_result = engine.analyze_transcription(transcription_processed).model_dump()

        if not analysis_result or analysis_result.get("isAnalyzable") == False:
            reason = analysis_result.get("reasonForFailure", "Failed to analyze transcription") if analysis_result else "Empty result"
            
            meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
            meeting.status = MeetingStatus.FAILED
            meeting.errorMessage = reason
            
            # Registra log do sistema
            log_entry = SystemLog(
                level="WARNING",
                source="NexoEngine",
                message=f"Falha na análise da reunião #{meeting_id}: {reason}"
            )
            db.add(log_entry)
            db.commit()
            return

        execution_time = round(time.time() - start_time, 2)
        talk_to_listen_ratio = calculate_talk_to_listen_ratio(
            transcription_processed, 
            analysis_result["totvsSpeakers"], 
            analysis_result["clientSpeakers"]
        )

        # Salva transcrição
        new_transcription = Transcription(
            meeting_id=meeting_id, 
            raw_text=transcription_processed, 
            transcript=analysis_result["transcript"]
        )
        db.add(new_transcription)

        # Salva análise
        new_analysis = Analysis(
            meeting_id=meeting_id,
            health_score=analysis_result["healthScore"],
            sentiment=analysis_result["sentiment"],
            upsell_oportunities=analysis_result["upsellOpportunities"],
            churnk_risk=analysis_result["churnRisk"],
            talk_to_listen_ratio=talk_to_listen_ratio,
            pain_points=analysis_result["insights"]["painPoints"],
            risk_factors=analysis_result["insights"]["riskPoints"],
            highlights=analysis_result["insights"]["positiveHighlights"],
            suggestions=analysis_result["insights"]["aiSuggestions"],
            sentiment_timeline=analysis_result["sentimentData"],
            execution_time=execution_time
        )
        db.add(new_analysis)

        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        meeting.participants = analysis_result["participants"]
        meeting.status = MeetingStatus.COMPLETED
        
        # Log de sucesso com tempo de execução
        db.add(SystemLog(
            level="INFO",
            source="NexoEngine",
            message=f"Reunião #{meeting_id} processada com sucesso em {execution_time}s"
        ))

        db.commit()

    except Exception as e:
        db.rollback()
        error_msg = str(e)
        stack_trace = traceback.format_exc()

        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if meeting:
            meeting.status = MeetingStatus.FAILED
            meeting.errorMessage = error_msg

        # Registra o erro detalhado no banco de dados
        db.add(SystemLog(
            level="ERROR",
            source="NexoEngine",
            message=f"Erro crítico no processamento da reunião #{meeting_id}",
            detail=stack_trace
        ))
        db.commit()
    finally:
        db.close()


def calculate_talk_to_listen_ratio(transcript: str, totvs_speakers: list, client_speakers: list):
    totvs_words, client_words = 0, 0

    for line in transcript.split("\\n"):
        if any(line.startswith(f"[{speaker}]") for speaker in totvs_speakers):
            totvs_words += len(line.split())
        elif any(line.startswith(f"[{speaker}]") for speaker in client_speakers):
            client_words += len(line.split())

    total_words = totvs_words + client_words

    if total_words == 0:
        return 50.0

    return totvs_words * 100 / total_words