# Gemini AI 클라이언트 및 모델/파라미터 설정
# 모델명과 RAG 동작 상수를 한 곳에서 관리합니다.
import time
import logging
from google import genai
from app.core.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)


def gemini_call(fn, *args, max_retries: int = 3, initial_delay: float = 5.0, **kwargs):
    """503 UNAVAILABLE 에러일 때만 지수 백오프로 재시도."""
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            err_str = str(e)
            if ("UNAVAILABLE" in err_str or "503" in err_str) and attempt < max_retries - 1:
                delay = initial_delay * (2 ** attempt)
                logger.warning(f"Gemini 503 에러, {delay:.0f}초 후 재시도 ({attempt + 1}/{max_retries - 1})")
                time.sleep(delay)
            else:
                raise

client = genai.Client(api_key=GEMINI_API_KEY)

CHAT_MODEL = "gemini-3.1-flash-lite"      # 채팅 답변 생성에 사용하는 모델
REWRITE_MODEL = "gemini-3.1-flash-lite"   # 팔로업 쿼리 재작성에 사용하는 모델
EMBEDDING_MODEL = "gemini-embedding-001"  # 텍스트 → 벡터 변환 모델
EMBEDDING_DIMENSIONS = 1536  # pgvector HNSW 인덱스 호환 (최대 2000차원)

CHUNK_SIZE = 1000            # RAG 인제스션 청크 크기 (문자 수)
RAG_CHUNK_LIMIT = 6          # 벡터 검색 반환 청크 수
HISTORY_LIMIT = 6            # 대화 히스토리 로드 개수
REWRITE_HISTORY_WINDOW = 4   # 쿼리 재작성에 사용할 최근 대화 수
