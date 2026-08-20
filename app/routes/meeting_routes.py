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
    try:
        # Process the transcription with the pandas service
        transcription = process_transcription(transcription)

        # Process the transcription with the NexoEngine
        engine = NexoEngine()
        analysis_result = engine.analyze_transcription(transcription).model_dump()

        if not analysis_result:
            meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
            meeting.status = MeetingStatus.FAILED
            db.commit()
            return
        
        if analysis_result["isAnalyzable"] == False:
            meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
            meeting.status = MeetingStatus.FAILED
            db.commit()
            return

        talk_to_listen_ratio = calculate_talk_to_listen_ratio(transcription, analysis_result["totvsSpeakers"], analysis_result["clientSpeakers"])

        new_transcription = Transcription(meeting_id=meeting_id, raw_text=transcription, transcript=analysis_result["transcript"])
        db.add(new_transcription)
        db.commit()
        db.refresh(new_transcription)

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
            sentiment_timeline=analysis_result["sentimentData"]
        )
        db.add(new_analysis)
        db.commit()
        db.refresh(new_analysis)

        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        meeting.participants = analysis_result["participants"]
        meeting.status = MeetingStatus.COMPLETED
        db.commit()
        db.refresh(meeting)
    except Exception:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        meeting.status = MeetingStatus.FAILED
        db.commit()


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