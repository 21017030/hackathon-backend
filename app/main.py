import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# API 라우터 임포트
from app.api.routes import documents, chat, auth, categories

# 로깅 설정: 애플리케이션 실행 중 발생하는 이벤트를 기록
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# FastAPI 애플리케이션 초기화
app = FastAPI(title="Hackathon API")

# CORS 허용 origins: 환경변수 ALLOWED_ORIGINS (콤마 구분) 또는 로컬 개발 기본값
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 기능별 API 라우터 등록
app.include_router(auth.router)       # 인증 관련 API (로그인, 회원가입 등)
app.include_router(documents.router)  # 문서 관리 관련 API (업로드, 조회 등)
app.include_router(categories.router) # 카테고리 관리 관련 API
app.include_router(chat.router)       # 채팅 및 RAG(검색 증강 생성) 관련 API
