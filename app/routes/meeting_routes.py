from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.models import Meeting
from app.database import SessionLocal

router = APIRouter(prefix="/meetings", tags=["meetings"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("")
def get_meetings(page: int = 1, limit: int = 10, db: Session = Depends(get_db)):
    meetings = db.query(Meeting).all()
    return meetings