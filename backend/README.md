# Smart Parking Management System — Backend (Software-only)

ШАГ 1 из плана: FastAPI-бэкенд + SQLite, без реального железа.
Все датчики/камеры дёргаются вручную через Swagger UI (`/docs`).

## Установка и запуск

```bash
cd smart_parking
python3 -m venv venv && source venv/bin/activate      # опционально
pip install -r requirements.txt

# локально:
uvicorn app.main:app --reload

# чтобы телефоны в той же Wi-Fi сети видели сервер (замени IP на свой):
PARKING_BASE_URL=http://192.168.1.50:8000 uvicorn app.main:app --host 0.0.0.0 --port 8000
```

При первом запуске автоматически создаётся `smart_parking.db` и наполняется:
- 6 слотов: `P1..P4` (PAID), `E1..E2` (EMPLOYEE)
- тариф: 5 у.е./мин, первые 2 минуты бесплатно
- 2 сотрудника: `A001AA`, `B777BB`

Swagger: **http://localhost:8000/docs**

## Структура проекта

```
app/
  main.py            # точка входа, роутеры, startup
  config.py          # BASE_URL для ссылки в QR
  database.py        # engine, get_db, init_db (сид-данные)
  models.py          # SQLAlchemy: Slot, Employee, Tariff, ParkingSession
  schemas.py         # Pydantic-схемы запросов/ответов
  crud.py            # вся бизнес-логика (расчёт тарифа, статусы, payload'ы)
  utils.py           # генерация QR-кода (base64 PNG)
  websocket_manager.py  # ConnectionManager (каналы entry/exit)
  routers/
    simulation.py    # POST /api/sim/entry, /api/sim/sensor/{id}, /api/sim/exit
    payment.py        # GET /pay/{id}, POST /api/pay/{id}
    websockets.py     # WS /ws/entry-display, /ws/exit-display
  templates/pay.html # мок-страница оплаты
```

## Полный сценарий тестирования через Swagger

1. **Открой два WebSocket-клиента** (например, вкладки на https://websocketking.com/
   или `wscat -c ws://localhost:8000/ws/entry-display`) на `/ws/entry-display` и `/ws/exit-display` —
   это имитация двух телефонов.

2. **Въезд сотрудника** — `POST /api/sim/entry` `{"plate_number": "A001AA"}`
   → ответ `null`, сессия не создаётся, на entry-канал уходит событие `barrier_open`.

3. **Въезд обычной машины** — `POST /api/sim/entry` `{"plate_number": "C777CC"}`
   → создаётся сессия со статусом `ENTERED`.

4. **Сработал датчик слота** — `POST /api/sim/sensor/1` `{"occupied": true, "plate_number": "C777CC"}`
   → слот `P1` становится `PARKED`, сессия переходит в `PARKED`,
   на entry-канал уходит обновлённый счётчик свободных мест.

5. Подожди немного (чтобы накопилось время парковки).

6. **Выездная камера** — `POST /api/sim/exit` `{"plate_number": "C777CC"}`
   → бэкенд считает длительность и сумму, статус `AWAITING_PAYMENT`,
   на exit-канал уходит `exit_bill` с `qr_code_base64` и `pay_url`.

7. **Оплата** — открой `pay_url` из ответа (`http://localhost:8000/pay/1`) в браузере
   и нажми «Оплатить», либо вызови `POST /api/pay/1` напрямую.
   → статус `PAID`, слот освобождён, на exit-канал уходит `barrier_open` + `exit_clear`,
   на entry-канал — обновлённый счётчик свободных мест.

Дополнительно для отладки: `GET /api/sim/slots`, `GET /api/sim/sessions`.

## Дальше (следующие шаги)
- ШАГ 2: мок-экраны React Native (Expo) для `/ws/entry-display` и `/ws/exit-display`.
- ШАГ 3: модуль OpenCV + EasyOCR (пока вызывается через `/api/sim/entry` и `/api/sim/exit`
  вручную; далее подключится к реальному видеопотоку).
