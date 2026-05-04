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

### PNG 변환 (슬라이드 뷰어용)

```
[사용자 업로드]
      │
      ├─ .pptx ─▶ [Windows]              win32com subprocess → PNG × N장
      │            [Linux + GOTENBERG_URL] Gotenberg → PDF → PyMuPDF → PNG
      │            [Linux fallback]        LibreOffice headless → PDF → PNG
      │                              │
      └─ .pdf ──▶ PyMuPDF (fitz) → PNG × N장 (DPI=150)
                                     │
                                     ▼
                              uploads/{id}/slides/
                              page_01.png ~ page_NN.png
```

### 고품질 PDF 변환 (벡터·폰트·링크 보존)

```
[고품질 PDF 요청] GET /api/export/{id}/original-pdf/convert  (SSE)
      │
      ├─ 원본이 .pdf ─▶ original.pdf 직접 사용 (즉시 done)
      │
      └─ 원본이 .pptx
            │
            ├─ [Windows]  win32com subprocess: prs.SaveAs(path, 32)  ← ppSaveAsPDF=32
            ├─ [Gotenberg] httpx POST → PDF bytes 직접 저장
            └─ [LibreOffice] libreoffice --headless --convert-to pdf
                        │
                        ▼
               uploads/{id}/original_hq.pdf  (캐싱 — 재요청 시 재변환 생략)
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

---

## 배포 아키텍처 — Cloudflare Tunnel (자택 Windows PC)

> win32com 100% 품질을 클라우드 비용 없이 인터넷에 노출하는 방식

```
[사용자 브라우저]  ──HTTPS──▶  [Cloudflare Edge]
                                       │
                              암호화 영구 터널
                              (cloudflared daemon)
                                       │
                                       ▼
                          [내 Windows PC :80 (nginx)]
                          ┌────────────────────────────┐
                          │  /            React 정적    │
                          │  /api/*   ──▶ FastAPI :8000 │
                          │  /uploads/*  ──▶ 정적 파일  │
                          └────────────┬───────────────┘
                                       │
                              [FastAPI uvicorn :8000]
                                       │
                          ┌────────────▼───────────────┐
                          │  win32com subprocess       │
                          │  PowerPoint.exe            │
                          │  → 100% 품질 PDF/PNG 변환  │
                          └────────────────────────────┘
```

### 요청 흐름

```
브라우저 POST /api/files/upload
  → Cloudflare Edge (TLS 종료)
  → cloudflared 터널 (암호화)
  → nginx :80 /api/* 프록시
  → FastAPI :8000
  → asyncio.Queue (변환 작업 큐)
  → win32com subprocess (PowerPoint.exe)
  → PNG 생성 → uploads/{id}/slides/
  → SSE 진행률 스트림으로 브라우저에 실시간 전달
```

### 개선된 PNG 캐싱 구조 (Cloudflare R2 연동 시)

```
[변환 완료 PNG]
      │
      ├──▶ 로컬 uploads/{id}/slides/ (즉시 서빙)
      │
      └──▶ Cloudflare R2 업로드 (비동기, 백그라운드)
                  │
                  ▼
           Cloudflare CDN 캐싱
                  │
           PC가 꺼져도 이미 변환된 슬라이드는 계속 서빙 가능
```

### 컴포넌트별 역할

| 컴포넌트 | 역할 |
|---------|------|
| `cloudflared` | PC↔Cloudflare 영구 터널 유지 (Windows 서비스) |
| `nginx` | 정적 파일 서빙 + `/api/*` 리버스 프록시 |
| `FastAPI (uvicorn)` | REST API + SSE 스트리밍 |
| `win32com subprocess` | PPTX → PDF/PNG 100% 품질 변환 |
| `asyncio.Queue` | 동시 변환 요청 순차 처리 (PowerPoint 단일 인스턴스 보호) |
| `Cloudflare Access` | 이메일/도메인 기반 접근 제어 (대시보드 설정만으로) |
