import os
from typing import List

from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Form, BackgroundTasks

from app.core.config import MAX_FILE_SIZE
from app.models.document import UploadResponse, DocumentResponse
from app.services.document_storage import (
    validate_file, upload_document,
    get_documents_by_user, get_documents_by_category, delete_document,
    get_document_view,
)
from app.services.document_rag import process_document_rag
from app.services.chat import ask_about_document
from app.core.supabase import supabase

# 문서 관리 관련 API 라우터 설정
router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Form(None),
    category_id: int = Form(None),
):
    """
    파일 업로드 엔드포인트
    1. 파일 크기 제한 확인
    2. 파일 저장 및 DB 등록
    3. 백그라운드 태스크로 RAG(문서 분석 및 임베딩) 작업 예약
    """
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="파일 크기는 50MB를 초과할 수 없습니다.")

    original_name = os.path.basename(file.filename or "")[:255]

    try:
        contents = await file.read()
    finally:
        await file.close()

    # 파일 유효성 검사 (확장자, 내용 등)
    ext = validate_file(original_name, contents)
    # 문서를 저장소에 업로드하고 DB에 메타데이터 저장
    document_id = upload_document(original_name, contents, ext, user_id, category_id)
    # 백그라운드에서 문서 내용 분석 및 검색 엔진용 데이터(RAG) 생성 시작
    background_tasks.add_task(process_document_rag, document_id)

    return UploadResponse(
        document_id=document_id,
        file_path=f"storage/documents/{document_id}",
        original_file_name=original_name,
    )


@router.get("/user/{user_id}", response_model=List[DocumentResponse])
def list_by_user(user_id: str):
    """사용자별 업로드한 문서 목록 조회"""
    return get_documents_by_user(user_id)


@router.get("/category/{category_id}", response_model=List[DocumentResponse])
def list_by_category(category_id: int):
    """카테고리별 문서 목록 조회"""
    return get_documents_by_category(category_id)


@router.get("/{document_id}/view")
def view_document(document_id: int):
    """특정 문서의 상세 정보 및 뷰어용 데이터 조회"""
    return get_document_view(document_id)


@router.get("/{document_id}/chat")
def get_document_chat(document_id: int):
    """특정 문서 내에서 나눈 채팅 메시지 내역 조회"""
    res = supabase.table("document_chat_messages") \
        .select("id, sender_type, content, created_at") \
        .eq("document_id", document_id) \
        .order("created_at", desc=False) \
        .execute()
    return res.data or []


@router.delete("/{document_id}/chat", status_code=204)
def clear_document_chat(document_id: int):
    """문서 내 채팅 내역 초기화"""
    supabase.table("document_chat_messages") \
        .delete() \
        .eq("document_id", document_id) \
        .execute()


@router.post("/{document_id}/ask")
async def ask_document(document_id: int, body: dict):
    """문서 내용 기반 질의응답 (특정 문서 1개에 대해 질문)"""
    content = body.get("content", "").strip()
    allow_ai_answer = bool(body.get("allow_ai_answer", False))
    if not content:
        raise HTTPException(status_code=400, detail="질문을 입력해주세요.")
    return await ask_about_document(document_id, content, allow_ai_answer)


@router.delete("/{document_id}", status_code=204)
def remove_document(document_id: int):
    """문서 삭제"""
    delete_document(document_id)
