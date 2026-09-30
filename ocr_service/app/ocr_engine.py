import threading
from dataclasses import dataclass
from typing import List

import cv2
import numpy as np

from app.plate_detector import find_plate, PlateCrop

_reader = None
_reader_lock = threading.Lock()


def get_reader():
    global _reader
    if _reader is None:
        with _reader_lock:
            if _reader is None:  
                import easyocr
                _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


@dataclass
class Detection:
    text: str
    confidence: float
    x: float  


def decode_image(image_bytes: bytes) -> np.ndarray:
    np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Не удалось декодировать изображение")
    return img


def _prep_for_ocr(plate_img: np.ndarray) -> np.ndarray:
    h, w = plate_img.shape[:2]
    if w < 300:
        scale = 300 / w
        plate_img = cv2.resize(plate_img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 15, 15)
    return gray


def run_ocr(image_bytes: bytes) -> tuple[List[Detection], PlateCrop]:
    frame = decode_image(image_bytes)
    plate_crop = find_plate(frame)
    prepared = _prep_for_ocr(plate_crop.image)

    reader = get_reader()
    raw = reader.readtext(prepared)  

    detections = [
        Detection(text=text, confidence=float(conf), x=float(min(p[0] for p in bbox)))
        for bbox, text, conf in raw
    ]
    detections.sort(key=lambda d: d.x)
    return detections, plate_crop
