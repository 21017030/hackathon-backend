from supabase import create_client, Client
from app.core.config import SUPABASE_URL, SUPABASE_KEY

# Supabase 클라이언트 초기화
# 데이터베이스, 스토리지, 인증 서비스를 사용하기 위한 중앙 클라이언트 객체입니다.
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
