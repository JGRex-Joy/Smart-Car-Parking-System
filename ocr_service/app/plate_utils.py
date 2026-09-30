import re
from dataclasses import dataclass
from typing import Optional, Tuple

VALID_REGION_CODES = {f"{i:02d}" for i in range(1, 12)}  # 01..11

LETTER_TO_DIGIT = {
    "O": "0", "Q": "0", "D": "0",
    "I": "1", "L": "1", "J": "1",
    "Z": "2", "S": "5", "G": "6", "T": "7", "B": "8",
}

DIGIT_TO_LETTER = {
    "0": "O", "1": "I", "2": "Z", "5": "S", "6": "G", "7": "T", "8": "B",
}


@dataclass
class PlateCandidate:
    region: str          
    serial: str          
    letters: str         
    corrections: int     

    @property
    def plate_number(self) -> str:
        return f"{self.region}{self.serial}{self.letters}"

    @property
    def formatted(self) -> str:
        return f"{self.region} KG {self.serial} {self.letters}"

    @property
    def is_valid_region(self) -> bool:
        return self.region in VALID_REGION_CODES


def clean(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", text).upper()


def fix_as_digits(s: str) -> Tuple[Optional[str], int]:
    out, fixes = [], 0
    for ch in s:
        if ch.isdigit():
            out.append(ch)
        elif ch in LETTER_TO_DIGIT:
            out.append(LETTER_TO_DIGIT[ch])
            fixes += 1
        else:
            return None, 0
    return "".join(out), fixes


def fix_as_letters(s: str) -> Tuple[Optional[str], int]:
    out, fixes = [], 0
    for ch in s:
        if ch.isalpha():
            out.append(ch)
        elif ch in DIGIT_TO_LETTER:
            out.append(DIGIT_TO_LETTER[ch])
            fixes += 1
        else:
            return None, 0
    return "".join(out), fixes


def _rank(c: PlateCandidate):
    return (0 if c.is_valid_region else 1, c.corrections, -len(c.letters))


def extract_plate(raw_text: str) -> Optional[PlateCandidate]:
    s = clean(raw_text)

    variants = {s}
    if "KG" in s:
        variants.add(s.replace("KG", ""))
    m = re.match(r"^(\w{2})KG(\w+)$", s)
    if m:
        variants.add(m.group(1) + m.group(2))

    best: Optional[PlateCandidate] = None
    for v in variants:
        for length in (8, 7):
            for start in range(0, len(v) - length + 1):
                w = v[start:start + length]
                region, f1 = fix_as_digits(w[:2])
                serial, f2 = fix_as_digits(w[2:5])
                letters, f3 = fix_as_letters(w[5:])
                if region is None or serial is None or letters is None:
                    continue
                cand = PlateCandidate(region, serial, letters, f1 + f2 + f3)
                if best is None or _rank(cand) < _rank(best):
                    best = cand
    return best
