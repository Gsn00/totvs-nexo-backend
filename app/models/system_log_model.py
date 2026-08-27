from app.database import Base
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone

class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    level: Mapped[str] = mapped_column(String(20), default="INFO")  # INFO, WARNING, ERROR
    source: Mapped[str] = mapped_column(String(50))                # e.g., 'NexoEngine', 'API', 'Auth'
    message: Mapped[str] = mapped_column(Text)
    detail: Mapped[str] = mapped_column(Text, nullable=True)       # Stacktrace ou contexto extra
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )