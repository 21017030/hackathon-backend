from pydantic import BaseModel
from typing import Optional


class RegisterRequest(BaseModel):
    """회원가입 요청 스키마"""
    student_id: str
    login_id: str
    password: str
    name: str


class LoginRequest(BaseModel):
    """로그인 요청 스키마"""
    login_id: str
    password: str


class UserResponse(BaseModel):
    """로그인/회원가입 성공 응답 스키마 (비밀번호 제외)"""
    id: str
    student_id: str
    login_id: str
    name: str


class UpdateUserRequest(BaseModel):
    """회원정보 수정 요청 스키마 (변경할 필드만 전송)"""
    student_id: Optional[str] = None
    login_id: Optional[str] = None
    name: Optional[str] = None
    password: Optional[str] = None
