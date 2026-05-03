"""
SlideNote Backend — FastAPI 진입점
"""
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트(src/backend에서 두 단계 위)의 .env 로드
_ROOT_ENV = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_ROOT_ENV)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="SlideNote API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 업로드 디렉터리
UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 라우터 등록
from routers import files, notes, export, ai, audio
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(notes.router, prefix="/api/notes", tags=["notes"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(audio.router, prefix="/api/audio", tags=["audio"])


@app.get("/")
def root():
    return {"status": "ok", "message": "SlideNote API v0.1"}


@app.get("/health")
def health():
    return {"status": "healthy"}
