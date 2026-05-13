import logging
from fastapi import HTTPException

from app.core.supabase import supabase

logger = logging.getLogger(__name__)


def create_category(user_id: str, name: str) -> dict:
    """새 카테고리(폴더)를 생성합니다."""
    try:
        res = supabase.table("categories").insert({
            "user_id": user_id,
            "name": name,
        }).execute()
        return res.data[0]
    except Exception as e:
        logger.error("카테고리 생성 실패: %s", e)
        raise HTTPException(status_code=500, detail="카테고리 생성 중 오류가 발생했습니다.")


def get_categories(user_id: str) -> list:
    """사용자의 카테고리 목록을 생성순으로 조회합니다."""
    res = supabase.table("categories").select("*").eq("user_id", user_id).order("created_at", desc=False).execute()
    return res.data


def delete_category(category_id: int) -> None:
    """카테고리를 삭제합니다. 연결된 문서가 있으면 409 오류를 반환합니다."""
    # 해당 카테고리에 연결된 문서가 있으면 삭제 불가
    docs = supabase.table("documents").select("id").eq("category_id", category_id).execute()
    if docs.data:
        raise HTTPException(status_code=409, detail="카테고리에 문서가 존재합니다. 먼저 문서를 삭제해 주세요.")

    try:
        supabase.table("categories").delete().eq("id", category_id).execute()
    except Exception as e:
        logger.error("카테고리 삭제 실패: %s", e)
        raise HTTPException(status_code=500, detail="카테고리 삭제 중 오류가 발생했습니다.")
