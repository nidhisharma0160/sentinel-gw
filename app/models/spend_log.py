from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime
from app.core.database import Base


class SpendLog(Base):
    __tablename__ = "spend_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trace_id = Column(String, nullable=False, index=True)
    model = Column(String, nullable=True)
    tokens_in = Column(Integer, nullable=True)
    tokens_out = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=False)
    status_code = Column(Integer, nullable=False)
    endpoint = Column(String, nullable=False)
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
