import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# API 라우터 임포트
from app.api.routes import documents, chat, auth, categories

# 로깅 설정: 애플리케이션 실행 중 발생하는 이벤트를 기록
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# FastAPI 애플리케이션 초기화
app = FastAPI(title="Hackathon API")

# CORS(Cross-Origin Resource Sharing) 설정
# 다른 도메인(예: 프론트엔드 서버)에서 이 API에 접근할 수 있도록 허용합니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # 프론트엔드 개발 환경 포트 허용
    allow_credentials=True,
    allow_methods=["*"], # 모든 HTTP 메서드 허용 (GET, POST, PUT, DELETE 등)
    allow_headers=["*"], # 모든 HTTP 헤더 허용
)

# 기능별 API 라우터 등록
app.include_router(auth.router)       # 인증 관련 API (로그인, 회원가입 등)
app.include_router(documents.router)  # 문서 관리 관련 API (업로드, 조회 등)
app.include_router(categories.router) # 카테고리 관리 관련 API
app.include_router(chat.router)       # 채팅 및 RAG(검색 증강 생성) 관련 API
