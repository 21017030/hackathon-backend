import logging
import re
from typing import List, Optional
from google.genai import types

from fastapi import HTTPException
from app.core.supabase import supabase
from app.core.gemini import client, CHAT_MODEL, REWRITE_MODEL, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, RAG_CHUNK_LIMIT, HISTORY_LIMIT, REWRITE_HISTORY_WINDOW, gemini_call

logger = logging.getLogger(__name__)


def _rewrite_query(content: str, history: list) -> str:
    """대화 맥락을 반영해 팔로업 질문을 독립적인 검색 쿼리로 재작성."""
    if not history:
        return content
    recent = history[-REWRITE_HISTORY_WINDOW:]
    history_str = "\n".join([
        f"{'사용자' if m.get('sender_type') == 'USER' or m.get('sender') == 'user' else 'AI'}: {m.get('content', '')[:300]}"
        for m in recent
    ])
    prompt = f"""아래 대화 내역을 참고하여 사용자의 질문을 문서 검색에 적합한 독립적인 쿼리로 변환하세요.
변환된 쿼리만 한 줄로 출력하세요.

대화 내역:
{history_str}

현재 질문: {content}

검색 쿼리:"""
    try:
        response = gemini_call(client.models.generate_content, model=REWRITE_MODEL, contents=prompt)
        rewritten = (response.text or "").strip()
        logger.info(f"쿼리 재작성: '{content}' → '{rewritten}'")
        return rewritten or content
    except Exception:
        return content


async def get_relevant_chunks_with_sources(
    query_vector: List[float],
    document_ids: Optional[List[int]] = None,
    limit: int = RAG_CHUNK_LIMIT,
) -> list:
    chunks = await get_relevant_chunks(query_vector, document_ids, limit)
    if not chunks:
        return []

    doc_ids = list({c['document_id'] for c in chunks})
    docs_res = supabase.table("documents").select("id, original_file_name, category_id").in_("id", doc_ids).execute()
    doc_map = {d['id']: d for d in (docs_res.data or [])}

    cat_ids = list({d['category_id'] for d in doc_map.values() if d.get('category_id')})
    cat_map = {}
    if cat_ids:
        cats_res = supabase.table("categories").select("id, name").in_("id", cat_ids).execute()
        cat_map = {c['id']: c['name'] for c in (cats_res.data or [])}

    for chunk in chunks:
        doc = doc_map.get(chunk['document_id'], {})
        chunk['filename'] = doc.get('original_file_name', '알 수 없음')
        chunk['category'] = cat_map.get(doc.get('category_id'), '분류 없음')
        match = re.search(r'\[(\d+)페이지\]', chunk.get('content', ''))
        chunk['page'] = int(match.group(1)) if match else None

    return chunks


def _build_context(chunks: list) -> str:
    if not chunks:
        return "자료에서 관련 내용을 찾을 수 없습니다."
    parts = []
    for c in chunks:
        label = f"[출처: {c['category']} > {c['filename']}"
        if c.get('page'):
            label += f" {c['page']}페이지"
        label += "]"
        parts.append(f"{label}\n{c['content']}")
    return "\n\n".join(parts)


def _extract_sources(chunks: list) -> list:
    seen, sources = set(), []
    for c in chunks:
        key = c.get('filename', '알 수 없음')
        if key not in seen:
            seen.add(key)
            sources.append({
                "filename": key,
                "category": c.get('category', '분류 없음'),
            })
    return sources


def _filter_used_sources(ai_answer: str, all_sources: list) -> tuple[str, list]:
    """Gemini가 명시한 파일명만 출처로 필터링하고 마커를 답변에서 제거."""
    # 프롬프트 구조 텍스트가 응답에 포함된 경우 제거
    ai_answer = re.sub(r'\[이전 대화 내역\].*', '', ai_answer, flags=re.DOTALL).strip()
    match = re.search(r'\[참고자료:([^\]]*)\]', ai_answer)
    if not match:
        return ai_answer, []
    used_names = {f.strip() for f in match.group(1).split('|') if f.strip()}
    cleaned = re.sub(r'\[참고자료:[^\]]*\]', '', ai_answer).strip()
    filtered = [s for s in all_sources if s['filename'] in used_names]
    if 'AI 답변' in used_names:
        filtered.append({"filename": "AI 답변", "category": "AI 답변"})
    return cleaned, filtered


async def get_relevant_chunks(query_vector: List[float], document_ids: Optional[List[int]] = None, limit: int = RAG_CHUNK_LIMIT):
    try:
        rpc_params = {
            "query_embedding": query_vector,
            "match_threshold": 0.5,
            "match_count": limit,
        }
        if document_ids:
            rpc_params["filter_document_ids"] = document_ids

        logger.info(f"Calling RPC match_document_chunks with params: {rpc_params}")
        res = supabase.rpc("match_document_chunks", rpc_params).execute()
        return res.data
    except Exception as e:
        logger.error(f"Vector search failed: {str(e)}")
        return []


# ── ask_question 보조 함수 ─────────────────────────────────────

def _load_history(session_id: int, limit: int = HISTORY_LIMIT) -> list:
    res = supabase.table("chat_messages") \
        .select("*") \
        .eq("session_id", session_id) \
        .order("created_at", desc=True) \
        .limit(limit) \
        .execute()
    return res.data[::-1]


def _filter_ai_history(history: list) -> list:
    """AI 지식으로 답변된 AI 메시지를 히스토리에서 제외."""
    return [
        msg for msg in history
        if not (
            msg.get('sender_type') == 'AI' and
            any(s.get('filename') == 'AI 답변' for s in (msg.get('sources') or []))
        )
    ]


def _save_message(session_id: int, sender_type: str, content: str, sources: list = None) -> dict:
    payload = {"session_id": session_id, "sender_type": sender_type, "content": content}
    if sources is not None:
        payload["sources"] = sources
    res = supabase.table("chat_messages").insert(payload).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="메시지 저장에 실패했습니다.")
    return res.data[0]


def _resolve_document_ids(session_id: int, document_ids: Optional[List[int]]) -> List[int]:
    """document_ids가 None이면 세션 소유자의 전체 문서 ID를 반환."""
    if document_ids is not None:
        return document_ids
    session_res = supabase.table("chat_sessions").select("user_id").eq("id", session_id).execute()
    if not session_res.data:
        raise HTTPException(status_code=404, detail="채팅 세션을 찾을 수 없습니다.")
    user_id = session_res.data[0]["user_id"]
    docs_res = supabase.table("documents").select("id").eq("user_id", user_id).execute()
    return [d["id"] for d in docs_res.data]


async def _generate_embedding(text: str) -> List[float]:
    res = gemini_call(
        client.models.embed_content,
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            task_type="retrieval_query",
            output_dimensionality=EMBEDDING_DIMENSIONS,
        ),
    )
    return res.embeddings[0].values


def _build_prompt(context: str, history_str: str, content: str, filenames: str, allow_ai_answer: bool = False) -> str:
    if allow_ai_answer:
        return f"""당신은 대학생의 학습을 돕는 AI 어시스턴트입니다.
아래 우선순위에 따라 답변하세요.

1순위: [강의자료 내용]에서 답을 찾아 답변하세요.
2순위: 강의자료에 없거나 내용이 부족하다면 AI 자신의 지식으로 완전하고 성실하게 답변하세요. 이 경우 답변 첫 문장을 반드시 아래 중 상황에 맞게 시작하세요:
  - 강의자료에 내용이 전혀 없는 경우: "강의자료에 해당 내용이 없어 AI 지식으로 답변드립니다."
  - 강의자료에 내용이 있지만 부족한 경우: "강의자료의 내용이 충분하지 않아 AI 지식으로 보완하여 답변드립니다."

페이지를 묻는 질문이라면 강의자료 내용의 페이지 표시를 참고하여 알려주세요.

답변 맨 끝에 실제로 활용한 출처만 아래 형식으로 표시하세요:
- 강의자료만으로 완전히 답변한 경우: [참고자료: 파일명1|파일명2]
- AI 지식을 조금이라도 활용한 경우: [참고자료: 파일명1|AI 답변] (강의자료도 참고했다면 파일명 포함)
- AI 지식만 활용한 경우: [참고자료: AI 답변]
실제로 내용을 참고하지 않은 파일은 절대 포함하지 마세요.
가능한 파일명: {filenames}

[강의자료 내용]
{context}

[이전 대화 내역]
{history_str}

사용자 질문: {content}

답변:"""
    return f"""당신은 대학생의 학습을 돕는 AI 어시스턴트입니다.
아래 우선순위에 따라 답변하세요.

1순위: [강의자료 내용]에서 답을 찾아 답변하세요.
2순위: 강의자료에 없다면 [이전 대화 내역]을 참고하여 답변하세요.
3순위: 둘 다 없으면 솔직하게 모른다고 말하세요.

페이지를 묻는 질문이라면 강의자료 내용의 페이지 표시를 참고하여 알려주세요.

답변에 실제로 활용한 강의자료가 있을 경우에만 답변 맨 끝에 아래 형식으로 추가하세요:
[참고자료: 파일명1|파일명2]
가능한 파일명: {filenames}
강의자료에서 답을 찾지 못했거나 활용하지 않은 경우에는 [참고자료:] 마커를 출력하지 마세요.

[강의자료 내용]
{context}

[이전 대화 내역]
{history_str}

사용자 질문: {content}

답변:"""


async def ask_question(session_id: int, content: str, document_ids: Optional[List[int]] = None, allow_ai_answer: bool = False):
    try:
        # 1. 과거 대화 내역 (현재 질문 저장 전에 조회)
        history = _load_history(session_id)
        if not allow_ai_answer:
            history = _filter_ai_history(history)

        # 2. 사용자 질문 저장
        logger.info(f"Saving user message to session {session_id}")
        _save_message(session_id, "USER", content)

        # 3. 쿼리 재작성 + 임베딩
        search_query = _rewrite_query(content, history)
        logger.info(f"Generating embedding for session {session_id}")
        query_vector = await _generate_embedding(search_query)

        # 4. 관련 청크 검색
        resolved_ids = _resolve_document_ids(session_id, document_ids)
        chunks = await get_relevant_chunks_with_sources(query_vector, resolved_ids) if resolved_ids else []
        context = _build_context(chunks)
        sources = _extract_sources(chunks)
        logger.info(f"Found {len(chunks)} relevant chunks for session {session_id}")

        # 5. 프롬프트 생성 및 답변
        history_str = "\n".join([f"{m['sender_type']}: {m['content']}" for m in history])
        filenames = "|".join(s['filename'] for s in sources)
        prompt = _build_prompt(context, history_str, content, filenames, allow_ai_answer)

        logger.info(f"Prompting {CHAT_MODEL} for session {session_id}")
        response = gemini_call(client.models.generate_content, model=CHAT_MODEL, contents=prompt)
        ai_answer, sources = _filter_used_sources(response.text, sources)

        # 6. AI 답변 저장
        logger.info(f"Saving AI response to session {session_id}")
        msg = _save_message(session_id, "AI", ai_answer, sources)
        return {"message": msg, "sources": sources}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in ask_question (session={session_id}): {e}")
        raise HTTPException(status_code=500, detail="AI 응답 생성 중 오류가 발생했습니다.")


async def ask_about_document(document_id: int, content: str, allow_ai_answer: bool = False) -> dict:
    try:
        # 1. 사용자 메시지 저장
        supabase.table("document_chat_messages").insert({
            "document_id": document_id,
            "sender_type": "USER",
            "content": content,
        }).execute()

        # 2. 대화 내역 로드
        history_res = supabase.table("document_chat_messages") \
            .select("sender_type, content") \
            .eq("document_id", document_id) \
            .order("created_at", desc=True) \
            .limit(HISTORY_LIMIT) \
            .execute()
        history = history_res.data[::-1]

        # 3. 쿼리 재작성 + 임베딩
        search_query = _rewrite_query(content, history)
        query_vector = await _generate_embedding(search_query)

        # 4. 관련 청크 검색
        chunks = await get_relevant_chunks_with_sources(query_vector, [document_id])
        context = _build_context(chunks)
        sources = _extract_sources(chunks)
        filename = sources[0]['filename'] if sources else '문서'

        history_str = "\n".join([
            f"{'사용자' if m['sender_type'] == 'USER' else 'AI'}: {m['content'][:300]}"
            for m in history
        ])

        if allow_ai_answer:
            prompt = f"""당신은 대학생의 학습을 돕는 AI 어시스턴트입니다.
아래 우선순위에 따라 답변하세요.

1순위: [문서 내용]에서 답을 찾아 답변하세요.
2순위: 문서에 없거나 내용이 부족하다면 AI 자신의 지식으로 완전하고 성실하게 답변하세요. 이 경우 답변 첫 문장을 반드시 아래 중 상황에 맞게 시작하세요:
  - 문서에 내용이 전혀 없는 경우: "문서에 해당 내용이 없어 AI 지식으로 답변드립니다."
  - 문서에 내용이 있지만 부족한 경우: "문서의 내용이 충분하지 않아 AI 지식으로 보완하여 답변드립니다."

[문서 내용]
{context}

[이전 대화 내역]
{history_str}

질문: {content}

답변:"""
        else:
            prompt = f"""당신은 대학생의 학습을 돕는 AI 어시스턴트입니다.
아래 [문서 내용]을 바탕으로 질문에 간결하게 답변하세요.
자료에 없는 내용은 솔직하게 모른다고 말하세요.

[문서 내용]
{context}

[이전 대화 내역]
{history_str}

질문: {content}

답변:"""

        response = gemini_call(client.models.generate_content, model=CHAT_MODEL, contents=prompt)
        answer = re.sub(r'\[이전 대화 내역\].*', '', response.text or "", flags=re.DOTALL).strip()

        # AI 지식 사용 여부 판단
        used_ai = allow_ai_answer and any(
            phrase in answer for phrase in ["AI 지식으로 답변드립니다", "AI 지식으로 보완하여"]
        )
        final_sources: list = []
        if used_ai:
            final_sources = [{"filename": "AI 답변", "category": "AI 답변"}]

        # 5. AI 답변 저장
        supabase.table("document_chat_messages").insert({
            "document_id": document_id,
            "sender_type": "AI",
            "content": answer,
        }).execute()

        return {"answer": answer, "sources": final_sources}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in ask_about_document (document_id={document_id}): {e}")
        raise HTTPException(status_code=500, detail="문서 질문 처리 중 오류가 발생했습니다.")


def delete_session(session_id: int) -> None:
    exists = supabase.table("chat_sessions").select("id").eq("id", session_id).execute()
    if not exists.data:
        raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")

    try:
        supabase.table("chat_messages").delete().eq("session_id", session_id).execute()
        supabase.table("chat_sessions").delete().eq("id", session_id).execute()
    except Exception as e:
        logger.error("채팅방 삭제 실패: %s", e)
        raise HTTPException(status_code=500, detail="채팅방 삭제 중 오류가 발생했습니다.")
