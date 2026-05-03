"""PDF 내보내기 엔드포인트"""
import json
from pathlib import Path
from typing import Literal
from urllib.parse import quote

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


def _content_disposition(filename: str) -> str:
    """RFC 5987 형식 Content-Disposition 헤더 값. 한글/특수문자 파일명 지원."""
    encoded = quote(filename, safe="")
    return f'attachment; filename="download"; filename*=UTF-8\'\'{encoded}'


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
        headers={"Content-Disposition": _content_disposition(f"{safe_name}_notes.md")},
    )


@router.get("/{file_id}/slides.md")
def download_slides_markdown(file_id: str):
    """
    슬라이드 원문 Markdown 다운로드 (Obsidian/Notion/NotebookLM 최적화).

    POST /api/ai/{file_id}/to-markdown 변환 완료 후 이 엔드포인트로 다운로드.

    notes.md(사용자 노트+AI요약)와 다른 파일:
    - notes.md      : 사용자가 입력한 노트 + AI 요약 (발표자 노트 형식)
    - slides.md     : 슬라이드 원문을 충실하게 변환한 구조화된 Markdown
    """
    from datetime import date

    fid = _validate_id(file_id)
    meta_path = UPLOADS_DIR / fid / "metadata.json"
    if not meta_path.exists():
        raise HTTPException(404, "파일을 찾을 수 없음")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    filename = meta.get("filename", "슬라이드")
    ext = meta.get("ext", "")
    page_count = meta.get("pageCount", 0)
    notes_dir = UPLOADS_DIR / fid / "notes"

    # 변환된 슬라이드 Markdown 존재 여부 확인
    converted_count = 0
    for page in range(1, page_count + 1):
        note_path = notes_dir / f"slide_{page:02d}.json"
        if note_path.exists():
            try:
                data = json.loads(note_path.read_text(encoding="utf-8"))
                if data.get("slide_markdown"):
                    converted_count += 1
            except Exception:
                pass

    if converted_count == 0:
        raise HTTPException(
            404,
            "변환된 슬라이드 Markdown이 없습니다. "
            "먼저 '슬라이드 → Markdown 변환'을 실행해 주세요.",
        )

    stem = Path(filename).stem
    today = date.today().isoformat()

    # YAML frontmatter (Obsidian 호환)
    lines: list[str] = [
        "---",
        f'title: "{stem}"',
        f'source: "{filename}"',
        f'converted: "{today}"',
        f"slides: {page_count}",
        "tags:",
        "  - slidenote",
        "  - presentation",
        "---",
        "",
        f"# {stem}",
        "",
        f"> **원본**: {filename}  ",
        f"> **슬라이드**: {page_count}장  ",
        f"> **변환**: {today} (SlideNote 슬라이드 Markdown 변환)",
        f"> **참고**: 이 파일은 슬라이드 원문 변환입니다. 발표자 노트 AI 요약은 `{stem}_notes.md`를 참조하세요.",
        "",
    ]

    for page in range(1, page_count + 1):
        note_path = notes_dir / f"slide_{page:02d}.json"
        slide_md = ""
        if note_path.exists():
            try:
                data = json.loads(note_path.read_text(encoding="utf-8"))
                slide_md = (data.get("slide_markdown") or "").strip()
            except Exception:
                pass

        lines.append(f"## 슬라이드 {page}")
        lines.append("")
        if slide_md:
            lines.append(slide_md)
        else:
            lines.append("_(변환 데이터 없음 — 변환을 다시 실행해 주세요)_")
        lines.append("")
        lines.append("---")
        lines.append("")

    md_content = "\n".join(lines)
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in stem)
    return PlainTextResponse(
        content=md_content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": _content_disposition(f"{safe_name}_slides.md")},
    )
