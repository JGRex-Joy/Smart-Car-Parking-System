import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship

from app.database import Base


class SlotType(str, enum.Enum):
    PAID = "PAID"
    EMPLOYEE = "EMPLOYEE"


class SlotStatus(str, enum.Enum):
    FREE = "FREE"
    PARKED = "PARKED"


class SessionStatus(str, enum.Enum):
    ENTERED = "ENTERED"              
    PARKED = "PARKED"                
    AWAITING_PAYMENT = "AWAITING_PAYMENT"  
    PAID = "PAID"                    
    EMPLOYEE_PASS = "EMPLOYEE_PASS"  


class Tariff(Base):
    __tablename__ = "tariffs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    price_per_minute = Column(Float, nullable=False, default=5.0)
    free_minutes = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True)


class Slot(Base):
    __tablename__ = "slots"

    id = Column(Integer, primary_key=True, index=True)
    slot_number = Column(String, unique=True, nullable=False)
    slot_type = Column(SAEnum(SlotType), nullable=False)
    status = Column(SAEnum(SlotStatus), nullable=False, default=SlotStatus.FREE)

    session = relationship("ParkingSession", back_populates="slot", uselist=False)


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)


class ParkingSession(Base):
    __tablename__ = "parking_sessions"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String, nullable=False, index=True)
    status = Column(SAEnum(SessionStatus), nullable=False, default=SessionStatus.ENTERED)

    entry_time = Column(DateTime, default=datetime.utcnow)
    parked_time = Column(DateTime, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    paid_time = Column(DateTime, nullable=True)

    duration_seconds = Column(Integer, nullable=True)
    amount_due = Column(Float, nullable=True)

    slot_id = Column(Integer, ForeignKey("slots.id"), nullable=True)
    slot = relationship("Slot", back_populates="session")

    tariff_id = Column(Integer, ForeignKey("tariffs.id"), nullable=True)
    tariff = relationship("Tariff")
