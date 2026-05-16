import logging
import traceback
import os
import tempfile
import fitz  # PyMuPDF
from google.genai import types

from app.core.supabase import supabase
from app.core.gemini import client, CHAT_MODEL, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, CHUNK_SIZE, gemini_call

logger = logging.getLogger(__name__)


def _extract_pdf_gemini(file_bytes: bytes, filename: str) -> str:
    """
    Gemini Files API를 사용하여 PDF 전체 내용을 텍스트로 추출합니다.
    멀티모달 기능을 사용하여 이미지, 표, 차트 내의 텍스트도 인식할 수 있습니다.
    """
    tmp_path = None
    uploaded_file = None
    try:
        # 1. 임시 파일 생성 (Gemini API 업로드용)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(file_bytes)
            tmp_path = f.name

        # 2. Gemini 클라우드 스토리지에 파일 업로드
        uploaded_file = client.files.upload(
            path=tmp_path,
            config=types.UploadFileConfig(
                mime_type="application/pdf",
                display_name=filename,
            ),
        )

        # 3. Gemini 모델을 사용하여 텍스트 추출 명령 실행
        response = gemini_call(
            client.models.generate_content,
            model=CHAT_MODEL,
            contents=[
                uploaded_file,
                "이 PDF 문서의 전체 내용을 텍스트로 추출해주세요. "
                "각 페이지가 시작될 때마다 반드시 '[N페이지]' 형식으로 페이지 번호를 표시하세요. "
                "코드가 포함된 이미지나 코드 블록이 있으면 들여쓰기, 특수문자, 줄바꿈을 포함하여 한 글자도 빠짐없이 정확히 그대로 추출하세요. "
                "표, 이미지, 그래프, 차트가 있으면 그 내용도 설명해주세요. "
                "마크다운 형식 없이 순수 텍스트로만 출력하세요.",
            ],
        )
        return response.text or ""
    finally:
        # 사용 후 임시 파일 및 업로드된 파일 삭제
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass


async def process_document_rag(document_id: int):
    """
    RAG(Retrieval-Augmented Generation) 인제스천 파이프라인:
    1. DB에서 문서 정보 조회 및 파일 다운로드
    2. 텍스트 추출 (Gemini 멀티모달 우선, 실패 시 PyMuPDF 폴백)
    3. 텍스트를 일정한 크기(Chunk)로 분할
    4. 각 청크에 대한 임베딩(Vector) 생성
    5. Supabase 벡터 DB에 저장 (시맨틱 검색용)
    6. 문서 처리 상태 업데이트
    """
    try:
        # 문서 정보 조회
        res = supabase.table("documents").select("*").eq("id", document_id).single().execute()
        doc_data = res.data
        if not doc_data:
            logger.error(f"문서 ID {document_id}를 찾을 수 없습니다.")
            return

        # 스토리지에서 실제 PDF 파일 다운로드
        file_path = doc_data["file_path"]
        file_bytes = supabase.storage.from_("documents").download(file_path)

        # 텍스트 추출 시도
        text = ""
        try:
            text = _extract_pdf_gemini(file_bytes, doc_data["original_file_name"])
            logger.info(f"문서 {document_id} Gemini 멀티모달 추출 완료 ({len(text)}자)")
        except Exception as e:
            # Gemini 추출 실패 시 전통적인 PDF 라이브러리(PyMuPDF)로 폴백
            logger.warning(f"Gemini 추출 실패, PyMuPDF 폴백: {e}")
            with fitz.open(stream=file_bytes, filetype="pdf") as pdf:
                for page in pdf:
                    text += page.get_text()

        if not text.strip():
            raise Exception("추출된 텍스트가 없습니다.")

        # 텍스트 청킹 (고정 크기로 분할)
        chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]

        # 각 청크에 대해 벡터 임베딩 생성 및 DB 저장
        for i, chunk_content in enumerate(chunks):
            embedding_res = gemini_call(
                client.models.embed_content,
                model=EMBEDDING_MODEL,
                contents=chunk_content,
                config=types.EmbedContentConfig(
                    task_type="retrieval_document",
                    output_dimensionality=EMBEDDING_DIMENSIONS,
                ),
            )
            embedding_vector = embedding_res.embeddings[0].values

            # 벡터 데이터를 포함하여 DB에 저장 (나중에 유사도 검색에 사용됨)
            supabase.table("document_chunks").insert({
                "document_id": document_id,
                "content": chunk_content,
                "embedding": embedding_vector,
                "chunk_index": i
            }).execute()

        # 처리 완료 상태로 업데이트
        supabase.table("documents").update({"parsing_status": "COMPLETED"}).eq("id", document_id).execute()
        logger.info(f"문서 {document_id} RAG 처리 완료")

    except Exception as e:
        # 오류 발생 시 실패 상태로 업데이트
        logger.error(f"문서 {document_id} RAG 처리 중 오류: {e}\n{traceback.format_exc()}")
        supabase.table("documents").update({"parsing_status": "FAILED"}).eq("id", document_id).execute()
