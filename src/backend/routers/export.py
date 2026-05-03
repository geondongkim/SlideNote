"""PDF 내보내기 엔드포인트"""
import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse

from services.exporter import export_to_pdf, export_handout

router = APIRouter()
UPLOADS_DIR = Path("uploads")


def _validate_id(file_id: str) -> str:
    if len(file_id) != 32 or not all(c in "0123456789abcdef" for c in file_id):
        raise HTTPException(400, "잘못된 file_id")
    return file_id


def _get_meta(file_dir: Path) -> dict:
    meta_path = file_dir / "metadata.json"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _safe_filename(name: str) -> str:
    """Content-Disposition에 안전한 파일명 생성."""
    return "".join(c if c.isalnum() or c in "._- ()가-힣" else "_" for c in name)


@router.get("/{file_id}")
def download_pdf(file_id: str):
    fid = _validate_id(file_id)
    file_dir = UPLOADS_DIR / fid
    if not (file_dir / "slides").exists():
        raise HTTPException(404, "슬라이드를 찾을 수 없음")

    meta = _get_meta(file_dir)
    original_name = Path(meta.get("filename", "slidenote")).stem
    download_name = _safe_filename(original_name) + ".pdf"

    out_path = file_dir / "export.pdf"
    try:
        export_to_pdf(file_dir, out_path)
    except Exception as e:
        raise HTTPException(500, f"PDF 생성 실패: {e}")

    return FileResponse(
        str(out_path),
        media_type="application/pdf",
        filename=download_name,
    )


@router.get("/{file_id}/handout")
def download_handout(
    file_id: str,
    layout: Literal["1up", "2up", "4up"] = Query(default="2up"),
):
    """유인물 레이아웃 PDF 다운로드. layout=1up|2up|4up"""
    fid = _validate_id(file_id)
    file_dir = UPLOADS_DIR / fid
    if not (file_dir / "slides").exists():
        raise HTTPException(404, "슬라이드를 찾을 수 없음")

    meta = _get_meta(file_dir)
    original_name = Path(meta.get("filename", "slidenote")).stem
    download_name = _safe_filename(original_name) + f"_handout_{layout}.pdf"

    out_path = file_dir / f"handout_{layout}.pdf"
    try:
        export_handout(file_dir, out_path, layout=layout)
    except Exception as e:
        raise HTTPException(500, f"유인물 PDF 생성 실패: {e}")

    return FileResponse(
        str(out_path),
        media_type="application/pdf",
        filename=download_name,
    )


@router.get("/{file_id}/notes.md")
def download_notes_markdown(file_id: str):
    """모든 슬라이드의 노트를 Markdown 형식으로 묶어 반환"""
    fid = _validate_id(file_id)
    meta_path = UPLOADS_DIR / fid / "metadata.json"
    if not meta_path.exists():
        raise HTTPException(404, "파일을 찾을 수 없음")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    filename = meta.get("filename", "슬라이드")
    page_count = meta.get("pageCount", 0)
    notes_dir = UPLOADS_DIR / fid / "notes"

    lines: list[str] = [
        f"# {filename}",
        f"> SlideNote 내보내기  ",
        f"> 총 {page_count}페이지",
        "",
    ]

    for page in range(1, page_count + 1):
        note_path = notes_dir / f"slide_{page:02d}.json"
        text = ""
        ai_summary = ""
        if note_path.exists():
            data = json.loads(note_path.read_text(encoding="utf-8"))
            text = (data.get("text") or "").strip()
            ai_summary = (data.get("ai_summary") or "").strip()

        lines.append(f"## 슬라이드 {page}")
        if text:
            lines.append("")
            lines.append(text)
        if ai_summary:
            lines.append("")
            lines.append("**AI 요약**")
            lines.append("")
            lines.append(ai_summary)
        if not text and not ai_summary:
            lines.append("")
            lines.append("_(노트 없음)_")
        lines.append("")

    md_content = "\n".join(lines)
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in filename)
    return PlainTextResponse(
        content=md_content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_notes.md"'},
    )

