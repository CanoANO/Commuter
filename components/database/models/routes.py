import uuid
import enum
from sqlalchemy import String, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from components.database.models.base import BaseModel

class TaskStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class RouteTask(BaseModel):
    __tablename__ = "route_tasks"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PENDING)
    locations: Mapped[list[int]] = mapped_column(JSON)
    segment_modes: Mapped[list[str]] = mapped_column(JSON)
    arrive_time: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    query_time: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    result: Mapped["RouteResult"] = relationship(back_populates="task", uselist=False, cascade="all, delete-orphan")

class RouteResult(BaseModel):
    __tablename__ = "route_results"
    
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("route_tasks.id"),
        unique=True
    )
    result_json: Mapped[str] = mapped_column(Text)
    
    task: Mapped["RouteTask"] = relationship(back_populates="result")
