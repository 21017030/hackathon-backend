from fastapi import APIRouter
from typing import List

from app.models.category import CategoryCreate, CategoryResponse
from app.services.category import create_category, get_categories, delete_category

# 카테고리(폴더) 관련 API 라우터
router = APIRouter(prefix="/categories", tags=["categories"])


@router.post("", response_model=CategoryResponse, status_code=201)
def create(request: CategoryCreate):
    """새 카테고리(폴더)를 생성합니다."""
    return create_category(user_id=request.user_id, name=request.name)


@router.get("/{user_id}", response_model=List[CategoryResponse])
def list_categories(user_id: str):
    """사용자의 카테고리 목록을 조회합니다."""
    return get_categories(user_id)


@router.delete("/{category_id}", status_code=204)
def delete(category_id: int):
    """카테고리를 삭제합니다. 내부에 문서가 있으면 삭제가 거부됩니다."""
    delete_category(category_id)
