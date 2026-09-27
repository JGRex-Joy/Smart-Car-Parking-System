from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db
from app.websocket_manager import manager
from app.utils import generate_qr_base64
from app.config import BASE_URL

router = APIRouter(prefix="/api/sim", tags=["Симуляция датчиков и камер"])


@router.post("/entry", response_model=Optional[schemas.SessionOut],
             summary="Въездная камера считала номер / сотрудник поднёс пропуск")
async def sim_entry(payload: schemas.SimEntryRequest, db: Session = Depends(get_db)):
    plate = payload.plate_number.upper()

    if crud.is_employee_plate(db, plate):
        await manager.broadcast("entry", crud.build_barrier_open_payload("entry", plate))
        return None

    if crud.count_free_slots(db, models.SlotType.PAID) == 0:
        raise HTTPException(status_code=409, detail="Нет свободных платных мест")

    session = crud.create_entry_session(db, plate)
    await manager.broadcast("entry", crud.build_barrier_open_payload("entry", plate))
    return session


@router.post("/sensor/{slot_id}", summary="Датчик слота сработал (машина встала/уехала с конкретного места)")
async def sim_sensor(slot_id: int, payload: schemas.SimSensorRequest, db: Session = Depends(get_db)):
    slot = crud.get_slot(db, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Слот не найден")

    if not payload.occupied:
        slot.status = models.SlotStatus.FREE
        db.add(slot)
        db.commit()
        await manager.broadcast("entry", crud.build_entry_display_payload(db))
        return {"detail": "Слот освобождён вручную", "slot": schemas.SlotOut.model_validate(slot)}

    if slot.status == models.SlotStatus.PARKED:
        raise HTTPException(status_code=409, detail="Слот уже занят")

    session = crud.get_latest_session_awaiting_slot(db, payload.plate_number)
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Нет сессии со статусом ENTERED без назначенного слота "
                   "(сначала вызовите /api/sim/entry)",
        )

    session = crud.assign_slot_to_session(db, session, slot)

    await manager.broadcast("entry", crud.build_entry_display_payload(db))
    return schemas.SessionOut.model_validate(session)


@router.post("/exit", response_model=schemas.SessionOut,
             summary="Выездная камера считала номер (выставляем счёт и QR)")
async def sim_exit(payload: schemas.SimExitRequest, db: Session = Depends(get_db)):
    plate = payload.plate_number.upper()

    session = crud.get_active_parked_session_by_plate(db, plate)
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Нет припаркованной (PARKED) сессии с таким номером",
        )

    session = crud.calculate_bill(db, session)

    pay_url = f"{BASE_URL}/pay/{session.id}"
    qr_base64 = generate_qr_base64(pay_url)

    await manager.broadcast("exit", crud.build_exit_display_payload(session, pay_url, qr_base64))
    return session


@router.get("/slots", response_model=list[schemas.SlotOut], summary="Текущее состояние всех слотов (debug)")
def list_slots(db: Session = Depends(get_db)):
    return db.query(models.Slot).all()


@router.get("/sessions", response_model=list[schemas.SessionOut], summary="Все сессии парковки (debug)")
def list_sessions(db: Session = Depends(get_db)):
    return db.query(models.ParkingSession).order_by(models.ParkingSession.id.desc()).all()
