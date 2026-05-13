from fastapi import APIRouter, HTTPException
from typing import List

from app.models.chat import ChatSessionCreate, ChatSessionResponse, ChatAskRequest, ChatMessageResponse
from app.services.chat import ask_question, delete_session
from app.core.supabase import supabase

# 채팅 세션 및 메시지 관련 API 라우터 설정
router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/session", response_model=ChatSessionResponse)
async def create_session(request: ChatSessionCreate):
    """새로운 채팅 세션을 생성합니다."""
    try:
        res = supabase.table("chat_sessions").insert({
            "user_id": request.user_id,
            "title": request.title
        }).execute()
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{user_id}", response_model=List[ChatSessionResponse])
async def get_sessions(user_id: str):
    """사용자의 모든 채팅 세션 목록을 최신순으로 가져옵니다."""
    res = supabase.table("chat_sessions").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return res.data

@router.post("/ask")
async def ask(request: ChatAskRequest):
    """
    AI에게 질문을 보냅니다.
    session_id에 메시지를 저장하고, 선택된 document_ids(문서들)의 내용을 기반으로 답변을 생성합니다.
    """
    try:
        return await ask_question(request.session_id, request.content, request.document_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/messages/{session_id}", response_model=List[ChatMessageResponse])
async def get_messages(session_id: int):
    """특정 채팅 세션의 모든 메시지 내역을 가져옵니다."""
    res = supabase.table("chat_messages").select("*").eq("session_id", session_id).order("created_at", desc=False).execute()
    return res.data

@router.delete("/sessions/{session_id}", status_code=204)
async def remove_session(session_id: int):
    """채팅 세션을 삭제합니다."""
    delete_session(session_id)
