# 환경변수 기반 애플리케이션 설정
# .env 파일에서 값을 읽어 전역 상수로 노출합니다.
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(".env 파일에 SUPABASE_URL과 SUPABASE_KEY를 설정해주세요.")

if not GEMINI_API_KEY:
    print("⚠️ 경고: .env 파일에 GEMINI_API_KEY가 설정되지 않았습니다. RAG 기능이 제한될 수 있습니다.")
