from app.database import Base
from sqlalchemy import DateTime, JSON, Date
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone, date
from app.enums.meeting_status import MeetingStatus

class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    client: Mapped[str] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    participants: Mapped[dict] = mapped_column(JSON, default=[])
    status: Mapped[MeetingStatus] = mapped_column(nullable=False, default=MeetingStatus.PROCESSING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))