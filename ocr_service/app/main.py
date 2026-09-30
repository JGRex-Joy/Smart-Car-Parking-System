from typing import List, Literal, Optional

import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from pydantic import BaseModel

from app.backend_client import forward_plate_to_backend
from app.config import MAX_CORRECTIONS_TO_TRUST
from app.ocr_engine import run_ocr
from app.plate_utils import extract_plate, PlateCandidate

app = FastAPI(
    title="Smart Parking - OCR Service",
    description="Распознавание кыргызских автомобильных номеров",
    version="0.2",
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
    attempts = []  # (PlateCandidate, confidence)

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


@app.post("/gate-event", response_model=GateEventResponse,
          summary="Событие с датчика (Arduino) + снимок камеры: распознать и сразу отправить в backend")
async def gate_event(
    gate: Literal["entry", "exit"] = Query(..., description="Какой шлагбаум сработал"),
    file: UploadFile = File(..., description="JPEG/PNG снимок с камеры этого шлагбаума"),
):
    """
    Имитирует полный реальный поток: датчик Arduino сработал -> камера сняла кадр ->
    этот эндпоинт распознаёт номер и, если уверен в результате, сам вызывает
    соответствующий эндпоинт backend'а (/api/sim/entry или /api/sim/exit) -
    без участия человека
    """
    image_bytes = await _read_image(file)
    recognized = await _recognize_response(image_bytes)

    if not recognized.plate_number:
        return GateEventResponse(recognized=recognized, forwarded_to_backend=False,
                                  reject_reason="Номер не распознан")
    if not recognized.is_valid_region:
        return GateEventResponse(recognized=recognized, forwarded_to_backend=False,
                                  reject_reason=f"Код региона '{recognized.region_code}' вне диапазона 01-11")
    if recognized.corrections_applied > MAX_CORRECTIONS_TO_TRUST:
        return GateEventResponse(recognized=recognized, forwarded_to_backend=False,
                                  reject_reason=f"Слишком много исправленных символов "
                                                f"({recognized.corrections_applied}) - результату не доверяем")

    try:
        backend_response = await forward_plate_to_backend(gate, recognized.formatted)
    except httpx.HTTPStatusError as e:
        return GateEventResponse(
            recognized=recognized, forwarded_to_backend=False,
            reject_reason=f"Backend отклонил: {e.response.status_code} {e.response.text}",
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Backend недоступен: {e}")

    return GateEventResponse(recognized=recognized, forwarded_to_backend=True, backend_response=backend_response)


@app.get("/health", summary="Проверка, что сервис жив")
def health():
    return {"status": "ok", "service": "ocr-service"}
