from fastapi import APIRouter, Depends, Form
from sqlalchemy.orm import Session
from app.enums.role import Role
from app.langchain.langchain import NexoEngine
from app.models.analysis_model import Analysis
from app.models.meeting_model import Meeting
from app.database import SessionLocal
from app.services.jwt import decode_jwt_token, require_roles
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

@router.post("", dependencies=[Depends(decode_jwt_token), Depends(require_roles(Role.USER, Role.ADMIN, Role.DEVELOPER))])
def create_meeting(
    client: str = Form(...),
    title: str = Form(...),
    transcription: str = Form(...),
    db: Session = Depends(get_db)
):
    ##Processamento do texto bruto com Pandas
    transcription = process_transcription(transcription)

    ##Enviando o texto processado para o LangChain para análise
    #langchain = NexoEngine();
    #analysis_result = langchain.analyze_transcription(transcription).model_dump()

    ##Carregando o resultado da análise do arquivo JSON para simular a resposta do LangChain
    import json
    from pathlib import Path
    analysis_result = {}
    with open(Path.home() / "Desktop" / "result.json", "r", encoding="utf-8") as file:
        analysis_result = json.load(file)

    ###Criando a reunião, transcrição e análise no banco de dados
    new_meeting = Meeting(client=client, title=title, participants=analysis_result["participants"])
    db.add(new_meeting)
    db.commit()
    db.refresh(new_meeting)

    new_transcription = Transcription(meeting_id=new_meeting.id, raw_text=transcription, transcript=analysis_result["transcript"])
    db.add(new_transcription)
    db.commit()
    db.refresh(new_transcription)

    talk_to_listen_ratio = calculate_talk_to_listen_ratio(transcription, analysis_result["totvsSpeakers"], analysis_result["clientSpeakers"])

    new_analysis = Analysis(
        meeting_id=new_meeting.id,
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

    return analysis_result

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