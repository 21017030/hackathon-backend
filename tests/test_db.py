import os
from supabase import create_client, Client

# .env 파일 직접 로드 (python-dotenv 없이)
def load_env(path=".env"):
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())

load_env()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ .env 파일에 SUPABASE_URL과 SUPABASE_KEY를 설정해주세요.")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def test_users():
    # users 테이블에서 최대 5개 행 조회
    print("\n[users 테이블]")
    res = supabase.table("users").select("*").limit(5).execute()
    if res.data:
        for row in res.data:
            print(f"  학번: {row['student_id']}, 이름: {row['name']}, 로그인ID: {row['login_id']}")
    else:
        print("  데이터 없음 (테이블 연결 성공)")

def test_categories():
    print("\n[categories 테이블]")
    res = supabase.table("categories").select("*").limit(5).execute()
    if res.data:
        for row in res.data:
            print(f"  ID: {row['id']}, 이름: {row['name']}, 학번: {row['student_id']}")
    else:
        print("  데이터 없음 (테이블 연결 성공)")

def test_documents():
    print("\n[documents 테이블]")
    res = supabase.table("documents").select("*").limit(5).execute()
    if res.data:
        for row in res.data:
            print(f"  ID: {row['id']}, 파일명: {row['original_file_name']}, 상태: {row['parsing_status']}")
    else:
        print("  데이터 없음 (테이블 연결 성공)")

def test_chat_sessions():
    print("\n[chat_sessions 테이블]")
    res = supabase.table("chat_sessions").select("*").limit(5).execute()
    if res.data:
        for row in res.data:
            print(f"  ID: {row['id']}, 제목: {row['title']}, 학번: {row['student_id']}")
    else:
        print("  데이터 없음 (테이블 연결 성공)")

def test_chat_messages():
    print("\n[chat_messages 테이블]")
    res = supabase.table("chat_messages").select("*").limit(5).execute()
    if res.data:
        for row in res.data:
            print(f"  ID: {row['id']}, 발신자: {row['sender_type']}, 내용: {row['content'][:30]}")
    else:
        print("  데이터 없음 (테이블 연결 성공)")

if __name__ == "__main__":
    print("=== Supabase DB 연결 테스트 ===")
    try:
        test_users()
        test_categories()
        test_documents()
        test_chat_sessions()
        test_chat_messages()
        print("\n✅ 모든 테이블 연결 성공!")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
