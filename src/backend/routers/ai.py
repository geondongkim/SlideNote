"""AI 요약 / 슬라이드 Markdown 변환 엔드포인트"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.gemini import convert_slide_to_markdown, summarize_slide

logger = logging.getLogger(__name__)
router = APIRouter()
UPLOADS_DIR = Path("uploads")
GEMINI_DELAY = 7.0  # 무료 티어 ~10 RPM 대응


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


class SummarizeRequest(BaseModel):
    page: int


@router.post("/{file_id}/summarize")
async def summarize(file_id: str, req: SummarizeRequest):
    if len(file_id) != 32 or not all(c in "0123456789abcdef" for c in file_id):
        raise HTTPException(400, "잘못된 file_id")
    if req.page < 1:
        raise HTTPException(400, "page는 1 이상")

    img_path = UPLOADS_DIR / file_id / "slides" / f"page_{req.page:02d}.png"
    if not img_path.exists():
        raise HTTPException(404, f"슬라이드 {req.page}를 찾을 수 없음")

    try:
        summary = await summarize_slide(img_path)
    except ValueError as e:
        raise HTTPException(503, str(e))
    except RuntimeError as e:
        logger.exception("Gemini 요약 실패")
        raise HTTPException(502, str(e))

    # 노트 파일에 ai_summary 업데이트 (slide_markdown과 별도 필드)
    note_path = UPLOADS_DIR / file_id / "notes" / f"slide_{req.page:02d}.json"
    if note_path.exists():
        note = json.loads(note_path.read_text(encoding="utf-8"))
    else:
        note = {"text": "", "annotations": {}, "ai_summary": "", "updated_at": None}
    note["ai_summary"] = summary
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"fileId": file_id, "page": req.page, "summary": summary}


@router.post("/{file_id}/to-markdown")
async def convert_to_markdown(file_id: str):
    """
    전체 슬라이드 → 구조화된 Markdown 변환 (원문 충실, 요약 아님).

    AI 요약(POST /{file_id}/summarize)과 다른 기능:
    - summarize: 슬라이드 내용을 압축해 '발표자 노트' 형식으로 요약
    - to-markdown: 슬라이드의 모든 텍스트/표/다이어그램을 빠짐없이 Markdown으로 변환

    SSE(text/event-stream)로 진행률을 스트리밍한다:
      {"status": "start",      "total": N}
      {"status": "converting", "page": N, "total": N}
      {"status": "done",       "page": N, "total": N}  (각 슬라이드 완료)
      {"status": "complete",   "total": N}
      {"status": "error",      "page": N, "message": "..."}
    """
    if len(file_id) != 32 or not all(c in "0123456789abcdef" for c in file_id):
        raise HTTPException(400, "잘못된 file_id")

    slides_dir = UPLOADS_DIR / file_id / "slides"
    if not slides_dir.exists():
        raise HTTPException(404, "슬라이드를 찾을 수 없음")

    slide_files = sorted(slides_dir.glob("page_*.png"))
    total = len(slide_files)
    if total == 0:
        raise HTTPException(404, "슬라이드 PNG가 없음")

    notes_dir = UPLOADS_DIR / file_id / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    meta_path = UPLOADS_DIR / file_id / "metadata.json"
    filename = file_id
    pptx_path: Path | None = None
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            filename = Path(meta.get("filename", file_id)).stem
            # PPTX 원본이 있으면 메타데이터 보강에 활용
            if meta.get("ext") == ".pptx":
                candidate = UPLOADS_DIR / file_id / "original.pptx"
                if candidate.exists():
                    pptx_path = candidate
        except Exception:
            pass

    async def generate():
        yield _sse({"status": "start", "total": total, "filename": filename})

        for idx, img_path in enumerate(slide_files, start=1):
            yield _sse({"status": "converting", "page": idx, "total": total})
            try:
                # PPTX 입력 시 slide_index(0-based) 전달 → python-pptx 메타데이터 보강
                md_text = await convert_slide_to_markdown(
                    img_path,
                    pptx_path=pptx_path,
                    slide_index=idx - 1,
                )
            except Exception as e:
                logger.exception("슬라이드 %d Markdown 변환 실패", idx)
                yield _sse({"status": "error", "page": idx, "message": str(e)})
                md_text = f"> ⚠️ 변환 실패: {e}"

            # 결과를 노트 JSON의 slide_markdown 필드에 저장 (ai_summary와 별도)
            note_path = notes_dir / f"slide_{idx:02d}.json"
            if note_path.exists():
                note = json.loads(note_path.read_text(encoding="utf-8"))
            else:
                note = {"text": "", "annotations": {}, "ai_summary": "", "updated_at": None}
            note["slide_markdown"] = md_text
            note_path.write_text(json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8")

            yield _sse({"status": "done", "page": idx, "total": total})

            # 마지막 슬라이드가 아니면 Gemini 무료 티어 RPM 제한 대기
            if idx < total:
                await asyncio.sleep(GEMINI_DELAY)

        yield _sse({"status": "complete", "total": total})

    return StreamingResponse(generate(), media_type="text/event-stream")
