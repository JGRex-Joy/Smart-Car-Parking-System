from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

SQLALCHEMY_DATABASE_URL = "sqlite:///./smart_parking.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if db.query(models.Slot).count() == 0:
            slots = [
                models.Slot(slot_number="P1", slot_type=models.SlotType.PAID),
                models.Slot(slot_number="P2", slot_type=models.SlotType.PAID),
                models.Slot(slot_number="P3", slot_type=models.SlotType.PAID),
                models.Slot(slot_number="P4", slot_type=models.SlotType.PAID),
                models.Slot(slot_number="E1", slot_type=models.SlotType.EMPLOYEE),
                models.Slot(slot_number="E2", slot_type=models.SlotType.EMPLOYEE),
            ]
            db.add_all(slots)

        if db.query(models.Tariff).count() == 0:
            tariff = models.Tariff(
                name="Стандартный (тест: считаем по минутам)",
                price_per_minute=5.0,   
                free_minutes=1,          # первую 1 минуту бесплатно
                is_active=True,
            )
            db.add(tariff)

        if db.query(models.Employee).count() == 0:
            employees = [
                models.Employee(plate_number="001AAA", full_name="Омуркулов А.Б"),
                models.Employee(plate_number="777BBB", full_name="Кенешбеков У.Н."),
            ]
            db.add_all(employees)

        db.commit()
    finally:
        db.close()
