from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db, SessionLocal
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
    try:
        await websocket.send_json({"event": "exit_clear"})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect("exit", websocket)
