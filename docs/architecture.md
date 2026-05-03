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

## PDF 내보내기 플로우 (exporter.py)

```
[export_to_pdf 호출]
      │
      ├─ .pdf 원본 ──▶ 직접 복사 (텍스트/링크 레이어 완전 보존)
      │
      └─ .pptx 원본 ─▶ searchable PDF 생성
                              │
                  ┌───────────▼───────────┐
                  │ 1. PPTX 폰트 목록 수집  │
                  │   _get_pptx_font_names │
                  └───────────┬───────────┘
                              │
                  ┌───────────▼────────────────────────────┐
                  │ 2. 폰트 레지스트리 구축 (_build_font_registry) │
                  │   ① 기등록 폰트 재사용                   │
                  │   ② 시스템 폰트 탐색 (OS별 자동 스캔)    │
                  │   ③ Google Fonts GitHub 자동 다운로드   │
                  │      → ~/.slidenote/fonts/ 캐시         │
                  └───────────┬────────────────────────────┘
                              │
                  ┌───────────▼───────────────────────────┐
                  │ 3. reportlab Canvas 렌더링             │
                  │   - 배경: 슬라이드 PNG                 │
                  │   - Invisible text overlay            │
                  │     * shape별 원본 폰트 (레지스트리 조회) │
                  │     * 미등록 폰트 → MalgunGothic 폴백  │
                  │     * textRenderMode=3 (검색·복사 가능) │
                  └───────────────────────────────────────┘
```

### 지원 자동 다운로드 폰트 목록 (Google Fonts)

| 한글 이름 | 등록명 | 분류 |
|---|---|---|
| 나눔고딕 | NanumGothic | 고딕 |
| 나눔명조 | NanumMyeongjo | 명조 |
| 나눔바른고딕 | NanumBarunGothic | 고딕 |
| 나눔손글씨붓 | NanumBrushScript | 손글씨 |
| 나눔손글씨펜 | NanumPenScript | 손글씨 |
| Do Hyeon | DoHyeon | 고딕 |
| Jua | Jua | 고딕 |
| Black Han Sans | BlackHanSans | 장체 |
| Gowun Batang | GowunBatang | 명조 |
| Gowun Dodum | GowunDodum | 돋움 |
| IBM Plex Sans KR | IBMPlexSansKR | 고딕 |
| Song Myung | SongMyung | 명조 |
| Yeon Sung | YeonSung | 손글씨 |
| + 5종 추가 | (Hi Melody, Gugi 등) | 기타 |

시스템 폰트 (Malgun Gothic, Batang, Gulim 등)는 우선 탐색하므로 별도 다운로드 불필요.
