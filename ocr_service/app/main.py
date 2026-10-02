from typing import List, Literal, Optional

import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from pydantic import BaseModel

from app.backend_client import forward_plate_to_backend
from app.config import MAX_CORRECTIONS_TO_TRUST
from app.mock_camera import capture_frame_bytes
from app.ocr_engine import run_ocr
from app.plate_utils import extract_plate, PlateCandidate

app = FastAPI(
    title="Smart Parking - OCR Service",
    description="Распознавание автомобильных номеров",
    version="0.2.1",
)


class DetectionOut(BaseModel):
    text: str
    confidence: float


class RecognizeResponse(BaseModel):
    plate_number: Optional[str]      
    formatted: Optional[str]         
    region_code: Optional[str]
    is_valid_region: bool
    corrections_applied: int         
    confidence: float                
    plate_detection_method: str      
    plate_detection_score: float
    raw_detections: List[DetectionOut]


def _best_candidate(detections) -> tuple[Optional[PlateCandidate], float]:
    attempts = []  

    if detections:
        joined = "".join(d.text for d in detections)
        joined_conf = sum(d.confidence for d in detections) / len(detections)
        cand = extract_plate(joined)
        if cand:
            attempts.append((cand, joined_conf))

    for d in detections:
        cand = extract_plate(d.text)
        if cand:
            attempts.append((cand, d.confidence))

    if not attempts:
        return None, 0.0

    def rank(item):
        cand, _ = item
        return (0 if cand.is_valid_region else 1, cand.corrections, -len(cand.letters))

    best_cand, best_conf = min(attempts, key=rank)
    return best_cand, best_conf


async def _read_image(file: UploadFile) -> bytes:
    if file.content_type not in ("image/jpeg", "image/png", "image/jpg"):
        raise HTTPException(status_code=400, detail="Ожидается изображение JPEG или PNG")
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Пустой файл")
    return image_bytes


async def _recognize_response(image_bytes: bytes) -> "RecognizeResponse":
    try:
        detections, plate_crop = run_ocr(image_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    candidate, confidence = _best_candidate(detections)

    return RecognizeResponse(
        plate_number=candidate.plate_number if candidate else None,
        formatted=candidate.formatted if candidate else None,
        region_code=candidate.region if candidate else None,
        is_valid_region=candidate.is_valid_region if candidate else False,
        corrections_applied=candidate.corrections if candidate else 0,
        confidence=round(confidence, 3),
        plate_detection_method=plate_crop.method,
        plate_detection_score=round(plate_crop.score, 3),
        raw_detections=[DetectionOut(text=d.text, confidence=d.confidence) for d in detections],
    )


@app.post("/recognize", response_model=RecognizeResponse, summary="Распознать номер на фото (без форварда в backend)")
async def recognize(file: UploadFile = File(..., description="JPEG/PNG кадр с камеры")):
    image_bytes = await _read_image(file)
    return await _recognize_response(image_bytes)


class GateEventResponse(BaseModel):
    recognized: RecognizeResponse
    forwarded_to_backend: bool
    backend_response: Optional[dict] = None
    reject_reason: Optional[str] = None
    frame_source: str   


async def _process_gate_event(gate: str, image_bytes: bytes, frame_source: str) -> GateEventResponse:
    recognized = await _recognize_response(image_bytes)

    if not recognized.plate_number:
        return GateEventResponse(recognized=recognized, forwarded_to_backend=False,
                                  reject_reason="Номер не распознан", frame_source=frame_source)
    if not recognized.is_valid_region:
        return GateEventResponse(recognized=recognized, forwarded_to_backend=False,
                                  reject_reason=f"Код региона '{recognized.region_code}' вне диапазона 01-11",
                                  frame_source=frame_source)
    if recognized.corrections_applied > MAX_CORRECTIONS_TO_TRUST:
        return GateEventResponse(recognized=recognized, forwarded_to_backend=False,
                                  reject_reason=f"Слишком много исправленных символов "
                                                f"({recognized.corrections_applied}) - результату не доверяем",
                                  frame_source=frame_source)

    try:
        backend_response = await forward_plate_to_backend(gate, recognized.formatted)
    except httpx.HTTPStatusError as e:
        # Бизнес-ошибка backend'а (нет мест, нет припаркованной сессии и т.п.) -
        # не роняем сервис, а прозрачно отдаём причину наружу
        return GateEventResponse(
            recognized=recognized, forwarded_to_backend=False,
            reject_reason=f"Backend отклонил: {e.response.status_code} {e.response.text}",
            frame_source=frame_source,
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Backend недоступен: {e}")

    return GateEventResponse(recognized=recognized, forwarded_to_backend=True,
                              backend_response=backend_response, frame_source=frame_source)


@app.post("/gate-event/signal", response_model=GateEventResponse,
          summary="ЧИСТЫЙ сигнал с датчика (Arduino) — без файла, камера снимает сама")
async def gate_event_signal(gate: Literal["entry", "exit"] = Query(..., description="Какой шлагбаум сработал")):
    try:
        image_bytes, source = capture_frame_bytes(gate)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Камера недоступна: {e}")
    return await _process_gate_event(gate, image_bytes, frame_source=source)


@app.post("/gate-event/with-photo", response_model=GateEventResponse,
          summary="То же самое, но кадр уже снят и прислан файлом")
async def gate_event_with_photo(
    gate: Literal["entry", "exit"] = Query(..., description="Какой шлагбаум сработал"),
    file: UploadFile = File(..., description="JPEG/PNG кадр, уже снятый внешней камерой-системой"),
):
    image_bytes = await _read_image(file)
    return await _process_gate_event(gate, image_bytes, frame_source="uploaded")


class CameraSnapshotResponse(BaseModel):
    source: str              
    image_base64: str       


@app.get("/debug/camera-snapshot", response_model=CameraSnapshotResponse,
          summary="DEBUG: посмотреть, что именно видит камера (без распознавания, без сохранения на диск)")
async def camera_snapshot(gate: Literal["entry", "exit"] = Query(...)):
    import base64
    try:
        image_bytes, source = capture_frame_bytes(gate)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Камера недоступна: {e}")

    b64 = base64.b64encode(image_bytes).decode("ascii")
    return CameraSnapshotResponse(source=source, image_base64=f"data:image/jpeg;base64,{b64}")


@app.get("/health", summary="Проверка, что сервис жив")
def health():
    return {"status": "ok", "service": "ocr-service"}
