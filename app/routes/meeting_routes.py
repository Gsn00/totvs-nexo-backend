from fastapi import APIRouter, Depends, Form
from sqlalchemy.orm import Session
from app.langchain.langchain import NexoEngine
from app.models.meeting_model import Meeting
from app.database import SessionLocal
from app.services.pandas import process_transcription
from app.models.transcription_model import Transcription

router = APIRouter(prefix="/meetings", tags=["meetings"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("")
def get_meetings(page: int = 1, limit: int = 10, db: Session = Depends(get_db)):
    offset = (page - 1) * limit
    meetings = db.query(Meeting).offset(offset).limit(limit).all()
    return meetings

@router.post("")
def create_meeting(
    client: str = Form(...),
    title: str = Form(...),
    transcription: str = Form(...),
    db: Session = Depends(get_db)
):
    new_meeting = Meeting(client=client, title=title, duration=0, participants={})
    db.add(new_meeting)
    db.commit()
    db.refresh(new_meeting)

    transcription = process_transcription(transcription)

    ##Analisar transcricao

    langchain = NexoEngine();
    analysis_result = langchain.analyze_transcription(transcription)
    print("-"*50)
    print("Analysis Result:", analysis_result)
    print("-"*50)

    new_transcription = Transcription(meeting_id=new_meeting.id, raw_text=transcription, transcription={})
    db.add(new_transcription)
    db.commit()
    db.refresh(new_transcription)

    return analysis_result