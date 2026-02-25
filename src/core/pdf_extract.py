from __future__ import annotations
from pathlib import Path

def extract_text_from_pdf(pdf_path: Path) -> str:
    text = ""

    # 1) pdfplumber (god til tekstlag)
    try:
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                text += t + "\n"
    except Exception:
        pass

    # 2) fallback: PyMuPDF
    if len(text.strip()) < 50:
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            text = "\n".join([page.get_text("text") for page in doc])
        except Exception:
            pass

    # 3) OCR fallback (klar til senere)
    # if len(text.strip()) < 50:
    #     text = ocr_pdf(pdf_path)

    return text.strip()
