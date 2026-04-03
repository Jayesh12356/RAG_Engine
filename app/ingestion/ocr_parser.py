import base64
from typing import Any

import fitz
import openai
import structlog

from app.config import get_settings

logger = structlog.get_logger()

try:
    import pytesseract
    from PIL import Image
except Exception:  # pragma: no cover - optional runtime dependency
    pytesseract = None
    Image = None


def _pixmap_to_pil_image(pix: fitz.Pixmap):
    if Image is None:
        return None
    mode = "RGBA" if pix.alpha else "RGB"
    return Image.frombytes(mode, [pix.width, pix.height], pix.samples)


def _score_text_quality(text: str) -> float:
    stripped = " ".join(text.split())
    if not stripped:
        return 0.0
    letters = sum(ch.isalpha() for ch in stripped)
    printable = sum(ch.isprintable() and not ch.isspace() for ch in stripped)
    length = len(stripped)
    alpha_ratio = letters / max(length, 1)
    printable_ratio = printable / max(length, 1)
    length_score = min(1.0, length / 800.0)
    return round((0.5 * length_score) + (0.3 * alpha_ratio) + (0.2 * printable_ratio), 4)


def _extract_with_tesseract(pix: fitz.Pixmap, languages: str) -> tuple[str, float]:
    settings = get_settings()
    if pytesseract is None or Image is None:
        return "", 0.0
    if settings.TESSERACT_CMD.strip():
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD.strip()
    image = _pixmap_to_pil_image(pix)
    if image is None:
        return "", 0.0
    try:
        text = pytesseract.image_to_string(image, lang=languages).strip()
    except Exception as exc:  # pragma: no cover - depends on local tesseract install
        logger.warning("ocr.tesseract.failed", error=str(exc))
        return "", 0.0
    return text, _score_text_quality(text)


def _select_vision_client() -> tuple[openai.OpenAI | None, str]:
    settings = get_settings()
    if settings.OPENAI_API_KEY:
        return openai.OpenAI(api_key=settings.OPENAI_API_KEY, base_url="https://api.openai.com/v1"), "openai"
    if settings.OPENROUTER_API_KEY:
        return openai.OpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
        ), "openrouter"
    return None, ""


def _extract_with_vision_llm(pix: fitz.Pixmap, *, enabled: bool) -> str:
    settings = get_settings()
    if not enabled:
        return ""
    client, provider = _select_vision_client()
    if client is None:
        logger.info("ocr.vision.skipped", reason="missing_key")
        return ""

    png_bytes = pix.tobytes("png")
    encoded = base64.b64encode(png_bytes).decode("ascii")
    data_url = f"data:image/png;base64,{encoded}"
    prompt = (
        "Extract all readable text from this document page exactly as written. "
        "Preserve headings, lists, and tabular structure where possible. "
        "Return only plain extracted text."
    )
    try:
        response = client.chat.completions.create(
            model=settings.OCR_VISION_MODEL,
            messages=[
                {"role": "system", "content": "You are an OCR extraction assistant."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            temperature=0.0,
            max_tokens=1800,
            timeout=settings.LLM_REQUEST_TIMEOUT_SEC,
        )
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        logger.warning("ocr.vision.failed", error=str(exc), provider=provider)
        return ""
    return (response.choices[0].message.content or "").strip()


def extract_page_text_with_ocr(
    page: fitz.Page,
    page_number: int,
    pdf_name: str,
) -> dict[str, Any]:
    """
    OCR text extraction with hybrid fallback:
    1) Local Tesseract
    2) Vision LLM fallback when confidence is low
    """
    settings = get_settings()
    mode = settings.OCR_MODE
    zoom = max(settings.OCR_RENDER_DPI / 72.0, 1.0)
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)

    used_vision = False
    fallback_used = False

    if mode == "vision":
        vision_text = _extract_with_vision_llm(pix, enabled=True)
        vision_conf = _score_text_quality(vision_text)
        if vision_text.strip():
            text, confidence = vision_text.strip(), vision_conf
            used_vision = True
        else:
            text, confidence = _extract_with_tesseract(pix, settings.OCR_LANGUAGES)

    elif mode == "tesseract":
        text, confidence = _extract_with_tesseract(pix, settings.OCR_LANGUAGES)

    else:
        text, confidence = _extract_with_tesseract(pix, settings.OCR_LANGUAGES)
        if settings.OCR_VISION_FALLBACK_ENABLED and confidence < settings.OCR_TEXT_CONFIDENCE_THRESHOLD:
            fallback_text = _extract_with_vision_llm(pix, enabled=True)
            fallback_used = True
            fallback_conf = _score_text_quality(fallback_text)
            if fallback_conf >= confidence and fallback_text.strip():
                text = fallback_text
                confidence = fallback_conf
                used_vision = True

    logger.info(
        "ocr.page.complete",
        pdf_name=pdf_name,
        page_number=page_number,
        mode=mode,
        confidence=confidence,
        used_vision=used_vision,
        fallback_attempted=fallback_used,
    )
    return {
        "text": text.strip(),
        "confidence": confidence,
        "used_vision": used_vision,
        "fallback_attempted": fallback_used,
    }
