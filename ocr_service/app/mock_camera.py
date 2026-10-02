import os
import platform
import time
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

CAMERA_INDEX_BY_GATE = {"entry": 0, "exit": 0}

WARMUP_FRAMES = int(os.getenv("CAMERA_WARMUP_FRAMES", "5"))

CAPTURE_DELAY_SECONDS = float(os.getenv("CAMERA_CAPTURE_DELAY_SECONDS", "0"))


class MockVideoCapture:

    def __init__(self, fixture_path: Path):
        self._fixture_path = fixture_path

    def isOpened(self) -> bool:
        return self._fixture_path.exists()

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        img = cv2.imread(str(self._fixture_path))
        if img is None:
            return False, None
        return True, img

    def release(self) -> None:
        pass


class RealVideoCapture:
    def __init__(self, index: int):
        if platform.system() == "Windows":
            self._cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        else:
            self._cap = cv2.VideoCapture(index)

    def isOpened(self) -> bool:
        return self._cap.isOpened()

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        for _ in range(WARMUP_FRAMES):
            self._cap.read()
            time.sleep(0.03)
        return self._cap.read()

    def release(self) -> None:
        self._cap.release()


def get_camera(gate: str):
    index = CAMERA_INDEX_BY_GATE.get(gate, 0)
    cam = RealVideoCapture(index)
    if cam.isOpened():
        return cam
    cam.release()

    fixture = FIXTURES_DIR / f"{gate}_camera_sample.jpg"
    if not fixture.exists():
        fixture = FIXTURES_DIR / "sample_plate.jpg"
    return MockVideoCapture(fixture)


def capture_frame_bytes(gate: str) -> Tuple[bytes, str]:
    if CAPTURE_DELAY_SECONDS > 0:
        time.sleep(CAPTURE_DELAY_SECONDS)

    cam = get_camera(gate)
    source = "webcam" if isinstance(cam, RealVideoCapture) else "fixture"

    if not cam.isOpened():
        raise RuntimeError(f"Камера для '{gate}' недоступна")

    ok, frame = cam.read()
    cam.release()
    if not ok or frame is None:
        raise RuntimeError(f"Не удалось получить кадр с камеры '{gate}'")

    success, buf = cv2.imencode(".jpg", frame)
    if not success:
        raise RuntimeError("Не удалось закодировать кадр в JPEG")
    return buf.tobytes(), source
