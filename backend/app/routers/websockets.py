from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from app import crud
from app.config import BASE_URL
from app.database import get_db, SessionLocal
from app.utils import generate_qr_base64
from app.websocket_manager import manager

router = APIRouter(tags=["WebSocket дисплеи"])


@router.websocket("/ws/entry-display")
async def ws_entry_display(websocket: WebSocket):
    await manager.connect("entry", websocket)
    db = SessionLocal()
    try:
        await websocket.send_json(crud.build_entry_display_payload(db))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        db.close()
        manager.disconnect("entry", websocket)


@router.websocket("/ws/exit-display")
async def ws_exit_display(websocket: WebSocket):
    await manager.connect("exit", websocket)
    db = SessionLocal()
    try:
        pending = crud.get_awaiting_payment_session(db)
        if pending:
            pay_url = f"{BASE_URL}/pay/{pending.id}"
            qr_base64 = generate_qr_base64(pay_url)
            await websocket.send_json(crud.build_exit_display_payload(pending, pay_url, qr_base64))
        else:
            await websocket.send_json({"event": "exit_clear"})

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        db.close()
        manager.disconnect("exit", websocket)
