# 개발 환경 설정 가이드

> 신규 기여자 또는 새 PC에서 SlideNote를 처음 설정할 때 참고하세요.

---

## 사전 요구사항

| 항목 | 버전 | 비고 |
|------|------|------|
| Python | 3.13+ | Anaconda/Miniconda 권장 (Windows) |
| Node.js | 20+ | npm 10+ 포함 |
| Microsoft PowerPoint | 2016+ | Windows만, PPTX 고품질 변환 시 필요 |
| Git | 최신 | |

> Linux/Mac에서 PPTX를 변환하려면 **LibreOffice** 또는 **Gotenberg** 컨테이너 필요.

---

## 저장소 클론

```bash
git clone https://github.com/geondongkim/SlideNote.git
cd SlideNote
```

---

## 환경 변수 설정

이 프로젝트에는 `.env` 파일이 **두 곳** 필요합니다.

### 1. 백엔드 — 프로젝트 루트 (`SlideNote/.env`)

`main.py`가 프로젝트 루트의 `.env`를 자동 로드합니다 (`src/backend/` 아님):

```bash
# SlideNote/.env
GOOGLE_API_KEY=AIzaSy...          # Gemini Vision API 키 (AI 기능 사용 시 필수)
# GOTENBERG_URL=http://localhost:3000  # Docker 배포 시 PPTX 변환용 (선택)
```

> **API 키 발급**: [Google AI Studio](https://aistudio.google.com/apikey) → "Create API key"

### 2. 프론트엔드 — `src/frontend/.env`

Firebase 설정값입니다. 예시 파일을 복사해서 시작하세요:

```bash
cp src/frontend/.env.example src/frontend/.env
# 이후 실제 값으로 채우기
```

```bash
# src/frontend/.env
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=your_project_id.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your_project_id
VITE_FIREBASE_STORAGE_BUCKET=your_project_id.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=...
VITE_FIREBASE_APP_ID=...
```

**값 확인 방법**: [Firebase 콘솔](https://console.firebase.google.com) → 해당 프로젝트 → 프로젝트 설정 → "내 앱" → SDK 설정 및 구성 → `firebaseConfig` 객체

> **`VITE_` 접두사**: Vite 빌드 시 클라이언트 번들에 포함됩니다. Firebase Web API 키는 클라이언트 공개용 키이므로 노출이 허용됩니다. 보안은 `firestore.rules` / `storage.rules`로 관리합니다.

> **두 `.env` 모두 `.gitignore`에 의해 커밋에서 제외됩니다.** 실수로 push하지 않도록 주의하세요.

---

## 백엔드 설정

### Windows (Anaconda/Miniconda 환경)

```powershell
cd src\backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Windows (venv 사용)

```powershell
cd src\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### macOS / Linux

```bash
cd src/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**서버 확인:**
- API 루트: http://localhost:8000/
- **Swagger UI** (전체 API 명세): http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 프론트엔드 설정

```bash
cd src/frontend
npm install
npm run dev
# http://localhost:5174 접속
# (5173 포트가 사용 중이면 Vite가 자동으로 5174 할당)
```

### Vite 프록시 설정 (vite.config.js)

개발 서버는 아래 경로를 백엔드(8000)로 자동 프록시합니다:

```js
proxy: {
  '/api':     'http://localhost:8000',
  '/uploads': 'http://localhost:8000',
}
```

별도 CORS 설정 없이 `http://localhost:5174`에서 API 호출이 동작합니다.

---

## 두 서버 동시 실행

### Windows (PowerShell 스크립트)

```powershell
.\scripts\dev.ps1
```

### Windows (터미널 2개 수동)

```powershell
# 터미널 1 — 백엔드
cd src\backend ; uvicorn main:app --reload --port 8000

# 터미널 2 — 프론트엔드
cd src\frontend ; npm run dev
```

### macOS / Linux

```bash
bash scripts/dev.sh
```

---

## 업로드 파일 저장 구조

파일을 업로드하면 `src/backend/uploads/` 아래에 저장됩니다:

```
uploads/
└── {file_id}/              # UUID (32자 hex)
    ├── meta.json           # 파일명, 페이지 수, 업로드 시각
    ├── original.pptx       # 원본 파일 (or .pdf)
    ├── original_hq.pdf     # 고품질 PDF 캐시 (PPTX → ppSaveAsPDF)
    ├── slides/
    │   ├── page_01.png     # 슬라이드 PNG (150 DPI)
    │   ├── page_02.png
    │   └── ...
    ├── notes/
    │   ├── slide_01.json   # 노트 + 주석 (Fabric.js JSON)
    │   └── ...
    └── audio/
        ├── slide_01.webm   # 오디오 녹음
        └── ...
```

> `uploads/`는 `.gitignore`에 포함되어 있습니다. 커밋 금지.

---

## 주요 파일 맵

### 백엔드

| 파일 | 역할 |
|------|------|
| `main.py` | FastAPI 앱 진입점, 미들웨어, 라우터 등록 |
| `routers/files.py` | 파일 업로드·목록·삭제·슬라이드 목록 |
| `routers/notes.py` | 노트·주석 CRUD |
| `routers/export.py` | PDF 내보내기, Markdown 다운로드, 고품질 PDF |
| `routers/ai.py` | AI 요약 · Markdown 변환 (SSE 스트리밍) |
| `routers/audio.py` | 오디오 업로드·스트리밍·타임스탬프 |
| `services/converter.py` | PPTX/PDF → PNG 변환, PPTX → 고품질 PDF |
| `services/gemini.py` | Gemini Vision API 연동 |
| `services/exporter.py` | Searchable PDF · 유인물 생성 (reportlab) |

### 프론트엔드

| 파일 | 역할 |
|------|------|
| `App.jsx` | 최상위 컴포넌트, 3단 레이아웃, 탭 상태 |
| `store/useAppStore.js` | Zustand 전역 상태 (fileId, currentSlide 등) |
| `lib/api.js` | axios 인스턴스 + 모든 API 호출 함수 |
| `lib/firebase.js` | Firebase 초기화 |
| `components/SlideViewer.jsx` | 슬라이드 이미지 + Fabric.js Canvas 오버레이 |
| `components/Toolbar.jsx` | 주석 도구 (펜/형광펜/텍스트/지우개 등) |
| `components/SlideList.jsx` | 좌측 슬라이드 목록 + 썸네일 |
| `components/AudioPanel.jsx` | 오디오 녹음·재생 패널 |
| `hooks/useAnnotation.js` | Fabric.js Canvas 초기화·저장·로드 훅 |
| `hooks/useAudioRecorder.js` | MediaRecorder API 녹음 훅 |
| `hooks/useAuth.js` | Firebase Google 로그인 훅 |
| `hooks/useFirestore.js` | Firestore 실시간 동기화 훅 |

---

## 자주 발생하는 문제

→ 자세한 내용은 [troubleshooting.md](troubleshooting.md) 참조.

### "Could not import module main" 오류

`uvicorn main:app`은 **`src/backend/`** 디렉터리에서 실행해야 합니다.

```powershell
# ❌ 잘못된 위치
cd SlideNote
uvicorn main:app --port 8000   # 오류

# ✅ 올바른 위치
cd SlideNote\src\backend
uvicorn main:app --port 8000
```

### .env 파일을 못 찾음 (API 키 없음)

`.env`는 프로젝트 **루트**에 있어야 합니다 (`src/backend/` 아님):

```
SlideNote/
├── .env          ← 여기
├── src/
│   └── backend/
│       └── main.py   # Path(__file__).parent.parent.parent / ".env" 로 로드
```

### PowerShell에서 curl 명령이 안 됨

PowerShell의 `curl`은 `Invoke-WebRequest` alias입니다. API 테스트는:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/" -Method GET
# 또는 Git Bash / WSL에서 curl 사용
```

### Vite 포트 5174 (5173 아닌 이유)

다른 프로세스가 5173을 사용 중이면 Vite가 자동으로 5174를 할당합니다.  
고정하려면 `vite.config.js`에 `server: { port: 5174, strictPort: true }` 추가.

---

## 환경별 PPTX 변환 우선순위

```
Windows (PowerPoint 설치됨)
  → win32com subprocess (COM STA 충돌 방지 패턴) — 최고 품질

Linux + GOTENBERG_URL 환경변수 설정됨
  → Gotenberg 컨테이너 (LibreOffice API) — 중간 품질

Linux + GOTENBERG_URL 없음
  → LibreOffice headless — 폴백 (한글 폰트 재현 불완전)
```

> Gotenberg 없이 Linux에서 고품질 변환이 필요하면:
> ```bash
> docker run -d -p 3000:3000 gotenberg/gotenberg:8
> # .env에 추가
> GOTENBERG_URL=http://localhost:3000
> ```
