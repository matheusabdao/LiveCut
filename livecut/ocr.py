"""
Lightweight OCR helper for user-uploaded chat screenshots.

Uses ``rapidocr-onnxruntime`` (ONNX-based, no external binary required). The
extracted text is fed into the clip selector's keyword list so moments where
those phrases appear get a higher score.

Falls back gracefully if the OCR engine cannot be imported.
"""

from __future__ import annotations

from typing import List

_ocr_engine = None


def _get_engine():
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR

            _ocr_engine = RapidOCR()
        except Exception:
            _ocr_engine = False
    return _ocr_engine if _ocr_engine is not False else None


def extract_text(image_path: str) -> str:
    """Return all recognized text from an image, joined by spaces.

    Returns an empty string if OCR is unavailable or no text is found.
    """
    engine = _get_engine()
    if engine is None:
        return ""
    try:
        result, _ = engine(image_path)
    except Exception:
        return ""
    if not result:
        return ""
    lines: List[str] = []
    for item in result:
        # item = [box, text, confidence]
        if len(item) >= 2 and isinstance(item[1], str):
            lines.append(item[1].strip())
    return " ".join(line for line in lines if line)


def ocr_available() -> bool:
    return _get_engine() is not None
