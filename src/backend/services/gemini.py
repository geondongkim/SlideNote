"""
Gemini Vision 슬라이드 요약 서비스

검증된 패턴 (gen_vision_improved.py 기반):
- PRIMARY: gemini-2.5-flash-image → inline_data 감지 시 FALLBACK: gemini-2.5-flash
- DELAY: 7.0초 (무료 티어 ~10 RPM 제한)
- 온도 0.1, max_tokens 8192
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

GEMINI_PRIMARY = "gemini-2.5-flash-image"
GEMINI_FALLBACK = "gemini-2.5-flash"
GEMINI_DELAY = 7.0

SLIDE_PROMPT = """다음 슬라이드 이미지를 보고 **발표자 노트 형식**으로 한국어 요약을 작성해 주세요.

## 작성 형식

### 핵심 요약 (3줄 이내)
슬라이드의 핵심 메시지 3줄

### 주요 내용
- 슬라이드에 담긴 주요 내용을 불릿으로 정리
- 다이어그램, 흐름도, 표가 있으면 설명 포함

### 발표 포인트
발표자가 강조해야 할 한 가지 포인트

---
Markdown 형식으로만 출력하세요. 마크다운 코드블록(```) 래퍼 없이 바로 내용만 출력하세요."""


def _get_client():
    """google-genai 클라이언트 초기화. API 키는 환경변수 GOOGLE_API_KEY."""
    from google import genai

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.")
    return genai.Client(api_key=api_key)


def _call_model(client, gtypes, model: str, img_path: Path) -> tuple[str, str | None]:
    """단일 모델 호출. 반환: (text, error_type|None)"""
    from PIL import Image

    try:
        img = Image.open(str(img_path))
        resp = client.models.generate_content(
            model=model,
            contents=[img, SLIDE_PROMPT],
            config=gtypes.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=8192,
            ),
        )
        text = resp.text or ""
        if not text.strip():
            return "", "inline_data"
        return text, None
    except Exception as e:
        err = str(e)
        if "inline_data" in err.lower() or "non-text" in err.lower():
            return "", "inline_data"
        return "", err


async def summarize_slide(img_path: Path) -> str:
    """
    슬라이드 PNG → 한국어 발표자 노트 요약 (Markdown).
    PRIMARY 실패 시 FALLBACK, GEMINI_DELAY 대기.
    """
    from google.genai import types as gtypes

    def _run() -> str:
        client = _get_client()
        text, err = _call_model(client, gtypes, GEMINI_PRIMARY, img_path)
        if err == "inline_data":
            logger.info("inline_data 감지 → %s 폴백", GEMINI_FALLBACK)
            import time
            time.sleep(GEMINI_DELAY)
            text, err = _call_model(client, gtypes, GEMINI_FALLBACK, img_path)
        if err:
            raise RuntimeError(f"Gemini 오류: {err}")
        return text

    # 동기 블로킹 함수를 이벤트 루프에서 실행
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)
