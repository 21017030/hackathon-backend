from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class UploadResponse(BaseModel):
    """파일 업로드 성공 응답 스키마"""
    document_id: int
    file_path: str
    original_file_name: str


class DocumentResponse(BaseModel):
    """문서 목록 조회 응답 스키마"""
    id: int
    user_id: Optional[str]
    category_id: Optional[int]
    original_file_name: str
    parsing_status: str
    created_at: datetime
