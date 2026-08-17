from pydantic import BaseModel

class MeetingCreate(BaseModel):
    client: str
    title: str
    transcription: str

class MeetingResponse(BaseModel):
    id: int
    client: str
    title: str
    duration: int
    participants: dict
    status: str
    created_at: str
    updated_at: str