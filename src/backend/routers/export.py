"""PDF 내보내기 엔드포인트"""
import json
import asyncio
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse

from services.exporter import export_to_pdf, export_handout
from services.converter import pptx_to_pdf_native

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


# ─── 고품질 PPTX → PDF 변환 (벡터/폰트/하이퍼링크 보존) ─────────────────────

@router.get("/{file_id}/original-pdf/convert")
async def convert_original_pdf(file_id: str):
    """PPTX → 고품질 PDF SSE 변환 스트림.

    - PDF 원본: 즉시 완료 (변환 불필요)
    - PPTX: win32com(Windows) / Gotenberg / LibreOffice 순으로 변환
    - 진행 이벤트: {"status": "converting"|"done"|"error", "message": "..."}
    """
    fid = _validate_id(file_id)
    file_dir = UPLOADS_DIR / fid
    meta_path = file_dir / "metadata.json"
    if not meta_path.exists():
        raise HTTPException(404, "파일을 찾을 수 없음")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    ext = meta.get("ext", "").lower()
    original_name = Path(meta.get("filename", "slidenote")).stem

    async def stream():
        import concurrent.futures

        def _sse(data: dict) -> str:
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        # PDF 원본이면 변환 필요 없음
        if ext == "pdf":
            original_pdf = file_dir / "original.pdf"
            if original_pdf.exists():
                yield _sse({"status": "done", "message": "PDF 원본 파일 준비 완료"})
                return
            yield _sse({"status": "error", "message": "원본 PDF를 찾을 수 없습니다"})
            return

        # PPTX 변환
        pptx_path = file_dir / "original.pptx"
        if not pptx_path.exists():
            yield _sse({"status": "error", "message": "원본 PPTX 파일을 찾을 수 없습니다"})
            return

        out_pdf = file_dir / "original_hq.pdf"
        yield _sse({"status": "converting", "message": "고품질 PDF 변환 중…"})

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                concurrent.futures.ThreadPoolExecutor(max_workers=1),
                pptx_to_pdf_native,
                pptx_path,
                out_pdf,
            )
            yield _sse({"status": "done", "message": f"{original_name}.pdf 변환 완료"})
        except Exception as e:
            yield _sse({"status": "error", "message": str(e)})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{file_id}/original-pdf")
def download_original_pdf(file_id: str):
    """변환된(또는 원본) 고품질 PDF 다운로드."""
    fid = _validate_id(file_id)
    file_dir = UPLOADS_DIR / fid
    meta_path = file_dir / "metadata.json"
    if not meta_path.exists():
        raise HTTPException(404, "파일을 찾을 수 없음")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    ext = meta.get("ext", "").lower()
    original_name = Path(meta.get("filename", "slidenote")).stem
    download_name = _safe_filename(original_name) + ".pdf"

    # PDF 원본
    if ext == "pdf":
        pdf_path = file_dir / "original.pdf"
        if not pdf_path.exists():
            raise HTTPException(404, "원본 PDF 파일 없음")
        return FileResponse(str(pdf_path), media_type="application/pdf", filename=download_name)

    # PPTX → 고품질 변환본
    hq_pdf = file_dir / "original_hq.pdf"
    if not hq_pdf.exists():
        raise HTTPException(
            404,
            "변환된 PDF가 없습니다. 먼저 변환 요청(/convert)을 실행하세요.",
        )
    return FileResponse(str(hq_pdf), media_type="application/pdf", filename=download_name)

