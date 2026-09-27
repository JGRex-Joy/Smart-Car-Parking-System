import math
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app import models


def get_active_tariff(db: Session) -> Optional[models.Tariff]:
    return db.query(models.Tariff).filter(models.Tariff.is_active == True).first() 


def is_employee_plate(db: Session, plate_number: str) -> bool:
    return db.query(models.Employee).filter(
        models.Employee.plate_number == plate_number.upper()
    ).first() is not None


def count_free_slots(db: Session, slot_type: models.SlotType) -> int:
    return db.query(models.Slot).filter(
        models.Slot.slot_type == slot_type,
        models.Slot.status == models.SlotStatus.FREE,
    ).count()


def get_slot(db: Session, slot_id: int) -> Optional[models.Slot]:
    return db.query(models.Slot).filter(models.Slot.id == slot_id).first()


def get_free_slot_by_type(db: Session, slot_type: models.SlotType) -> Optional[models.Slot]:
    return db.query(models.Slot).filter(
        models.Slot.slot_type == slot_type,
        models.Slot.status == models.SlotStatus.FREE,
    ).first()


def create_entry_session(db: Session, plate_number: str) -> models.ParkingSession:
    session = models.ParkingSession(
        plate_number=plate_number.upper(),
        status=models.SessionStatus.ENTERED,
        entry_time=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_latest_session_awaiting_slot(db: Session, plate_number: Optional[str] = None):
    q = db.query(models.ParkingSession).filter(
        models.ParkingSession.status == models.SessionStatus.ENTERED,
        models.ParkingSession.slot_id.is_(None),
    )
    if plate_number:
        q = q.filter(models.ParkingSession.plate_number == plate_number.upper())
    return q.order_by(models.ParkingSession.entry_time.asc()).first()


def get_active_parked_session_by_plate(db: Session, plate_number: str):
    return db.query(models.ParkingSession).filter(
        models.ParkingSession.plate_number == plate_number.upper(),
        models.ParkingSession.status == models.SessionStatus.PARKED,
    ).order_by(models.ParkingSession.entry_time.desc()).first()


def get_session(db: Session, session_id: int) -> Optional[models.ParkingSession]:
    return db.query(models.ParkingSession).filter(models.ParkingSession.id == session_id).first()


def assign_slot_to_session(db: Session, session: models.ParkingSession, slot: models.Slot):
    slot.status = models.SlotStatus.PARKED
    session.slot_id = slot.id
    session.status = models.SessionStatus.PARKED
    session.parked_time = datetime.utcnow()
    db.add(slot)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def calculate_bill(db: Session, session: models.ParkingSession) -> models.ParkingSession:
    tariff = get_active_tariff(db)
    now = datetime.utcnow()

    duration_seconds = int((now - session.entry_time).total_seconds())
    duration_seconds = max(duration_seconds, 0)

    billable_minutes = max(math.ceil(duration_seconds / 60) - tariff.free_minutes, 0)
    amount = round(billable_minutes * tariff.price_per_minute, 2)

    session.exit_time = now
    session.duration_seconds = duration_seconds
    session.amount_due = amount
    session.tariff_id = tariff.id
    session.status = models.SessionStatus.AWAITING_PAYMENT

    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def mark_session_paid(db: Session, session: models.ParkingSession) -> models.ParkingSession:
    session.status = models.SessionStatus.PAID
    session.paid_time = datetime.utcnow()

    if session.slot_id:
        slot = get_slot(db, session.slot_id)
        if slot:
            slot.status = models.SlotStatus.FREE
            db.add(slot)

    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def build_entry_display_payload(db: Session) -> dict:
    tariff = get_active_tariff(db)
    return {
        "event": "entry_display_update",
        "free_paid_slots": count_free_slots(db, models.SlotType.PAID),
        "free_employee_slots": count_free_slots(db, models.SlotType.EMPLOYEE),
        "total_paid_slots": db.query(models.Slot).filter(
            models.Slot.slot_type == models.SlotType.PAID).count(),
        "total_employee_slots": db.query(models.Slot).filter(
            models.Slot.slot_type == models.SlotType.EMPLOYEE).count(),
        "tariff": {
            "name": tariff.name,
            "price_per_minute": tariff.price_per_minute,
            "free_minutes": tariff.free_minutes,
        } if tariff else None,
    }


def build_exit_display_payload(session: models.ParkingSession, pay_url: str, qr_base64: str) -> dict:
    hours, remainder = divmod(session.duration_seconds or 0, 3600)
    minutes, seconds = divmod(remainder, 60)
    return {
        "event": "exit_bill",
        "session_id": session.id,
        "plate_number": session.plate_number,
        "duration": {"hours": hours, "minutes": minutes, "seconds": seconds},
        "amount_due": session.amount_due,
        "pay_url": pay_url,
        "qr_code_base64": qr_base64,   
        "status": session.status.value,
    }


def build_barrier_open_payload(channel_hint: str, plate_number: str) -> dict:
    return {"event": "barrier_open", "plate_number": plate_number, "gate": channel_hint}


def build_exit_cleared_payload() -> dict:
    return {"event": "exit_clear"}
