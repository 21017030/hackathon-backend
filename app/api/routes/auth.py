from fastapi import APIRouter

from app.models.auth import RegisterRequest, LoginRequest, UserResponse, UpdateUserRequest
from app.services.auth import register_user, login_user, check_login_id_available, update_user

# 인증 관련 API 라우터 (회원가입, 로그인, 아이디 중복확인, 회원정보 수정)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
def register(request: RegisterRequest):
    """신규 사용자를 등록합니다."""
    return register_user(
        student_id=request.student_id,
        login_id=request.login_id,
        password=request.password,
        name=request.name,
    )


@router.post("/login", response_model=UserResponse)
def login(request: LoginRequest):
    """아이디/비밀번호로 로그인합니다."""
    return login_user(login_id=request.login_id, password=request.password)


@router.get("/check-login-id")
def check_id(login_id: str):
    """로그인 아이디 중복 여부를 확인합니다."""
    return {"available": check_login_id_available(login_id)}


@router.put("/users/{user_id}", response_model=UserResponse)
def update_profile(user_id: str, request: UpdateUserRequest):
    """사용자 정보(아이디, 이름, 학번, 비밀번호)를 수정합니다."""
    return update_user(
        user_id,
        student_id=request.student_id,
        login_id=request.login_id,
        name=request.name,
        password=request.password,
    )
