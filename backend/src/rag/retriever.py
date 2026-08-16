"""
retriever.py — Buoc 3 roadmap: Cau hinh retriever.

- Mo lai ChromaDB tu VECTORSTORE_DIR (cung embedding model da dung khi build).
- Similarity search voi top-k = RETRIEVER_TOP_K (mac dinh 5).
- Tuy chon: MMR de tranh trung lap ngu canh (search_type="mmr").

Cach dung:
    vs = get_vectorstore()
    retriever = get_retriever(vs, top_k=5, use_mmr=True)
    docs = retriever.invoke("cau hoi")
"""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

VECTORSTORE_DIR = os.getenv("VECTORSTORE_DIR", "vectorstore")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL",
                            "bkai-foundation-models/vietnamese-bi-encoder")
RETRIEVER_TOP_K = int(os.getenv("RETRIEVER_TOP_K", "5"))
COLLECTION_NAME = "quy_che"


@lru_cache(maxsize=1)
def get_vectorstore():
    """Mo ChromaDB da persist (singleton — chi tai 1 lan cho moi process)."""
    from langchain_community.vectorstores import Chroma

    from src.ingestion.build_index import get_embeddings

    if not os.path.isdir(VECTORSTORE_DIR):
        raise FileNotFoundError(
            f"Chua co vector store tai '{VECTORSTORE_DIR}/'. "
            "Chay: python -m src.ingestion.build_index"
        )
    return Chroma(collection_name=COLLECTION_NAME,
                  embedding_function=get_embeddings(),
                  persist_directory=VECTORSTORE_DIR)


def get_retriever(top_k: int = RETRIEVER_TOP_K, use_mmr: bool = True,
                  fetch_k: int = 20):
    """Tra ve retriever: similarity top-k, tuy chon MMR chong trung lap.

    MMR: lay fetch_k ket qua similarity, chon loc top_k ket qua da dang nhat —
    tranh truong hop 5 chunk tra ve deu la cac phan trung cua cung 1 dieu.
    """
    vs = get_vectorstore()
    if use_mmr:
        return vs.as_retriever(search_type="mmr",
                               search_kwargs={"k": top_k, "fetch_k": fetch_k})
    return vs.as_retriever(search_type="similarity",
                           search_kwargs={"k": top_k})


if __name__ == "__main__":
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    q = " ".join(sys.argv[1:]) or "Điều kiện xét học bổng khuyến khích học tập?"
    print(f"Truy van: {q}\n")
    retriever = get_retriever()
    for i, d in enumerate(retriever.invoke(q), 1):
        m = d.metadata
        src = ", ".join(x for x in (m.get("muc", "")[:55], m.get("dieu", ""),
                                    m.get("khoan", "")) if x)
        print(f"[{i}] {src} | tr.~{m.get('so_trang')} ({len(d.page_content)} chars)")
        print(f"    {d.page_content[:160]}...")
        print()
