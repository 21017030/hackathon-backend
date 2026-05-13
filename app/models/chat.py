from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ChatSessionCreate(BaseModel):
    """채팅 세션 생성 요청 스키마"""
    user_id: str
    title: str

class ChatSessionResponse(BaseModel):
    """채팅 세션 응답 스키마"""
    id: int
    user_id: str
    title: str
    created_at: datetime

class ChatAskRequest(BaseModel):
    """AI 질문 요청 스키마"""
    session_id: int
    content: str # 질문 내용
    document_ids: Optional[List[int]] = None # 특정 문서만 검색하고 싶을 때

class ChatMessageResponse(BaseModel):
    """채팅 메시지 응답 스키마"""
    id: int
    sender_type: str # 'USER' or 'AI'
    content: str
    created_at: datetime
    sources: Optional[List] = []
