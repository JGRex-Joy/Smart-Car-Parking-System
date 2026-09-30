from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routers import simulation, payment, websockets as ws_router

app = FastAPI(
    title="Smart Parking Management System",
    description=(
        "Макет умной парковки. Все датчики/камеры эмулируются"
    ),
    version="0.2",
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
