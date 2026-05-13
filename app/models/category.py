from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class CategoryCreate(BaseModel):
    """카테고리 생성 요청 스키마"""
    user_id: str
    name: str


class CategoryResponse(BaseModel):
    """카테고리 응답 스키마"""
    id: int
    user_id: Optional[str]
    name: str
    created_at: datetime
