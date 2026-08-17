"""
retriever.py — Truy van vector store bang chromadb client truc tiep.

Diem cot loi: KHONG bao gio dinh kem embedding function vao collection —
moi thao tac add/query deu truyen vector tuong minh (query_embeddings /
embeddings). Chroma tu nhúng van ban se tai model ONNX ngam -> RAM bat tang,
ma pipeline nay dung embedding Voyage AI API goi qua
app/services/embedding_service.py.

Vector store dung san tai VECTORSTORE_DIR (da commit trong repo) — duoc
nhúng bang Voyage AI (VOYAGE_MODEL, mac dinh voyage-4). Doi model embedding
la phai chay lai scripts/rebuild_vector_store.py (moi model = 1 khong gian
vector rieng).

Cach dung:
    collection = get_collection()
    result = collection.query(query_embeddings=[vec], n_results=5)
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache

from dotenv import load_dotenv

from app.core.config import settings

load_dotenv()

logger = logging.getLogger(__name__)

VECTORSTORE_DIR = os.getenv("VECTORSTORE_DIR", "vectorstore")
# Model embedding duy nhất — đọc qua settings để trùng 1 nguồn cấu hình với
# embedding_service.py (Voyage). Đổi model = phải rebuild vector store.
EMBEDDING_MODEL = os.getenv("VOYAGE_MODEL", "") or settings.VOYAGE_MODEL
RETRIEVER_TOP_K = int(os.getenv("RETRIEVER_TOP_K", "5"))
COLLECTION_NAME = "quy_che"


@lru_cache(maxsize=1)
def get_client():
    """Mo ChromaDB persist dir (singleton — chi mo 1 lan cho moi process).

    KHONG truyen embedding_function: moi thao tac truyen vector tuong minh,
    tranh viec Chroma ngam tai model nhúng local (RAM).
    """
    import chromadb

    if not os.path.isdir(VECTORSTORE_DIR):
        raise FileNotFoundError(
            f"Chua co vector store tai '{VECTORSTORE_DIR}/'. "
            "Dat file quy che (DOCX) vao data/raw/ roi chay: "
            "python scripts/rebuild_vector_store.py")
    return chromadb.PersistentClient(path=VECTORSTORE_DIR)


def get_collection():
    """Tra ve collection quy_che. Loi ro khi chua co collection/index.

    Kiem tra them: collection duoc build bang model embedding nao (metadata
    'embedding_model' do rebuild_vector_store.py ghi). Doi model ma quen
    rebuild thi bao loi ngay — vector 2 model khac khong gian, query se ra
    ket qua sai lech thay vi bao loi.

    rebuild_vector_store.py LUON ghi metadata 'embedding_model', nen mot
    collection KHONG co metadata nay chac chan la index tien-Voyage (Gemini /
    sentence-transformers, 768 chieu, space l2) — phai bi chan va yeu cau
    rebuild, KHONG duoc mo (khong thi no chi no loi lech dimension 768!=1024
    o buoc query, khong co thong bao huong dan nao).
    """
    client = get_client()
    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception as e:
        raise FileNotFoundError(
            f"Chua co collection '{COLLECTION_NAME}' trong vector store "
            f"({VECTORSTORE_DIR}/) — chay: python scripts/rebuild_vector_store.py"
        ) from e
    built_with = (collection.metadata or {}).get("embedding_model")
    if built_with != EMBEDDING_MODEL:
        if built_with:
            huong_dan = (f"hoac doi bien moi truong VOYAGE_MODEL ve '{built_with}' "
                         f"neu index duoc build dung model do")
        else:
            huong_dan = "khong co metadata 'embedding_model' — index tien-Voyage, phai nhúng lai"
        raise FileNotFoundError(
            f"Vector store duoc nhúng bang model khac VOYAGE_MODEL hien tai "
            f"('{EMBEDDING_MODEL}'): {huong_dan}. Moi model la mot khong gian "
            f"vector rieng, khong dung chung duoc. Chay lai: "
            f"python scripts/rebuild_vector_store.py")
    return collection


if __name__ == "__main__":
    # Test nhanh retrieval — can chay tu backend/ va co .env voi key Voyage:
    #   python -m src.rag.retriever "cau hoi"
    import asyncio
    import sys

    from app.services.embedding_service import get_embedding

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    q = " ".join(sys.argv[1:]) or "Điều kiện xét học bổng khuyến khích học tập?"
    print(f"Truy van: {q}\n")
    vec = asyncio.run(get_embedding(q, input_type="query"))
    collection = get_collection()
    result = collection.query(query_embeddings=[vec], n_results=5,
                              include=["documents", "metadatas", "distances"])
    for i, (doc, meta, dist) in enumerate(zip(
            result["documents"][0], result["metadatas"][0],
            result["distances"][0]), 1):
        src = ", ".join(str(x) for x in (meta.get("muc", "")[:55],
                                         meta.get("dieu", ""),
                                         meta.get("khoan", "")) if x)
        print(f"[{i}] {src} | tr.~{meta.get('so_trang')} | dist={dist:.3f}")
        print(f"    {doc[:160]}...")
        print()
