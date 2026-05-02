# SlideNote 시스템 아키텍처

## 전체 구조

```
┌─────────────────────────────────────────────────────────┐
│                      브라우저 (React)                     │
│                                                         │
│  ┌──────────┐  ┌──────────────────────┐  ┌──────────┐  │
│  │SlideList │  │   SlideViewer        │  │NoteEditor│  │
│  │(좌측)    │  │  <img> + Fabric.js   │  │(우측)    │  │
│  │thumbnail │  │  Canvas (주석 오버레이)│  │텍스트    │  │
│  │목록      │  │                      │  │AI 요약   │  │
│  └──────────┘  └──────────────────────┘  └──────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │ REST API (HTTP)
┌───────────────────────▼─────────────────────────────────┐
│                  FastAPI 백엔드 (Python)                   │
│                                                         │
│  /api/files/*        /api/notes/*       /api/ai/*       │
│       │                    │                 │          │
│  converter.py          notes CRUD       gemini.py       │
│  (PyMuPDF/win32com)   (JSON 파일)      (Vision API)     │
└───────────────────────┬─────────────────────────────────┘
                        │
              ┌─────────▼──────────┐
              │  uploads/{file_id}/ │
              │  ├─ original.pptx   │
              │  ├─ slides/*.png    │
              │  ├─ notes/*.json    │
              │  └─ audio/*.webm    │
              └────────────────────┘
```

## 파일 변환 플로우

```
[사용자 업로드]
      │
      ├─ .pptx ─▶ [Windows] win32com PowerPoint COM
      │            [Linux]   LibreOffice headless → PDF
      │                              │
      │                              ▼
      └─ .pdf ──▶ PyMuPDF (fitz) → PNG × N장 (DPI=150)
                                     │
                                     ▼
                              uploads/{id}/slides/
                              page_01.png ~ page_NN.png
```

## 주석 저장 플로우

```
[사용자 필기]
      │
      ▼
Fabric.js Canvas.toJSON()
      │
      ▼ PUT /api/notes/{file_id}/{slide_n}/annotations
      │
      ▼
uploads/{id}/notes/slide_NN.json
{
  "text": "노트 텍스트",
  "annotations": { fabric.js JSON },
  "ai_summary": "AI 요약",
  "audio_timestamps": { ... }
}
```

## AI 요약 플로우

```
[슬라이드 PNG] + [python-pptx 메타데이터]
      │
      ▼
Gemini Vision API
├─ Primary:  gemini-2.5-flash-image
└─ Fallback: gemini-2.5-flash (inline_data 감지 시)
      │
      ▼
구조화 Markdown (헤더/테이블/Mermaid)
      │
      ▼
NoteEditor "AI 요약" 영역에 표시
```
