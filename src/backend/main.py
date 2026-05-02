"""
SlideNote Backend — FastAPI 진입점
"""
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI(title="SlideNote API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 업로드 디렉터리
UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 라우터 등록 (구현 예정)
# from routers import files, notes, ai
# app.include_router(files.router, prefix="/api/files")
# app.include_router(notes.router, prefix="/api/notes")
# app.include_router(ai.router, prefix="/api/ai")


@app.get("/")
def root():
    return {"status": "ok", "message": "SlideNote API v0.1"}


@app.get("/health")
def health():
    return {"status": "healthy"}
