# SlideNote 구현 계획

> PPTX / PDF 혼용 슬라이드 노트 앱 — 단계별 개발 로드맵

---

## 목표 & 범위

### 해결하는 문제
- 발표자: 슬라이드와 발표 대본을 한 화면에서 관리
- 학생: PDF 강의자료 위에 직접 필기·주석 추가
- 청중: 슬라이드 캡처 + 즉시 메모 작성

### 핵심 가치
1. **포맷 무관**: PPTX든 PDF든 동일한 UX 제공
2. **주석 비파괴**: 원본 파일을 수정하지 않고 레이어로 관리
3. **AI 보조**: Gemini Vision으로 슬라이드 내용 자동 요약

---

## 아키텍처 결정

### 왜 Python 백엔드인가?

기존 PPTX/PDF → Markdown 변환 파이프라인 개발에서 검증된 라이브러리를 그대로 활용합니다:

| 검증된 라이브러리 | 역할 | 검증 근거 |
|----------------|------|----------|
| `PyMuPDF` | PDF → PNG | 44페이지 변환 완료, DPI 150 최적 |
| `python-pptx` | PPTX 메타 추출 | 22슬라이드 구조 분석 완료 |
| `pywin32` | PPTX → PNG (Windows) | 1920px 고품질 출력 검증 (Python subprocess 방식으로 COM STA 충돌 해결) |
| `google-genai` | Gemini Vision AI | 3종 모델 비교 완료 |

### 렌더링 전략

```
[업로드]
  PPTX ──▶ pywin32/LibreOffice ──▶ PNG (서버)
  PDF  ──▶ PyMuPDF              ──▶ PNG (서버)
                                      │
                              [FastAPI 정적 제공]
                                      │
[브라우저]                            ▼
  <img src="/slides/page_01.png"> + Fabric.js Canvas (주석 오버레이)
```

**PDF.js를 쓰지 않는 이유**: 브라우저 내 PDF 렌더링은 폰트/레이아웃 재현 불안정. 서버에서 PNG로 변환 후 제공하는 방식이 더 일관성 있음 (파이프라인 경험에서 검증).

---

## Phase 1: MVP (2~3주)

> **진행 상태 (2026-05-04)**: 1주차 백엔드/프론트 골격 구현 완료
> - ✅ `services/converter.py` (pdf_to_pngs / pptx_to_pngs Windows·LibreOffice 분기)
>   - **PPTX Windows COM 방식 확정**: `_win32_pptx_to_pngs` → Python subprocess (`sys.executable + 임시 .py`)
>   - uvicorn 이벤트루프 스레드에서 `Visible=True` COM 오류(0x80048240) → 부모 window station 상속 subprocess로 해결
>   - 성능 측정 완료 (2026-05-03):
>     | 항목 | PDF | PPTX |
>     |------|-----|------|
>     | 파일 크기 | 1.41 MB | 20.77 MB |
>     | 페이지/슬라이드 | 22 | 22 |
>     | 업로드+변환 시간 | 2.15–4.06초 | 16.14초 |
>     | MB/s | 0.35–0.66 | 1.29 |
>     | 초/페이지 | 0.10–0.18 | 0.73 |
>     | UX 동일성 | ✅ | ✅ |
> - ✅ `routers/files.py` (`POST /api/files/upload`, `GET /{id}/slides`, 50MB 제한, file_id sanitize)
> - ✅ `routers/notes.py` (`GET/PUT /api/notes/{file_id}/{page}` 파일 기반 JSON)
> - ✅ `services/exporter.py` — **Searchable PDF 내보내기** (2026-05-04):
>   - PDF 원본: `original.pdf` 직접 복사 → 텍스트/검색/하이퍼링크 레이어 완전 유지
>   - PPTX 원본: reportlab + python-pptx invisible text overlay (render_mode=3)
>     * EMU → px 좌표 변환으로 텍스트 위치 근사 매핑
>     * 맑은고딕(malgun.ttf) 폰트 등록으로 한글 검색 지원
>   - 다운로드 파일명: `slidenote_xxx.pdf` → 원본 파일명.pdf
>   - 유인물(handout) 인터페이스: `file_dir` 단일 인수로 통일
> - ✅ 프론트 `lib/api.js`, `store/useAppStore.js`, `components/UploadButton.jsx`, `SlideList.jsx`
> - ✅ App.jsx 통합 + 노트 자동 저장 (500ms 디바운스)
> - ⏭️ 다음: Fabric.js Canvas 주석, 단위 테스트

### 1-1. 백엔드 기반 (`src/backend/`)

#### `services/converter.py`

```python
# PPTX → PNG (Windows: win32com, 그 외: LibreOffice)
def pptx_to_pngs(pptx_path: Path, out_dir: Path, dpi: int = 150) -> list[Path]:
    """
    검증된 전략 (gen_vision_improved.py 참조):
    - Windows: PowerPoint COM automation (PNG_WIDTH=1920)
    - Linux/Mac: LibreOffice --headless --convert-to pdf, 이후 PyMuPDF
    - 반환: [page_01.png, page_02.png, ...]
    """
    import platform
    if platform.system() == "Windows":
        return _win32_pptx_to_pngs(pptx_path, out_dir)
    else:
        return _libreoffice_pptx_to_pngs(pptx_path, out_dir, dpi)

def pdf_to_pngs(pdf_path: Path, out_dir: Path, dpi: int = 150) -> list[Path]:
    """
    PyMuPDF 기반 (검증됨):
    - DPI 150: 속도/품질 최적 균형 (300은 2~3배 느림)
    - 출력: page_01.png ~ page_NN.png
    """
    import fitz
    doc = fitz.open(str(pdf_path))
    matrix = fitz.Matrix(dpi/72, dpi/72)
    results = []
    for i, page in enumerate(doc):
        png_path = out_dir / f"page_{i+1:02d}.png"
        pix = page.get_pixmap(matrix=matrix)
        pix.save(str(png_path))
        results.append(png_path)
    return results
```

#### `services/gemini.py`

```python
# 검증된 Gemini Vision 호출 패턴 (gen_vision_improved.py 참조)
GEMINI_PRIMARY   = "gemini-2.5-flash-image"
GEMINI_FALLBACK  = "gemini-2.5-flash"
GEMINI_DELAY_SEC = 7.0  # 무료 티어 rate limit (~10 RPM)

def call_gemini_smart(client, img_path: Path, context: str = "") -> tuple[str, str]:
    """
    inline_data 자동 감지 → 폴백 전략 (검증됨):
    - flash-image 응답에 inline_data 포함 시 → flash로 재시도
    - 이유: flash-image는 디자인 요소 많은 슬라이드에서 이미지 재생성 시도
    반환: (markdown_text, model_used)
    """
    ...
```

#### `routers/files.py`

```python
@router.post("/upload")
async def upload_file(file: UploadFile):
    """
    1. 파일 저장 (uploads/{file_id}/)
    2. 확장자 감지: .pptx → pptx_to_pngs(), .pdf → pdf_to_pngs()
    3. 슬라이드 수, 썸네일 URL 목록 반환
    4. PPTX의 경우 python-pptx로 메타데이터도 추출하여 저장
    """
```

#### `routers/notes.py`

```python
# 노트 저장 형식 (파일 기반, Phase 1)
# uploads/{file_id}/notes/slide_{n:02d}.json
#
# pdfanno(paperai/pdfanno)의 스키마를 참고하여 정규화된 좌표 방식 채택
# - id: UUID (pdfanno 방식)
# - page: 1-based 페이지 번호 (pdfanno 방식과 동일)
# - type: 'rect' | 'span' | 'path' | 'text' (pdfanno 타입 체계 확장)
# - position: [x, y, width, height]  — 뷰포트 상대 비율(0~1)로 정규화
#   → 해상도 변경에도 주석 위치 유지 (pdfanno의 convertFromExportY 아이디어)
#
# {
#   "version": "1.0",
#   "fileId": "...",
#   "page": 1,
#   "text": "발표 대본...",
#   "annotations": {
#     "fabricVersion": "6.6.1",
#     "objects": [                    # Fabric.js toJSON() 결과
#       {
#         "id": "<uuid>",            # 추가 필드
#         "type": "path",
#         "_pageRatio": [1.0, 0.75], # 저장 당시 이미지 비율 (리사이즈 복원용)
#         "_timestamp": 32.5,        # 오디오 타임스탬프 (Phase 2)
#         ...                        # Fabric.js 표준 필드
#       }
#     ]
#   },
#   "ai_summary": "...",
#   "updated_at": "2026-05-03T..."
# }
```

### 1-2. 프론트엔드 기반 (`src/frontend/`)

#### 3단 레이아웃 구조

```jsx
// App.jsx
<div className="flex h-screen">
  {/* 좌측: 슬라이드 목록 (200px) */}
  <SlideList slides={slides} current={current} onSelect={setCurrent} />
  
  {/* 중앙: 뷰어 + 주석 Canvas (flex-1) */}
  <SlideViewer slideUrl={slideUrl} annotations={annotations} />
  
  {/* 우측: 노트 에디터 (320px) */}
  <NoteEditor note={note} onSave={saveNote} onAI={requestAI} />
</div>
```

#### `usePdfRenderer.js` (서버 PNG 방식)

```js
// PDF.js 대신 서버 변환 PNG 사용 → 더 일관된 렌더링
export function useSlideImage(fileId, slideNum) {
  return `/api/files/${fileId}/slide/${slideNum}`;
}
```

#### `useAnnotation.js` (Fabric.js + drauu 패턴 참고)

```js
// Slidev(slidevjs/slidev)의 useDrawings.ts + pympress scribble.py 패턴 적용
export function useAnnotation(canvasRef) {
  // ── 도구 상태 (Slidev brushColors 팔레트 참고) ──
  const BRUSH_COLORS = ['#ff595e','#ffca3a','#8ac926','#1982c4','#6a4c93','#ffffff','#000000'];
  const [tool, setTool]   = useState('select'); // pen | highlight | rect | text | arrow
  const [color, setColor] = useState(BRUSH_COLORS[0]);
  const [width, setWidth] = useState(2);

  // ── Undo/Redo 스택 (pympress scribble_list / scribble_redo_list 패턴) ──
  // Fabric.js는 내장 history 없음 → 스냅샷 스택으로 직접 구현
  const historyRef   = useRef([]);  // [{objects: [...], timestamp}]
  const redoStackRef = useRef([]);

  const saveSnapshot = () => {
    historyRef.current.push(canvas.toJSON(['id','_timestamp','_pageRatio']));
    redoStackRef.current = [];      // redo 스택 클리어 (pympress scribble_drawing 패턴)
    if (historyRef.current.length > 50) historyRef.current.shift(); // max 50
  };

  const undo = () => {
    if (historyRef.current.length < 2) return;
    redoStackRef.current.push(historyRef.current.pop());
    canvas.loadFromJSON(historyRef.current.at(-1), () => canvas.renderAll());
  };

  const redo = () => {
    if (!redoStackRef.current.length) return;
    const next = redoStackRef.current.pop();
    historyRef.current.push(next);
    canvas.loadFromJSON(next, () => canvas.renderAll());
  };

  const enablePen = () => {
    canvas.isDrawingMode = true;
    canvas.freeDrawingBrush.color = color;
    canvas.freeDrawingBrush.width = width;
  };

  const enableHighlight = () => {
    canvas.isDrawingMode = true;
    canvas.freeDrawingBrush.color = color.replace(')', ',0.4)').replace('rgb','rgba');
    canvas.freeDrawingBrush.width = 20;
  };

  // Slidev의 per-slide drawing state 저장 방식 참고:
  // BroadcastChannel로 동일 파일 열린 다른 탭과 실시간 동기화 (Phase 3)
  const saveAnnotations = async () => {
    const json = canvas.toJSON(['id','_timestamp','_pageRatio']);
    await api.put(`/notes/${fileId}/${slideNum}/annotations`, json);
  };

  return { tool, setTool, color, setColor, width, setWidth,
           enablePen, enableHighlight, undo, redo, saveAnnotations };
}
```

> **참고**: Slidev는 `drauu` 라이브러리(SVG 기반)를 사용하지만, SlideNote는 이미지 위 픽셀 드로잉이 목적이므로 Canvas 기반 Fabric.js 유지. Undo 스택 패턴만 참고.

---

## Phase 2: 차별화 기능 (4~6주)

> **진행 상태**: ✅ 2-1 완료 (commit `bedfdde`, 2025-05)

### 2-1. AI 자동 요약 ✅

**구현 완료**:
- `services/gemini.py`: `summarize_slide(img_path)` — PRIMARY `gemini-2.5-flash-image`, FALLBACK `gemini-2.5-flash`, DELAY 7.0s
- `routers/ai.py`: `POST /api/ai/{file_id}/summarize` — 노트 파일 ai_summary 필드 업데이트
- `App.jsx`: "AI 요약 생성" 버튼 + 결과 우측 패널 표시, 방향키(←/→) 네비게이션, 헤더 UploadButton
- `.env.example`: `GOOGLE_API_KEY` 발급 안내

**원래 설계** (참고):
```
슬라이드 PNG + python-pptx 메타데이터 → Gemini Vision
                                            ↓
                                    한국어 요약 노트 (Markdown)
                                            ↓
                                    NoteEditor 우측에 자동 삽입
```

**핵심 프롬프트 전략** (gen_vision_improved.py의 SLIDE_PROMPT 응용):
- Mermaid 다이어그램 감지 → `graph TD`, `sequenceDiagram` 변환
- 테이블 → HTML table (colspan/rowspan 포함)
- 핵심 인사이트 3줄 요약 추가

### 2-2. 오디오 녹음 연동 ✅

**구현 완료** (commit `ed295ee`):
- `useAudioRecorder.js`: MediaRecorder WebM, `stamp(annotationId)` → elapsed 반환, `playFrom`, `loadAudio`
- `AudioPanel.jsx`: 녹음 시작/중지, 재생, 타임스탬프 목록 UI
- `routers/audio.py`: `POST /api/audio/{file_id}/{page}` (WebM 업로드), `PUT .../timestamps`, `GET .../file`
- `notes.py` Note 모델: `audio_url`, `audio_timestamps` 필드 추가
- `useAnnotation.js`: `stampRef` prop 연동 — `object:added` 시 녹음 중이면 elapsed 자동 기록 (`_timestamp`)
- `App.jsx`: `AudioPanel`, `stampRef` 연결

**원래 설계** (참고):
```
[녹음 시작] → MediaRecorder API
     │
     ▼
[필기 1 timestamp: 00:32]
[필기 2 timestamp: 01:15]  → annotation.json에 timestamp 저장
     │
     ▼
[필기 클릭] → audio.currentTime = timestamp → 재생
```

저장 구조:
```json
{
  "annotations": [...],
  "audio_url": "/uploads/{file_id}/audio/slide_{n}.webm",
  "audio_timestamps": {
    "annotation_id_1": 32.5,
    "annotation_id_2": 75.1
  }
}
```

### 2-3. 유인물 레이아웃 (PowerPoint '유인물 마스터' 대응) ✅

**구현 완료 (2026-05-03)**

**백엔드**
- `services/exporter.py` — `export_handout(slides_dir, notes_dir, out_path, layout)` 추가
  - `1up`: A4 1장에 슬라이드 1개 + 노트 8줄 영역
  - `2up`: A4 1장에 슬라이드 2개 + 각 노트 4줄 영역
  - `4up`: A4 1장에 슬라이드 4개 2×2 그리드 (요약 인쇄용, 슬라이드 번호 표시)
  - Pillow `ImageDraw`로 줄 그리기 + 한글 폰트(맑은 고딕) 지원, 없으면 기본 폰트 fallback
  - 노트 텍스트 자동 줄 바꿈 (`textwrap.wrap`)
- `routers/export.py` — `GET /api/export/{file_id}/handout?layout=1up|2up|4up` 추가
  - `_validate_id()` 헬퍼로 중복 검증 통합

**프론트엔드**
- `lib/api.js` — `downloadHandout(fileId, layout)` 추가 (a 태그 클릭 방식)
- `App.jsx` — 우측 패널 하단에 유인물 버튼 그룹 추가 (`1up` / `2up` / `4up`)

```python
# 실제 구현 시그니처
def export_handout(
    slides_dir: Path,
    notes_dir: Path,
    out_path: Path,
    layout: Literal["1up", "2up", "4up"] = "2up",
) -> Path:
```

### 2-4. 화이트보드 모드 ✅

**구현 완료 (2026-05-03)**

**백엔드**
- `routers/files.py` — `POST /api/files/{file_id}/whiteboard` 추가
  - 기존 슬라이드 크기 참조(없으면 1920×1080) → 흰 PNG 생성 → `page_NN.png` 저장
  - `metadata.json pageCount` 자동 증가
  - 반환: `{ page, url, pageCount }`

**프론트엔드**
- `store/useAppStore.js` — `setPageCount(pageCount)` 액션 추가
- `lib/api.js` — `insertWhiteboardPage(fileId)` 추가
- `components/SlideList.jsx`
  - 하단에 **"+ 빈 페이지 삽입"** 점선 버튼 추가
  - 삽입 후 해당 페이지로 자동 이동, `onWhiteboardInserted` 콜백 호출
- `components/SlideViewer.jsx`
  - `whiteboardPages: Set<number>` prop 수신
  - 화이트보드 페이지면 황색 안내 배너 표시: "✏ 화이트보드 페이지 — 자유롭게 드로잉하세요"
- `App.jsx`
  - `whiteboardPages` 상태 관리 (Set)
  - `SlideList`에 `onWhiteboardInserted` 전달, `SlideViewer`에 `whiteboardPages` 전달

**내보내기**: 화이트보드 페이지도 `page_NN.png`로 저장되므로 기존 `export_to_pdf` / `export_handout` 자동 포함

---

## Phase 3: 동기화 & 배포 (8주+)

> **진행 상태 (2026-05-08)**: Firebase 전체 동기화 구현 완료

### Firebase 연동 ✅ (구현 완료)

```
노트/주석 → Firestore (실시간 sync)                  ✅
파일      → Firebase Storage (useStorage.js)         ✅ (Console에서 Storage 활성화 필요)
인증      → Firebase Auth (Google)                   ✅ (Console에서 공급자 활성화 필요)
세션      → Firestore sessions/{uid}/files/{fileId}  ✅
파일목록  → GET /api/files + RecentFiles 컴포넌트     ✅
```

**구현 완료**:
- Firebase 프로젝트: `slidenote-2026` (Tokyo 리전: `asia-northeast1`)
- 프로젝트 파일: `firebase.json`, `.firebaserc`, `firestore.rules`, `firestore.indexes.json`
- `src/frontend/src/lib/firebase.js` — `initializeApp`, `getFirestore`, `getAuth`
- `src/frontend/src/hooks/useAuth.js` — Google 팝업 로그인, `onAuthStateChanged`
- `src/frontend/src/hooks/useFirestore.js` — Firestore `setDoc` + `onSnapshot` 실시간 동기화
  - 문서 ID: `{uid}_{fileId}_{page}` 형태로 사용자·파일·페이지별 격리
- `App.jsx` 업데이트 — 헤더 Google 로그인 버튼, 노트 패널 `☁ 동기화` 상태 표시

**활성화 필요** (Firebase Console 수동):
```
https://console.firebase.google.com/project/slidenote-2026/authentication/providers
→ Google 공급자 활성화
```

**Firestore 보안 규칙** (`firestore.rules`):
```
notes/{noteId}              → uid 일치하는 로그인 사용자만 읽기/쓰기
sessions/{uid}/files/{fid}  → uid 경로 일치하는 로그인 사용자만 읽기/쓰기
```

**Firebase Storage 보안 규칙** (`storage.rules`):
```
users/{uid}/** → uid 일치하는 로그인 사용자만 읽기/쓰기
```

**수동 활성화 필요** (Firebase Console):
```
https://console.firebase.google.com/project/slidenote-2026/authentication/providers
→ Google 공급자 활성화

https://console.firebase.google.com/project/slidenote-2026/storage
→ Firebase Storage 활성화 → Get Started
→ 이후: firebase deploy --only storage
```

### Gotenberg 기반 PPTX 변환 서버 (Linux/Mac 배포 시) ✅

> 참고: `gotenberg/gotenberg` — LibreOffice + Chromium 기반 문서 변환 API

**구현 완료 (Phase 3)**:
- `services/converter.py` — `GOTENBERG_URL` 환경변수 감지 → `_gotenberg_pptx_to_pngs()` 호출
  - `httpx.Client(timeout=300)` 동기 POST → PDF bytes → PyMuPDF PNG 변환
  - 우선순위: Windows → win32com, Linux `GOTENBERG_URL` 설정 시 → Gotenberg, 없으면 → LibreOffice
- `requirements.txt` — `httpx==0.28.1` 추가
- `src/backend/Dockerfile` — python:3.13-slim + uvicorn
- `src/frontend/Dockerfile` — node:20-alpine 빌드 + nginx:1.27-alpine 서빙
- `src/frontend/nginx.conf` — `/api/`, `/uploads/` 프록시 + SSE 지원 + SPA fallback
- `docker-compose.yml` (루트) — backend + frontend + gotenberg 3-서비스 구성
- `src/backend/.dockerignore`, `src/frontend/.dockerignore` 추가

```bash
# Docker로 전체 스택 실행
docker compose up --build

# 서비스 접속
# 앱:     http://localhost
# API:    http://localhost/api
# 백엔드: http://localhost:8000 (직접)
```

> **주의**: Windows 로컬 개발 시는 win32com 사용. Linux 배포/Docker 환경에서만 Gotenberg 활성화.

### 모바일 앱 (React Native, Phase 3 확장)

> 참고: `thatkid02/react-native-pdf-viewer` — NitroModules 기반 네이티브 PDF 뷰어

```tsx
// NitroModules 방식: 네이티브 PDF 렌더링 (pdfjs보다 성능 우수)
import { PdfViewer } from 'react-native-pdf-viewer';

// 핵심 Props (PdfViewer.nitro.ts 참고)
<PdfViewer
  source="file:///path/to/slide.pdf"  // file://, http://, https://
  horizontal={true}                   // iOS: 가로 스크롤 (슬라이드 모드)
  enablePaging={true}                 // iOS: 페이지 단위 스크롤
  spacing={8}
  onLoadComplete={(e) => setPageCount(e.pageCount)}
  onPageChange={(e) => setCurrentPage(e.page)}
  onThumbnailGenerated={(e) => setThumb(e.uri)}
/>
// DocumentInfo: { pageCount, pageWidth, pageHeight, currentPage }  (0-indexed)
// Android: PDF 렌더링은 PDFRenderer API 사용
```

> Flutter 대안: `aliyoge/flutter_file_preview` — Android(TBS), iOS(WKWebView)
> PPT/PDF/Word/Excel 지원. 단, 커스텀 주석 레이어 추가 어려움 → React Native 권장.

---

## UX 개선 (v1.5) — 사이드바 과밀·탐색 불편 해소

> **진단**: 우측 w-80 사이드바에 7가지 기능이 세로로 쌓여 노트 영역 압박 + 스크롤 없이는
> 하단 버튼 접근 불가. 현재 파일명 맥락 없음, 전환 피드백 없음, 첫 사용 진입점 불명확.

### UX-1. 사이드바 탭 UI 분리 ★★★

**변경 파일**: `App.jsx`

**목적**: 우측 aside 320px 전체를 탭별로 독점 사용 → textarea 공간 3배 확보, 기능 목적 명확화

```
[노트] [내보내기] [오디오]  ← 탭 헤더 (항상 고정)
─────────────────────────
노트 탭:
  textarea (h-full)
  AI 요약 결과 (접힌 상태 기본)
  AI 요약 생성 버튼

내보내기 탭:
  PDF 내보내기
  유인물 1up / 2up / 4up
  노트 Markdown 내보내기
  ─ 구분선 ─
  슬라이드 Markdown 변환
    · 변환 중 프로그레스 바
    · Obsidian/Notion 최적화 안내

오디오 탭:
  AudioPanel (전체 높이 사용)
```

**구현 포인트**:
- `activeTab: 'note' | 'export' | 'audio'` — `useState('note')`
- 탭 버튼 className: 활성 `border-b-2 border-blue-500 text-white` / 비활성 `text-gray-400`
- 오디오 녹음 중(`recording === true`) + 비오디오 탭 → 오디오 탭 버튼에 `●` 빨간 dot 표시
- 탭 내용은 `{activeTab === 'note' && <...>}` 조건부 렌더링 (unmount 방지 필요 시 `hidden` class 토글)

### UX-2. 헤더 파일명 표시 ★★★

**변경 파일**: `store/useAppStore.js`, `App.jsx`, `components/RecentFiles.jsx`, `components/UploadButton.jsx`

**목적**: "SlideNote" + "7 / 22" 만 있는 헤더에 현재 파일명 추가 → 다중 파일 전환 시 맥락 제공

```jsx
// 헤더 변경 후
<span className="font-semibold text-white text-sm">SlideNote</span>
{filename && (
  <span className="text-gray-400 text-xs truncate max-w-[200px] ml-2" title={filename}>
    / {filename}
  </span>
)}
```

**스토어 변경**:
```js
// useAppStore.js
filename: '',
setFile: (fileId, pageCount, filename = '') => set({ fileId, pageCount, currentSlide: 1, filename }),
```

**연결 지점**:
- `RecentFiles.handleOpen(fileId, pageCount, filename)` → `setFile(fileId, pageCount, f.filename)`
- `UploadButton` onSuccess 콜백: `meta.filename` → `handleUploadSuccess(file, meta)` → `setFile(..., meta.filename)`

### UX-3. 슬라이드 전환 로딩 스켈레톤 ★★☆

**변경 파일**: `components/SlideViewer.jsx`

**목적**: 슬라이드 이미지 교체 시 순간 회색 배경 노출 → 스켈레톤으로 "로딩 중" 의도 표현

```jsx
// SlideViewer.jsx 핵심 변경
const [imgLoaded, setImgLoaded] = useState(false)

useEffect(() => {
  setImgLoaded(false)   // 슬라이드 변경 시마다 리셋
}, [fileId, currentSlide])

// 렌더
<div className="relative inline-block shadow-2xl">
  {!imgLoaded && (
    <div
      className="absolute inset-0 bg-gray-700 animate-pulse rounded z-10"
      style={{ aspectRatio: '16/9', minWidth: 400 }}
    />
  )}
  <img
    ref={imgRef}
    src={slideUrl}
    onLoad={() => { setImgLoaded(true); onImageLoad() }}
    className={`block max-h-[calc(100vh-9rem)] max-w-full transition-opacity duration-150 ${imgLoaded ? 'opacity-100' : 'opacity-0'}`}
  />
  <canvas ... />
</div>
```

**주의**: `onImageLoad`(annotation resize 트리거)는 `imgLoaded = true` 와 동시에 호출해야 canvas 크기 동기화됨.

### UX-4. 오디오 패널 접기/펼치기 ★★☆

**변경 파일**: `components/AudioPanel.jsx`

**목적**: 녹음 미사용 시 패널이 노트 공간 압박 → 기본 접힘, 클릭 시 펼침

```jsx
// AudioPanel.jsx 변경
const [collapsed, setCollapsed] = useState(true)

return (
  <div className="mt-3 border border-gray-600 rounded">
    <button
      onClick={() => setCollapsed(c => !c)}
      className="w-full flex items-center justify-between px-2 py-1.5 text-[10px] text-orange-400 font-medium"
    >
      <span>오디오 녹음</span>
      <span>{collapsed ? '▶' : '▼'}</span>
    </button>
    {!collapsed && (
      <div className="px-2 pb-2">
        {/* 기존 녹음 컨트롤 내용 */}
      </div>
    )}
  </div>
)
```

**탭 분리(UX-1) 이후**: 오디오 탭 내에서도 동일하게 적용 (탭 전환 자체가 접기 역할을 하므로 중요도 낮아짐)

### UX-5. 초기 화면 업로드 CTA ★☆☆

**변경 파일**: `components/RecentFiles.jsx`

**목적**: 파일 없는 초기 화면에서 업로드 버튼이 헤더 우측에만 있어 첫 사용자가 놓침 → 중앙 CTA 추가

```jsx
// files.length === 0 일 때 빈 상태 UI
<div className="flex flex-col items-center justify-center h-full text-gray-400 gap-4">
  <p className="text-3xl">📂</p>
  <p className="text-sm">최근 열었던 파일이 없습니다</p>
  <label className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded cursor-pointer transition-colors">
    PPTX / PDF 업로드
    <input
      type="file"
      accept=".pptx,.pdf"
      className="hidden"
      onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
    />
  </label>
  <p className="text-xs text-gray-500">또는 상단 업로드 버튼 사용</p>
</div>
```

**연결**: `onUpload` prop을 `App.jsx`에서 `UploadButton`의 업로드 로직과 공유 (중복 구현 방지).
`uploadFile(file)` → `handleUploadSuccess(file, meta)` → `setFile` 순서 그대로 재사용.

### UX-6. Toolbar 단축키 툴팁 ★☆☆

**변경 파일**: `components/Toolbar.jsx`, `App.jsx`

**목적**: ←/→ 외 도구 단축키 존재 자체를 사용자가 모름 → `title` 속성 + 키 핸들러 등록

**Toolbar.jsx 변경**:
```js
const TOOLS = [
  { id: 'select',    label: '선택',   icon: '↖',  shortcut: 'V' },
  { id: 'pen',       label: '펜',     icon: '✏️',  shortcut: 'P' },
  { id: 'highlight', label: '형광펜', icon: '🖌',  shortcut: 'H' },
  { id: 'text',      label: '텍스트', icon: 'T',   shortcut: 'T' },
  { id: 'arrow',     label: '화살표', icon: '→',   shortcut: 'A' },
]

// 버튼 title 속성
title={`${t.label} (${t.shortcut})`}
```

**App.jsx 키 핸들러 확장** (기존 ←/→ 핸들러에 추가):
```js
const TOOL_SHORTCUTS = { v: 'select', p: 'pen', h: 'highlight', t: 'text', a: 'arrow' }
// handler 내부
const key = e.key.toLowerCase()
if (TOOL_SHORTCUTS[key] && !e.ctrlKey && !e.metaKey) {
  // setTool은 annotation에 있으므로 전역 이벤트로 dispatch 또는 annotation ref 경유
}
```

**구현 선택**: `useAnnotation`이 반환하는 `setTool`을 `App.jsx`에서 ref로 받거나, `CustomEvent`로 툴 변경 이벤트 발행.

---

## 파일 저장 구조

```
uploads/
└── {file_id}/          # UUID
    ├── original.pptx   # 원본 파일
    ├── slides/
    │   ├── page_01.png
    │   ├── page_02.png
    │   └── ...
    ├── metadata.json    # 총 슬라이드 수, 파일명, 변환 시각
    ├── notes/
    │   ├── slide_01.json  # {text, annotations, ai_summary, audio_timestamps}
    │   └── slide_02.json
    └── audio/
        └── slide_01.webm
```

---

## 기술 리스크 & 대응

| 리스크 | 원인 | 대응 |
|--------|------|------|
| PPTX 변환 실패 | win32com은 Windows+PowerPoint 필수 | LibreOffice headless fallback |
| Gemini inline_data | flash-image가 디자인 슬라이드서 이미지 재생성 | flash 자동 폴백 (검증됨) |
| Rate limit | Gemini 무료 ~10 RPM | 7초 딜레이 + 큐 처리 |
| 대용량 PPTX | 21MB+ PPTX (22슬라이드) | 비동기 변환 + 진행률 SSE 스트리밍 |
| Canvas 성능 | Fabric.js 고해상도 Canvas | 뷰포트 크기만 렌더링, 스크롤 시 lazy load |

---

## 개발 우선순위 체크리스트

### 1주차
- [x] FastAPI 프로젝트 초기화
- [x] `converter.py`: `pdf_to_pngs()` 구현 (PyMuPDF)
- [x] `converter.py`: `pptx_to_pngs()` 구현 (win32com + LibreOffice fallback)
- [x] `/api/files/upload` 엔드포인트

### 2주차
- [x] React + Vite 프론트엔드 초기화
- [x] 3단 레이아웃 (`SlideList` + `SlideViewer` + `NoteEditor`)
- [x] Fabric.js Canvas 통합 (펜, 형광펜)
- [x] **Undo/Redo 스택 구현** (pympress scribble_list 패턴 — 스냅샷 방식, 최대 50단계)
- [x] **주석 좌표 정규화** (pdfanno `_pageRatio` 패턴 — 뷰포트 비율로 저장)
- [x] 노트 저장/불러오기 (`/api/notes`)

### 3주차
- [x] 주석 도구 (도형, 텍스트 박스)
- [x] PDF 내보내기 (주석 레이어 병합)
- [x] 파일 목록 / 최근 파일 관리 (`GET /api/files`, `DELETE /api/files/{id}`, `RecentFiles` 컴포넌트)

### 4주차 (AI)
- [x] `gemini.py`: `call_gemini_smart()` 구현
- [x] `/api/ai/summarize` 엔드포인트
- [x] NoteEditor에 "AI 요약" 버튼 연동

### 5~6주차 (오디오)
- [x] MediaRecorder API 연동
- [x] 필기 timestamp 저장
- [x] 오디오 재생 컨트롤러

### 7~8주차 (유인물 & 화이트보드)
- [x] 유인물 레이아웃 PDF 내보내기 (1up/2up/4up + 한글 노트)
- [x] 화이트보드 빈 페이지 삽입 (`POST /api/files/{id}/whiteboard`)
- [x] Fabric.js 화이트보드 모드 (황색 배너, 자유 드로잉)

### 9~10주차 (Firebase 동기화)
- [x] Firebase 프로젝트 생성 (`slidenote-2026`, Tokyo 리전)
- [x] Firestore 데이터베이스 생성 + 보안 규칙 배포
- [x] Firebase SDK 설치 (`firebase` npm 패키지)
- [x] `lib/firebase.js` — `initializeApp`, `getFirestore`, `getAuth`
- [x] `hooks/useAuth.js` — Google 로그인/로그아웃, `onAuthStateChanged`
- [x] `hooks/useFirestore.js` — `setDoc` + `onSnapshot` 실시간 동기화
- [x] `App.jsx` — 헤더 로그인 버튼, 노트 패널 "☁ 동기화" 상태 표시
- [ ] Firebase Console에서 **Google 인증 공급자 활성화** (수동 필요)
  - https://console.firebase.google.com/project/slidenote-2026/authentication/providers
- [x] Firebase Storage 연동 (`useStorage.js`, `storage.rules` — Console에서 Storage 활성화 후 `firebase deploy --only storage` 실행)
- [x] 다중 기기 세션 관리 (`useSession.js`, Firestore `sessions/{uid}/files/{fileId}`)

### Docker + Gotenberg 배포 환경 (Phase 3)
- [x] `services/converter.py` — `GOTENBERG_URL` env 감지 → `_gotenberg_pptx_to_pngs()` (httpx 동기 POST)
- [x] `requirements.txt` — `httpx==0.28.1` 추가
- [x] `src/backend/Dockerfile` — python:3.13-slim 기반, uvicorn 서빙
- [x] `src/frontend/Dockerfile` — node:20-alpine 빌드 → nginx:1.27-alpine 멀티스테이지
- [x] `src/frontend/nginx.conf` — /api, /uploads 프록시 + SSE unbuffered + SPA fallback
- [x] `docker-compose.yml` (루트) — backend + frontend + gotenberg 3-서비스

### 업로드 진행률 + 노트 내보내기 (v1.4)
- [x] `GET /api/files/upload/{file_id}/progress` — SSE 스트림 (변환 증간수 실시간 전송)
- [x] `UploadButton` 진행률 바 UI (업로드 진행 중 페이지 카운트 표시)
- [x] `GET /api/export/{file_id}/notes.md` — 전체 슬라이드 노트 Markdown 파일로 다운로드
- [x] 우측 패널 “표 Markdown 내보내기” 버튼 추가
- [x] `PresentationMode` 컴포넌트 — 전체화면 슬라이드 뷰어
  - ←/→/Space 키 슬라이드 이동, ESC/종료 버튼으로 나가기
  - `document.requestFullscreen()` API 연동
  - 하단 컨트롤 바 (평소 투명 → hover 시 표시)
- [x] 헤더 "▶ 발표" 버튼 (파일 업로드 시에만 표시)
### UX 개선 (v1.5) — 사이드바/탐색 답답함 해소

> **배경**: 우측 사이드바(w-80)에 노트·AI 요약·오디오·내보내기 버튼이 세로로 과밀 적재됨.
> 현재 파일명 맥락 없음, 슬라이드 전환 피드백 없음, 첫 사용자 진입점 불명확 등 복합 원인.

#### 핵심 (★★★) — 사이드바 탭 UI 분리
- [x] `App.jsx` 우측 aside: 탭 상태(`activeTab`) 추가 — `'note' | 'export' | 'audio'`
- [x] 탭 헤더 3개 버튼: **노트** / **내보내기** / **오디오** (각 탭 내용만 표시)
- [x] 기본 활성 탭은 `'note'`

#### 핵심 (★★★) — 헤더에 현재 파일명 표시
- [x] `useAppStore`에 `filename: ''` 상태 추가, `setFile` 시그니처 확장
- [x] `RecentFiles.handleOpen`, `UploadButton.onSuccess` 에서 filename 전달
- [x] `App.jsx` 헤더에 `/ {filename}` 표시

#### 보조 (★★☆) — 슬라이드 전환 로딩 스켈레톤
- [x] `SlideViewer.jsx`: `imgLoaded` state + `animate-pulse` 스켈레톤 오버레이
- [x] `currentSlide` 변경 시 `imgLoaded = false` 리셋

#### 보조 (★★☆) — 오디오 패널 접기/펼치기 토글
- [x] `AudioPanel.jsx`: `collapsed` state (기본 `false`) + 토글 헤더 버튼

#### 보조 (★☆☆) — 초기 화면 업로드 CTA
- [x] `RecentFiles.jsx`: 빈 상태에 "PPTX / PDF 업로드" label+input 버튼 추가
- [x] `handleCTAUpload`: `uploadFile` 직접 호출 → `setFile()` 즉시 전환

#### 보조 (★☆☆) — Toolbar 단축키 툴팁
- [x] `Toolbar.jsx` TOOLS 배열에 `shortcut` 필드 + `title` 속성 업데이트
- [x] `App.jsx` 키보드 핸들러에 V/P/H/T/A 단축키, `setToolRef`로 SlideViewer 브릿지

> **구현 완료 (commit 49da015)**

---

## UX 개선 (v1.6) — 단축키 버그 수정 + 드래그 앤 드롭

> **배경**: v1.5 단축키 T/A가 실제로 동작하지 않았음 (tool state만 변경, addText/addArrow 미호출). 파일 업로드 진입점 추가.

#### T/A 키보드 단축키 수정
- [x] `useAnnotation.js`: `activateTool(id)` 추가 — text/arrow 분기 처리 포함
- [x] `SlideViewer.jsx`: `setToolRef.current = annotation.activateTool` (기존 `setTool` → 교체)

#### Toolbar 단축키 tooltip 완성
- [x] `Toolbar.jsx`: `title={`${t.label} (${t.shortcut})`}` 적용 (기존 `title={t.label}` 수정)

#### 전체 화면 드래그 앤 드롭 업로드
- [x] `App.jsx`: `dragOver` state + `handleDragOver/Leave/Drop` 핸들러
- [x] 파란 대시 보더 + 안내 오버레이 표시 (드래그 중)
- [x] PPTX/PDF 파일 드롭 시 즉시 변환 → 로그인 상태면 Firebase 세션 저장

> **구현 완료 (commit 8c06a32)**

---

## UX 개선 (v1.7) — 단축키 완성 + 지우개 도구

> **배경**: v1.6에서 Ctrl+Z/Y 버튼에 tooltip만 있고 실제 키보드 단축키 미연결. 지우개 도구 부재.

#### 지우개(Eraser) 도구
- [x] `useAnnotation.js`: `tool === 'eraser'` 시 마우스 드래그로 닿은 객체 제거 (`containsPoint` + `canvas.remove`)
- [x] `Toolbar.jsx`: TOOLS에 `{ id: 'eraser', label: '지우개', icon: '⌫', shortcut: 'E' }` 추가

#### 단축키 완성
- [x] `SlideViewer.jsx`: `useEffect` — Ctrl+Z(undo), Ctrl+Y/Ctrl+Shift+Z(redo), Delete/Backspace(선택 삭제), Escape(선택 모드)
  - Fabric.js IText 편집 중(`isEditing`) + textarea/input 포커스 시 무시
- [x] `App.jsx`: `TOOL_SHORTCUTS`에 `e: 'eraser'` 추가

> **구현 완료 (commit TBD)**



클론 위치: `repo/` (shallow, `--depth=1`)

| 리포지토리 | 핵심 분석 파일 | 채택한 패턴 |
|-----------|--------------|------------|
| `pdfanno` | `src/core/src/annotation/rect.js`, `schemas/pdfanno-schema.json` | 주석 좌표 정규화 (뷰포트 비율), uuid 기반 ID, type 체계 |
| `slidev` | `packages/client/composables/useDrawings.ts`, `state/drawings.ts` | Per-slide `Record<pageNo, svgStr>` 저장, BroadcastChannel 탭간 동기화 |
| `pympress` | `pympress/scribble.py` | Undo 스냅샷 스택 + Redo 스택, color/width 도구 상태 |
| `gotenberg` | `pkg/modules/libreoffice/routes.go` | `/forms/libreoffice/convert` multipart API, exportHiddenSlides/quality 옵션 |
| `PptxGenJS` | `README.md` | Phase 2: 유인물 내보내기 시 JS 환경에서 PPTX 재생성 고려 |
| `stirling-pdf` | `app/core/.../controller/api/` | 50+ PDF 도구 REST API 구조 참고 (Java Spring Boot) |
| `react-native-pdf-viewer` | `src/PdfViewer.nitro.ts` | NitroModules 인터페이스, DocumentInfo 이벤트 구조 |
| `flutter_file_preview` | README | Android TBS / iOS WKWebView, PPT/PDF 파일 지원 범위 |
| `loose-leaf` | iOS Obj-C | 제스처 기반 필기 UX 참고 (Apple Pencil pressure 값 저장 → pympress에서도 동일) |

### 핵심 채택 결정

1. **주석 좌표 정규화**: pdfanno의 `convertFromExportY()` 아이디어 → 저장 시 `_pageRatio:[w,h]` 기록, 로드 시 현재 뷰포트 크기로 역변환. 해상도 변경에도 주석 위치 유지.

2. **Undo/Redo 스택**: pympress의 `scribble_list` / `scribble_redo_list` 구조 → Fabric.js JSON 스냅샷 방식으로 구현 (최대 50단계, `path:create` 이벤트마다 저장).

3. **Gotenberg 백엔드 분리**: Windows는 win32com, Linux/Docker는 Gotenberg 선택적 사용. `GOTENBERG_URL` 환경변수로 활성화 여부 제어.

4. **모바일 우선순위**: react-native-pdf-viewer가 NitroModules 기반으로 성능 우수. Flutter는 주석 커스터마이징 제약 있어 React Native 우선.

---

## 참고 자료

- [PDF.js 공식](https://mozilla.github.io/pdf.js/)
- [Fabric.js 공식](http://fabricjs.com/)
- [drauu (Slidev 드로잉)](https://github.com/antfu/drauu)
- [PyMuPDF 문서](https://pymupdf.readthedocs.io/)
- [python-pptx 문서](https://python-pptx.readthedocs.io/)
- [google-genai SDK](https://googleapis.github.io/python-genai/)
- [Gotenberg 문서](https://gotenberg.dev/)
- 경쟁 앱: Slid, Notability, ExtraPPT Speaker Notes
