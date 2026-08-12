from fastapi import FastAPI
from app.database import Base, engine
from app.seed import create_admin_user

app = FastAPI()

@app.on_event("startup")
def startup_event():
    create_admin_user()

Base.metadata.create_all(bind=engine)