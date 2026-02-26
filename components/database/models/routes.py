import uuid
import enum
from sqlalchemy import String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from components.database.models.base import BaseModel

class TaskStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class TaskMode(enum.Enum):
    drive = "drive"
    transit = "transit"
    mixed = "mixed"

class DrivePart(enum.Enum):
    first = "first"
    second = "second"

class RouteTask(BaseModel):
    __tablename__ = "route_tasks"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PENDING)
    start_address_id: Mapped[int] = mapped_column(ForeignKey("addresses.id"))
    transfer_address_id: Mapped[int | None] = mapped_column(ForeignKey("addresses.id"), nullable=True)
    destination_address_id: Mapped[int] = mapped_column(ForeignKey("addresses.id"))
    mode: Mapped[TaskMode] = mapped_column(Enum(TaskMode))
    drive_part: Mapped[DrivePart | None] = mapped_column(Enum(DrivePart), nullable=True)
    arrive_time: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    query_time: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    start_address: Mapped["Address"] = relationship(foreign_keys=[start_address_id])
    transfer_address: Mapped["Address"] = relationship(foreign_keys=[transfer_address_id])
    destination_address: Mapped["Address"] = relationship(foreign_keys=[destination_address_id])
    result: Mapped["RouteResult"] = relationship(back_populates="task", uselist=False)

class RouteResult(BaseModel):
    __tablename__ = "route_results"
    
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("route_tasks.id"),
        unique=True
    )
    result_json: Mapped[str] = mapped_column(Text)
    
    task: Mapped["RouteTask"] = relationship(back_populates="result")
