from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

MIN_ASPECT, MAX_ASPECT = 2.3, 6.5


@dataclass
class PlateCrop:
    image: np.ndarray            
    method: str                  
    score: float                 
    box: Optional[np.ndarray]    


def _order_points(pts: np.ndarray) -> np.ndarray:
    pts = pts.astype("float32")
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype="float32")


def _warp(img: np.ndarray, box: np.ndarray) -> np.ndarray:
    tl, tr, br, bl = _order_points(box)
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if height > width:  # повёрнутый на 90°
        width, height = height, width
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")
    m = cv2.getPerspectiveTransform(np.array([tl, tr, br, bl], dtype="float32"), dst)
    return cv2.warpPerspective(img, m, (width, height), flags=cv2.INTER_CUBIC)


def _score_candidate(gray: np.ndarray, rect) -> float:
    (cx, cy), (rw, rh), _ = rect
    if rw < 1 or rh < 1:
        return 0.0
    w, h = max(rw, rh), min(rw, rh)
    aspect = w / h
    if not (MIN_ASPECT <= aspect <= MAX_ASPECT) or w < 50:
        return 0.0

    box = cv2.boxPoints(rect).astype(np.int32)
    mask = np.zeros(gray.shape, np.uint8)
    cv2.fillConvexPoly(mask, box, 255)
    pixels = gray[mask > 0]
    if pixels.size < 200:
        return 0.0

    thr = np.percentile(pixels, 60)
    bright_bg = float(np.mean(pixels > max(thr * 0.8, 90)))
    dark_ratio = float(np.mean(pixels < (pixels.mean() * 0.6)))
    contrast = float(pixels.std() / 128.0)

    aspect_score = 1.0 - min(abs(aspect - 4.6) / 3.0, 1.0)
    char_score = 1.0 - min(abs(dark_ratio - 0.22) / 0.22, 1.0)
    return 0.35 * aspect_score + 0.30 * char_score + 0.20 * min(contrast, 1.0) + 0.15 * bright_bg


def _candidates_bright(gray: np.ndarray) -> List:
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    out = []
    for thr in (200, 170, 140):
        _, th = cv2.threshold(blur, thr, 255, cv2.THRESH_BINARY)
        th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (7, 3)))
        cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out += [cv2.minAreaRect(c) for c in cnts if cv2.contourArea(c) > 300]
    return out


def _candidates_blackhat(gray: np.ndarray) -> List:
    rect_kern = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 7))
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, rect_kern)
    _, th = cv2.threshold(blackhat, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (31, 9)))
    th = cv2.erode(th, None, iterations=1)
    th = cv2.dilate(th, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 5)), iterations=1)
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return [cv2.minAreaRect(c) for c in cnts if cv2.contourArea(c) > 300]


def find_plate(img: np.ndarray) -> PlateCrop:
    h, w = img.shape[:2]

    if w / h >= 3.0 and w <= 1000:
        return PlateCrop(img, "already_cropped", 0.9, None)

    scale = 1.0
    if max(h, w) > 1100:
        scale = 1100 / max(h, w)
        small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    else:
        small = img
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    scored: List[Tuple[float, str, object]] = []
    for method, rects in (("bright", _candidates_bright(gray)), ("blackhat", _candidates_blackhat(gray))):
        for rect in rects:
            s = _score_candidate(gray, rect)
            if s > 0:
                scored.append((s, method, rect))

    if not scored:
        return PlateCrop(img, "fallback_full_frame", 0.0, None)

    scored.sort(key=lambda t: t[0], reverse=True)
    best_score, method, rect = scored[0]

    (cx, cy), (rw, rh), ang = rect
    rect = ((cx, cy), (rw * 1.06 + 4, rh * 1.12 + 4), ang)
    box = cv2.boxPoints(rect) / scale
    crop = _warp(img, box)
    return PlateCrop(crop, method, float(best_score), box)
