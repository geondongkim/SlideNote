"""
PPTX / PDF → PNG 변환

검증된 전략:
- PDF: PyMuPDF, DPI=150 (속도/품질 최적)
- PPTX (Windows): win32com + PowerPoint COM, 1920px
- PPTX (Linux/Mac): LibreOffice headless → PDF → PyMuPDF (Phase 2: Gotenberg)
"""
from __future__ import annotations

import logging
import os
import platform
import subprocess
import tempfile
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
    """PPTX → PNG. Windows는 win32com, Linux는 Gotenberg(우선) 또는 LibreOffice 폴백."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if platform.system() == "Windows":
        return _win32_pptx_to_pngs(pptx_path, out_dir)
    gotenberg_url = os.environ.get("GOTENBERG_URL")
    if gotenberg_url:
        return _gotenberg_pptx_to_pngs(pptx_path, out_dir, gotenberg_url)
    return _libreoffice_pptx_to_pngs(pptx_path, out_dir)


def _win32_pptx_to_pngs(pptx_path: Path, out_dir: Path) -> list[Path]:
    """PowerPoint COM — Python subprocess로 실행.

    uvicorn 이벤트루프 스레드에서 COM STA 충돌을 피하기 위해
    별도 Python 프로세스를 생성해 COM 변환을 수행한다.
    부모 프로세스의 window station을 상속하므로 Visible=True 설정 가능.
    """
    import sys
    import tempfile

    abs_pptx = str(pptx_path.resolve())
    abs_out  = str(out_dir.resolve())

    py_script = f"""\
import pythoncom, win32com.client, sys
from pathlib import Path
pythoncom.CoInitialize()
app = win32com.client.DispatchEx('PowerPoint.Application')
app.Visible = True
try:
    prs = app.Presentations.Open({abs_pptx!r}, False, False, True)
    try:
        for i, slide in enumerate(prs.Slides, 1):
            png = str(Path({abs_out!r}) / f'page_{{i:02d}}.png')
            slide.Export(png, 'PNG', {PNG_WIDTH})
        print(prs.Slides.Count)
    finally:
        prs.Close()
finally:
    try: app.Quit()
    except: pass
    pythoncom.CoUninitialize()
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(py_script)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True, text=True, timeout=300,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"PPTX COM 변환 실패:\n{result.stderr.strip()}")

    pngs = sorted(out_dir.glob("page_*.png"))
    if not pngs:
        raise RuntimeError("변환 결과 PNG 없음")
    logger.info("PPTX 변환 완료: %d슬라이드 → %s", len(pngs), out_dir)
    return pngs


def _gotenberg_pptx_to_pngs(pptx_path: Path, out_dir: Path, gotenberg_url: str) -> list[Path]:
    """Gotenberg LibreOffice API → PDF bytes → PyMuPDF PNG 변환 (Linux/Docker)."""
    import httpx

    endpoint = f"{gotenberg_url.rstrip('/')}/forms/libreoffice/convert"
    with open(pptx_path, "rb") as f:
        resp = httpx.Client(timeout=300).post(
            endpoint,
            files={"files": (pptx_path.name, f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            data={"exportHiddenSlides": "false", "quality": "90"},
        )
    resp.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(resp.content)
        tmp_path = Path(tmp.name)
    try:
        result = pdf_to_pngs(tmp_path, out_dir)
    finally:
        tmp_path.unlink(missing_ok=True)

    logger.info("Gotenberg PPTX 변환 완료: %d슬라이드 → %s", len(result), out_dir)
    return result


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


# ─── 고품질 PPTX → PDF 변환 (벡터/폰트 보존) ────────────────────────────────

def pptx_to_pdf_native(pptx_path: Path, out_path: Path) -> Path:
    """PPTX → 고품질 네이티브 PDF 변환 (벡터·폰트·하이퍼링크 보존).

    우선순위:
    1. Windows — PowerPoint COM (SaveAs ppSaveAsPDF=32): 최고 품질
    2. Linux + GOTENBERG_URL — Gotenberg LibreOffice API: PDF bytes 직접 반환
    3. Linux fallback — LibreOffice headless: 로컬 변환
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if platform.system() == "Windows":
        return _win32_pptx_to_pdf(pptx_path, out_path)

    gotenberg_url = os.environ.get("GOTENBERG_URL")
    if gotenberg_url:
        return _gotenberg_pptx_to_pdf(pptx_path, out_path, gotenberg_url)

    return _libreoffice_pptx_to_pdf(pptx_path, out_path)


def _win32_pptx_to_pdf(pptx_path: Path, out_path: Path) -> Path:
    """PowerPoint COM으로 PPTX → PDF (ppSaveAsPDF=32). 벡터·폰트·링크 완전 보존."""
    import sys

    abs_pptx = str(pptx_path.resolve())
    abs_pdf = str(out_path.resolve())

    py_script = f"""\
import pythoncom, win32com.client
from pathlib import Path
pythoncom.CoInitialize()
app = win32com.client.DispatchEx('PowerPoint.Application')
app.Visible = True
try:
    prs = app.Presentations.Open({abs_pptx!r}, False, False, True)
    try:
        prs.SaveAs({abs_pdf!r}, 32)  # ppSaveAsPDF = 32
    finally:
        prs.Close()
finally:
    try: app.Quit()
    except: pass
    pythoncom.CoUninitialize()
print('ok')
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(py_script)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True, text=True, timeout=300,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"PPTX→PDF COM 변환 실패:\n{result.stderr.strip()}")

    if not out_path.exists():
        raise RuntimeError("PowerPoint COM이 PDF를 생성하지 않음")

    logger.info("PowerPoint COM PDF 변환 완료: %s", out_path)
    return out_path


def _gotenberg_pptx_to_pdf(pptx_path: Path, out_path: Path, gotenberg_url: str) -> Path:
    """Gotenberg LibreOffice API → PDF bytes 직접 저장 (PNG 변환 없음, 고품질)."""
    import httpx

    endpoint = f"{gotenberg_url.rstrip('/')}/forms/libreoffice/convert"
    with open(pptx_path, "rb") as f:
        resp = httpx.Client(timeout=300).post(
            endpoint,
            files={
                "files": (
                    pptx_path.name,
                    f,
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
            },
            data={"exportHiddenSlides": "false"},
        )
    resp.raise_for_status()
    out_path.write_bytes(resp.content)
    logger.info("Gotenberg PDF 변환 완료: %s (%d bytes)", out_path, len(resp.content))
    return out_path


def _libreoffice_pptx_to_pdf(pptx_path: Path, out_path: Path) -> Path:
    """LibreOffice headless PPTX → PDF."""
    cmd = [
        "libreoffice",
        "--headless",
        "--convert-to", "pdf",
        "--outdir", str(out_path.parent),
        str(pptx_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    # LibreOffice는 outdir에 {stem}.pdf로 저장
    generated = out_path.parent / f"{pptx_path.stem}.pdf"
    if not generated.exists():
        raise RuntimeError(f"LibreOffice PDF 변환 실패: {generated}")
    if generated != out_path:
        generated.rename(out_path)
    logger.info("LibreOffice PDF 변환 완료: %s", out_path)
    return out_path

