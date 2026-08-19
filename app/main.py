from fastapi import FastAPI
from app.database import Base, engine
from app.seed import create_admin_user
from app.models.meeting_model import Meeting
from app.models.transcription_model import Transcription
from app.models.analysis_model import Analysis
from app.routes import meeting_routes, auth_routes
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meeting_routes.router)
app.include_router(auth_routes.router)

@app.on_event("startup")
def startup_event():
    create_admin_user()

Base.metadata.create_all(bind=engine)