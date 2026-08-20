from pydantic import BaseModel
from datetime import date

class MeetingCreate(BaseModel):
    client: str
    title: str
    date: date
    transcription: str

class MeetingResponse(BaseModel):
    id: int
    client: str
    title: str
    participants: dict
    status: str
    created_at: str
    updated_at: str