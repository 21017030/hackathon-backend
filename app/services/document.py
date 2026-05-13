# 이 파일은 하위 호환성을 위해 유지합니다.
# 실제 구현은 document_storage.py와 document_rag.py로 분리되어 있습니다.
from app.services.document_storage import (
    validate_file,
    upload_document,
    get_document_view,
    get_documents_by_user,
    get_documents_by_category,
    delete_document,
    ALLOWED_EXTENSIONS,
    CONTENT_TYPES,
    MAGIC_NUMBERS,
)
from app.services.document_rag import process_document_rag
