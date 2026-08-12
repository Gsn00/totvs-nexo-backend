from fastapi import FastAPI
from app.database import Base, engine

app = FastAPI()

Base.metadata.create_all(bind=engine)