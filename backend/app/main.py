"""
Запуск:  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routers import simulation, payment, websockets as ws_router

app = FastAPI(
    title="Smart Parking Management System",
    description=(
        "Макет парковки. Все датчики/камеры эмулируются через REST "
    ),
    version="0.1",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(simulation.router)
app.include_router(payment.router)
app.include_router(ws_router.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/", tags=["Служебное"], summary="Проверка, что сервис жив")
def root():
    return {
        "service": "Smart Parking Management System",
        "mode": "software-only (mock sensors via REST)",
        "docs": "/docs",
        "entry_display_ws": "/ws/entry-display",
        "exit_display_ws": "/ws/exit-display",
    }
