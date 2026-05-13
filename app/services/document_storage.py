import logging
import uuid
import os

from fastapi import HTTPException

from app.core.config import MAX_FILE_SIZE
from app.core.supabase import supabase

logger = logging.getLogger(__name__)

# 지원 파일 형식별 매직 바이트 (파일 앞부분으로 실제 형식 검증)
MAGIC_NUMBERS = {
    ".pdf": b"%PDF",
}

# 파일 형식별 Content-Type 매핑
CONTENT_TYPES = {
    ".pdf": "application/pdf",
}

# 업로드 허용 확장자 목록
ALLOWED_EXTENSIONS = {".pdf"}


def validate_file(original_name: str, contents: bytes) -> str:
    """파일 확장자, 크기, 매직 바이트를 검증하고 확장자를 반환합니다."""
    ext = os.path.splitext(original_name)[1].lower()
    if not original_name or ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="파일 크기는 50MB를 초과할 수 없습니다.")

    magic = MAGIC_NUMBERS.get(ext)
    if magic and not contents.startswith(magic):
        raise HTTPException(status_code=400, detail="파일 형식이 올바르지 않습니다.")

    return ext


def upload_document(original_name: str, contents: bytes, ext: str, user_id: str = None, category_id: int = None) -> int:
    """파일을 스토리지에 업로드하고 DB에 메타데이터를 저장한 뒤 문서 ID를 반환합니다."""
    file_path = f"{uuid.uuid4()}{ext}"

    try:
        content_type = CONTENT_TYPES[ext]
        supabase.storage.from_("documents").upload(file_path, contents, {"content-type": content_type})
    except Exception as e:
        logger.error("스토리지 업로드 실패: %s", e)
        raise HTTPException(status_code=500, detail="파일 저장 중 오류가 발생했습니다.")

    try:
        res = supabase.table("documents").insert({
            "user_id": user_id,
            "category_id": category_id,
            "original_file_name": original_name,
            "file_path": file_path,
            "parsing_status": "PENDING",
        }).execute()

        if not res.data:
            raise Exception("DB insert result is empty")

        return res.data[0]["id"]
    except Exception as e:
        logger.error("DB 저장 실패: %s", e)
        # DB 저장 실패 시 이미 업로드된 스토리지 파일도 정리
        try:
            supabase.storage.from_("documents").remove([file_path])
        except Exception as cleanup_err:
            logger.error("스토리지 정리 실패: %s", cleanup_err)
        raise HTTPException(status_code=500, detail="파일 정보 저장 중 오류가 발생했습니다.")


def get_document_view(document_id: int) -> dict:
    """문서 뷰어용 데이터(서명 URL, 청크 텍스트)를 반환합니다."""
    res = supabase.table("documents").select("*").eq("id", document_id).single().execute()
    doc = res.data
    if not doc:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

    ext = os.path.splitext(doc["file_path"])[1].lower()

    # 1시간 유효한 서명 URL 생성 (PDF 직접 열람용)
    try:
        signed = supabase.storage.from_("documents").create_signed_url(doc["file_path"], 3600)
        signed_url = signed.get("signedURL") or signed.get("signedUrl") or ""
    except Exception:
        signed_url = ""

    # RAG 청크들을 순서대로 이어 붙여 전체 텍스트 재구성
    chunks_res = (
        supabase.table("document_chunks")
        .select("content, chunk_index")
        .eq("document_id", document_id)
        .order("chunk_index")
        .execute()
    )
    content = "\n".join(c["content"] for c in chunks_res.data) if chunks_res.data else ""

    return {
        "filename": doc["original_file_name"],
        "ext": ext,
        "signed_url": signed_url,
        "content": content,
    }


def get_documents_by_user(user_id: str) -> list:
    """사용자별 문서 목록을 최신순으로 반환합니다."""
    res = supabase.table("documents").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return res.data


def get_documents_by_category(category_id: int) -> list:
    """카테고리별 문서 목록을 최신순으로 반환합니다."""
    res = supabase.table("documents").select("*").eq("category_id", category_id).order("created_at", desc=True).execute()
    return res.data


def delete_document(document_id: int) -> None:
    """청크 → DB → 스토리지 순으로 문서를 완전히 삭제합니다."""
    res = supabase.table("documents").select("file_path").eq("id", document_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

    file_path = res.data[0]["file_path"]

    try:
        supabase.table("document_chunks").delete().eq("document_id", document_id).execute()
    except Exception as e:
        logger.error("청크 삭제 실패: %s", e)
        raise HTTPException(status_code=500, detail="문서 청크 삭제 중 오류가 발생했습니다.")

    try:
        supabase.table("documents").delete().eq("id", document_id).execute()
    except Exception as e:
        logger.error("문서 DB 삭제 실패: %s", e)
        raise HTTPException(status_code=500, detail="문서 정보 삭제 중 오류가 발생했습니다.")

    try:
        supabase.storage.from_("documents").remove([file_path])
    except Exception as e:
        logger.warning("스토리지 파일 삭제 실패 (이미 없을 수 있음): %s", e)
