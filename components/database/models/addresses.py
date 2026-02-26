from sqlalchemy import String, Float
from sqlalchemy.orm import Mapped, mapped_column
from components.database.models.base import BaseModel

class Address(BaseModel):
    __tablename__ = "addresses"
    
    raw_text: Mapped[str] = mapped_column(String)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
