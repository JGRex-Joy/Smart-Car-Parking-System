from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db
from app.websocket_manager import manager

router = APIRouter(tags=["Оплата"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/pay/{session_id}", response_class=HTMLResponse, summary="Страница оплаты (открывается по QR)")
def pay_page(request: Request, session_id: int, db: Session = Depends(get_db)):
    session = crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    hours, remainder = divmod(session.duration_seconds or 0, 3600)
    minutes, seconds = divmod(remainder, 60)

    return templates.TemplateResponse(
        "pay.html",
        {
            "request": request,
            "session": session,
            "hours": hours,
            "minutes": minutes,
            "seconds": seconds,
            "already_paid": session.status == models.SessionStatus.PAID,
        },
    )


@router.post("/api/pay/{session_id}", response_model=schemas.PaymentResult, summary="Подтвердить оплату")
async def confirm_payment(session_id: int, db: Session = Depends(get_db)):
    session = crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    if session.status == models.SessionStatus.PAID:
        raise HTTPException(status_code=409, detail="Сессия уже оплачена")

    if session.status != models.SessionStatus.AWAITING_PAYMENT:
        raise HTTPException(
            status_code=409,
            detail="Оплата недоступна: счёт ещё не выставлен выездной камерой",
        )

    session = crud.mark_session_paid(db, session)

    await manager.broadcast("exit", crud.build_barrier_open_payload("exit", session.plate_number))
    await manager.broadcast("exit", crud.build_exit_cleared_payload())
    await manager.broadcast("entry", crud.build_entry_display_payload(db))

    return schemas.PaymentResult(
        session_id=session.id,
        status=session.status,
        amount_paid=session.amount_due or 0.0,
    )
