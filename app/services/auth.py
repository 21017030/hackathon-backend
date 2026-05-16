import logging
import bcrypt
from typing import Optional
from fastapi import HTTPException

from app.core.supabase import supabase

logger = logging.getLogger(__name__)


def _hash(password: str) -> str:
    """비밀번호를 bcrypt로 해시합니다."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify(password: str, hashed: str) -> bool:
    """입력 비밀번호와 저장된 해시를 비교합니다."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def check_login_id_available(login_id: str) -> bool:
    """해당 로그인 아이디가 사용 가능한지 확인합니다."""
    res = supabase.table("users").select("id").eq("login_id", login_id).execute()
    return not bool(res.data)


def register_user(student_id: str, login_id: str, password: str, name: str) -> dict:
    """새 사용자를 등록합니다. 아이디·학번 중복 시 409 오류를 반환합니다."""
    if supabase.table("users").select("id").eq("login_id", login_id).execute().data:
        raise HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다.")

    if supabase.table("users").select("id").eq("student_id", student_id).execute().data:
        raise HTTPException(status_code=409, detail="이미 등록된 학번입니다.")

    try:
        res = supabase.table("users").insert({
            "student_id": student_id,
            "login_id": login_id,
            "password": _hash(password),
            "name": name,
        }).execute()
        user = res.data[0]
        return {"id": user["id"], "student_id": user["student_id"], "login_id": user["login_id"], "name": user["name"]}
    except Exception as e:
        logger.error("회원가입 실패: %s", e)
        raise HTTPException(status_code=500, detail="회원가입 처리 중 오류가 발생했습니다.")


def login_user(login_id: str, password: str) -> dict:
    """아이디·비밀번호로 인증하고 사용자 정보를 반환합니다."""
    res = supabase.table("users").select("*").eq("login_id", login_id).execute()
    if not res.data:
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    user = res.data[0]
    if not _verify(password, user["password"]):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    return {"id": user["id"], "student_id": user["student_id"], "login_id": user["login_id"], "name": user["name"]}


def delete_user(user_id: str) -> None:
    """사용자 계정과 관련된 모든 데이터를 삭제합니다."""
    try:
        docs = supabase.table("documents").select("id, file_path").eq("user_id", user_id).execute()
        doc_ids = [d["id"] for d in (docs.data or [])]
        file_paths = [d["file_path"] for d in (docs.data or []) if d.get("file_path")]
        if doc_ids:
            supabase.table("document_chat_messages").delete().in_("document_id", doc_ids).execute()
            supabase.table("document_chunks").delete().in_("document_id", doc_ids).execute()
            supabase.table("documents").delete().in_("id", doc_ids).execute()
        if file_paths:
            try:
                supabase.storage.from_("documents").remove(file_paths)
            except Exception as e:
                logger.warning("스토리지 파일 삭제 실패 (DB는 삭제됨): %s", e)

        sessions = supabase.table("chat_sessions").select("id").eq("user_id", user_id).execute()
        session_ids = [s["id"] for s in (sessions.data or [])]
        if session_ids:
            supabase.table("chat_messages").delete().in_("session_id", session_ids).execute()
            supabase.table("chat_sessions").delete().in_("id", session_ids).execute()

        supabase.table("categories").delete().eq("user_id", user_id).execute()
        supabase.table("users").delete().eq("id", user_id).execute()
    except Exception as e:
        logger.error("회원 탈퇴 실패: %s", e)
        raise HTTPException(status_code=500, detail="회원 탈퇴 처리 중 오류가 발생했습니다.")


def update_user(user_id: str, student_id: Optional[str] = None, login_id: Optional[str] = None, name: Optional[str] = None, password: Optional[str] = None) -> dict:
    """사용자 정보를 수정합니다. 변경된 필드만 DB에 반영합니다."""
    updates: dict = {}
    if student_id is not None:
        if supabase.table("users").select("id").eq("student_id", student_id).neq("id", user_id).execute().data:
            raise HTTPException(status_code=409, detail="이미 등록된 학번입니다.")
        updates["student_id"] = student_id
    if login_id is not None:
        if supabase.table("users").select("id").eq("login_id", login_id).neq("id", user_id).execute().data:
            raise HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다.")
        updates["login_id"] = login_id
    if name is not None:
        updates["name"] = name
    if password is not None:
        updates["password"] = _hash(password)
    if not updates:
        raise HTTPException(status_code=400, detail="수정할 내용이 없습니다.")
    try:
        res = supabase.table("users").update(updates).eq("id", user_id).execute()
        user = res.data[0]
        return {"id": user["id"], "student_id": user["student_id"], "login_id": user["login_id"], "name": user["name"]}
    except Exception as e:
        logger.error("회원정보 수정 실패: %s", e)
        raise HTTPException(status_code=500, detail="회원정보 수정 중 오류가 발생했습니다.")
