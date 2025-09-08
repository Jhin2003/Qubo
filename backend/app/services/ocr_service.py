# ocr_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

import logging
import numpy as np
import cv2

from paddleocr import PaddleOCR


__all__ = ["OCRConfig", "PaddleOCRService"]


@dataclass
class OCRConfig:
    """Configuration for PaddleOCRService."""
    lang: str = "en"           # e.g., 'en', 'en_mobile', 'ch', 'korean'
    use_angle_cls: bool = True
    default_dpi: int = 300     # rasterization dpi for pdf pages


def _silence_paddle_logs(level: int = logging.ERROR) -> None:
    """
    Optional: silence noisy logs from PaddleOCR modules.
    Call once at startup if desired.
    """
    for name in ("ppocr", "ppocr.utils.utility", "ppocr.postprocess"):
        logging.getLogger(name).setLevel(level)


class PaddleOCRService:
    """
    Reusable OCR service for:
      - Full-page OCR from a pdfplumber Page
      - OCR for only embedded image regions on a Page
      - OCR for non-text regions (masking native text before OCR)
      - Direct OCR of a PIL image
    """
    _instance: Optional["PaddleOCRService"] = None

    def __init__(self, config: Optional[OCRConfig] = None) -> None:
        self.config = config or OCRConfig()
        # Initialize PaddleOCR once (expensive).
        self._ocr = PaddleOCR(
            use_angle_cls=self.config.use_angle_cls,
            lang=self.config.lang,
        )

    @classmethod
    def get(cls, config: Optional[OCRConfig] = None) -> "PaddleOCRService":
        """
        Singleton accessor to avoid repeated heavy initializations.
        If you need multiple instances with different configs,
        instantiate the class directly instead of using .get().
        """
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance

    # ----------------- Public API -----------------

    def ocr_pil_image(self, pil_img) -> str:
        """
        OCR a PIL.Image and return extracted text (one line per detection).
        """
        img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return self._run_ocr(img_bgr)

    def ocr_full_page(self, page, dpi: Optional[int] = None) -> str:
        """
        OCR the entire pdfplumber Page.
        """
        dpi = dpi or self.config.default_dpi
        pil_img = page.to_image(resolution=dpi).original
        return self.ocr_pil_image(pil_img)

    def ocr_images_on_page(self, page, dpi: Optional[int] = None) -> str:
        """
        OCR only the embedded image regions on a pdfplumber Page.
        Uses each image's bbox to crop and OCR.
        """
        if not getattr(page, "images", None):
            return ""

        dpi = dpi or self.config.default_dpi
        texts: List[str] = []

        for img in page.images:
            # pdfplumber image dict has x0, x1, top, bottom in points
            bbox = (img["x0"], img["top"], img["x1"], img["bottom"])
            region = page.within_bbox(bbox)
            pil_img = region.to_image(resolution=dpi).original
            t = self.ocr_pil_image(pil_img)
            if t:
                texts.append(t)

        return "\n".join(texts).strip()

    def ocr_non_text_regions(
        self,
        page,
        dpi: Optional[int] = None,
        text_margin_pts: float = 2.0,
    ) -> str:
        """
        OCR only the parts of the page that do NOT contain native PDF text.
        - Renders page to image
        - Masks native text bounding boxes (from extract_words)
        - Runs OCR on the masked image
        """
        dpi = dpi or self.config.default_dpi
        pil_img = page.to_image(resolution=dpi).original

        img = np.array(pil_img)  # RGB
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        # 1 PDF point = 1/72 inch; pixels_per_point = dpi / 72
        px_per_pt = dpi / 72.0
        words = page.extract_words(use_text_flow=True) or []

        # Paint white rectangles over native text areas to prevent re-OCR.
        for w in words:
            x0 = int((w["x0"] - text_margin_pts) * px_per_pt)
            y0 = int((w["top"] - text_margin_pts) * px_per_pt)
            x1 = int((w["x1"] + text_margin_pts) * px_per_pt)
            y1 = int((w["bottom"] + text_margin_pts) * px_per_pt)

            # clamp to image bounds
            x0 = max(0, x0)
            y0 = max(0, y0)
            x1 = min(img_bgr.shape[1] - 1, x1)
            y1 = min(img_bgr.shape[0] - 1, y1)

            cv2.rectangle(img_bgr, (x0, y0), (x1, y1), (255, 255, 255), thickness=-1)

        return self._run_ocr(img_bgr)

    # ----------------- Internal -----------------

    def _run_ocr(self, img_bgr) -> str:
        """
        Run PaddleOCR on a BGR np.ndarray and join results as lines.
        """
        result = self._ocr.ocr(img_bgr, cls=True)
        lines: List[str] = []
        if result:
            for block in result:
                if not block:
                    continue
                for (_, (text, _conf)) in block:
                    if text:
                        lines.append(text)
        return "\n".join(lines).strip()
