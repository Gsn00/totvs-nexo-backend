from app.database import Base
from sqlalchemy import JSON, Float, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.enums.sentiment import Sentiment


class Analysis(Base):
    __tablename__ = "analysis"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    health_score: Mapped[float] = mapped_column()
    sentiment: Mapped[Sentiment] = mapped_column()
    upsell_oportunities: Mapped[dict] = mapped_column(JSON)
    churnk_risk: Mapped[int] = mapped_column()
    talk_to_listen_ratio: Mapped[float] = mapped_column()
    pain_points: Mapped[dict] = mapped_column(JSON)
    risk_factors: Mapped[dict] = mapped_column(JSON)
    highlights: Mapped[dict] = mapped_column(JSON)
    suggestions: Mapped[dict] = mapped_column(JSON)
    sentiment_timeline: Mapped[dict] = mapped_column(JSON)
    execution_time: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())