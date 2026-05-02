"""
PPTX / PDF → PNG 변환

검증된 전략:
- PDF: PyMuPDF, DPI=150 (속도/품질 최적)
- PPTX (Windows): win32com + PowerPoint COM, 1920px
- PPTX (Linux/Mac): LibreOffice headless → PDF → PyMuPDF (Phase 2: Gotenberg)
"""
from __future__ import annotations

import logging
import platform
import subprocess
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

DPI = 150
PNG_WIDTH = 1920


def pdf_to_pngs(pdf_path: Path, out_dir: Path, dpi: int = DPI) -> list[Path]:
    """PDF → PNG (PyMuPDF). 1-based 파일명: page_01.png ..."""
    out_dir.mkdir(parents=True, exist_ok=True)
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    results: list[Path] = []
    with fitz.open(str(pdf_path)) as doc:
        for i, page in enumerate(doc, start=1):
            png_path = out_dir / f"page_{i:02d}.png"
            page.get_pixmap(matrix=matrix).save(str(png_path))
            results.append(png_path)
    logger.info("PDF 변환 완료: %d페이지 → %s", len(results), out_dir)
    return results


def pptx_to_pngs(pptx_path: Path, out_dir: Path) -> list[Path]:
    """PPTX → PNG. Windows는 win32com, 그 외는 LibreOffice 폴백."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if platform.system() == "Windows":
        return _win32_pptx_to_pngs(pptx_path, out_dir)
    return _libreoffice_pptx_to_pngs(pptx_path, out_dir)


def _win32_pptx_to_pngs(pptx_path: Path, out_dir: Path) -> list[Path]:
    """PowerPoint COM (pywin32). Visible=True, 1-based, list() 변환 필수."""
    import pythoncom  # noqa: F401  pywin32 동반 설치
    from win32com import client as win32

    powerpoint = win32.Dispatch("PowerPoint.Application")
    powerpoint.Visible = True  # 필수: False 시 일부 환경에서 실패
    try:
        prs = powerpoint.Presentations.Open(
            str(pptx_path.resolve()), WithWindow=False, ReadOnly=True
        )
        try:
            slides = list(prs.Slides)  # 슬라이스 오류 방지
            results: list[Path] = []
            for i, slide in enumerate(slides, start=1):
                png_path = out_dir / f"page_{i:02d}.png"
                # ppFixedFormatTypePNG는 Export로 저장 (가로 1920)
                slide.Export(str(png_path), "PNG", PNG_WIDTH)
                results.append(png_path)
            return results
        finally:
            prs.Close()
    finally:
        powerpoint.Quit()


def _libreoffice_pptx_to_pngs(pptx_path: Path, out_dir: Path) -> list[Path]:
    """LibreOffice headless → PDF 변환 후 PyMuPDF로 PNG 추출."""
    pdf_path = out_dir / f"{pptx_path.stem}.pdf"
    cmd = [
        "libreoffice",
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
        str(pptx_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    if not pdf_path.exists():
        raise RuntimeError(f"LibreOffice 변환 실패: {pdf_path}")
    try:
        return pdf_to_pngs(pdf_path, out_dir)
    finally:
        pdf_path.unlink(missing_ok=True)
