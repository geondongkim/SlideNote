"""슬라이드별 오디오 업로드/다운로드"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter()
UPLOADS_DIR = Path("uploads")
ALLOWED_AUDIO = {".webm", ".mp4", ".ogg", ".wav"}
MAX_AUDIO_MB = 100


def _safe_id(file_id: str) -> str:
    if len(file_id) != 32 or not all(c in "0123456789abcdef" for c in file_id):
        raise HTTPException(400, "잘못된 file_id")
    return file_id


class TimestampsPayload(BaseModel):
    audio_timestamps: dict[str, float] = {}


@router.post("/{file_id}/{page}")
async def upload_audio(file_id: str, page: int, audio: UploadFile):
    """WebM 오디오 업로드 → uploads/{file_id}/audio/slide_{page:02d}.webm 저장"""
    fid = _safe_id(file_id)
    if page < 1:
        raise HTTPException(400, "page는 1 이상")

    suffix = Path(audio.filename or "a.webm").suffix.lower()
    if suffix not in ALLOWED_AUDIO:
        raise HTTPException(415, f"지원하지 않는 오디오 형식: {suffix}")

    audio_dir = UPLOADS_DIR / fid / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    out_path = audio_dir / f"slide_{page:02d}{suffix}"

    data = await audio.read()
    if len(data) > MAX_AUDIO_MB * 1024 * 1024:
        raise HTTPException(413, f"오디오 파일이 {MAX_AUDIO_MB}MB를 초과합니다")
    out_path.write_bytes(data)

    # note 파일에 audio_url 업데이트
    note_path = UPLOADS_DIR / fid / "notes" / f"slide_{page:02d}.json"
    if note_path.exists():
        note = json.loads(note_path.read_text(encoding="utf-8"))
    else:
        note = {"text": "", "annotations": {}, "ai_summary": "", "updated_at": None}
    note["audio_url"] = f"/api/audio/{fid}/{page}/file"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"fileId": fid, "page": page, "audioUrl": note["audio_url"]}


@router.put("/{file_id}/{page}/timestamps")
def save_timestamps(file_id: str, page: int, payload: TimestampsPayload):
    """주석 ID → 오디오 초 단위 매핑 저장"""
    fid = _safe_id(file_id)
    if page < 1:
        raise HTTPException(400, "page는 1 이상")
    note_path = UPLOADS_DIR / fid / "notes" / f"slide_{page:02d}.json"
    if note_path.exists():
        note = json.loads(note_path.read_text(encoding="utf-8"))
    else:
        note = {"text": "", "annotations": {}, "ai_summary": "", "updated_at": None}
    note["audio_timestamps"] = payload.audio_timestamps
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"saved": True, "count": len(payload.audio_timestamps)}


@router.get("/{file_id}/{page}/file")
def get_audio(file_id: str, page: int):
    """오디오 파일 스트리밍 반환"""
    fid = _safe_id(file_id)
    audio_dir = UPLOADS_DIR / fid / "audio"
    for ext in ALLOWED_AUDIO:
        candidate = audio_dir / f"slide_{page:02d}{ext}"
        if candidate.exists():
            return FileResponse(str(candidate), media_type="audio/webm")
    raise HTTPException(404, f"슬라이드 {page}의 오디오가 없습니다")
