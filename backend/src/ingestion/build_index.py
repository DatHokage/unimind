"""
build_index.py — Buoc 3 roadmap: Build vector store (chay offline, khong can API key).

Luong xu ly:
  data/raw/*.docx|pdf  -> loader -> chunker -> embedding (local) -> ChromaDB

Cach chay:
  python -m src.ingestion.build_index            # build lai toan bo (xoa index cu)
  python -m src.ingestion.build_index --save-chunks  # luu them data/processed/chunks.json

Re-index: khi quy che cap nhat, chi can dat file moi vao data/raw/ va chay lai
lenh tren — index cu bi xoa va build lai tu dau.

Luu y: Embedding chay local 100% (sentence-transformers), chi tai model lan dau.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

# Windows console mac dinh cp1252 khong in duoc tieng Viet
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
import os

load_dotenv()

DATA_RAW_DIR = Path(os.getenv("DATA_RAW_DIR", "data/raw"))
VECTORSTORE_DIR = Path(os.getenv("VECTORSTORE_DIR", "vectorstore"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL",
                            "bkai-foundation-models/vietnamese-bi-encoder")
COLLECTION_NAME = "quy_che"
BATCH_SIZE = 32  # ChromaDB gioi han 41666 ops/request; 32 chunk x 3 op = an toan


def get_embeddings(model_name: str = EMBEDDING_MODEL):
    """Tao embedding chay local qua sentence-transformers."""
    from langchain_community.embeddings import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=model_name,
        encode_kwargs={"normalize_embeddings": True, "batch_size": 32},
    )


def collect_source_files(raw_dir: Path) -> list[Path]:
    """Quet file quy che trong data/raw (bo file tam ~$ cua Word)."""
    files = sorted(raw_dir.glob("*.docx")) + sorted(raw_dir.glob("*.pdf"))
    files = [f for f in files if not f.name.startswith("~$")]
    if not files:
        raise FileNotFoundError(
            f"Khong tim thay file PDF/DOCX nao trong {raw_dir}/ — "
            "hay copy file quy che vao thu muc nay truoc."
        )
    return files


def build_index(files: list[Path]) -> int:
    """Toan bo pipeline: load -> chunk -> embed -> luu ChromaDB. Tra ve so chunk."""
    from src.ingestion.loader import load_docx
    from src.ingestion.chunker import chunk_by_article

    # 1) Parse + chunk
    print(f"[1/3] Parse {len(files)} file tai lieu...")
    parsed = []
    for f in files:
        if f.suffix.lower() == ".docx":
            p = load_docx(f)
            print(f"      {f.name}: {p.n_sections} sections, "
                  f"~{p.tong_so_trang} trang")
            parsed.append(p)
        elif f.suffix.lower() == ".pdf":
            # PDF chua duoc ho tro parse cau truc (tai lieu hien tai la DOCX)
            print(f"      [BO QUA] {f.name}: parser PDF chua trien khai "
                  "(chuyen sang DOCX neu co the)")
    if not parsed:
        raise ValueError("Khong co tai lieu DOCX nao de build index")

    docs = chunk_by_article(parsed)
    print(f"      -> {len(docs)} chunks")

    # 2) Embedding (local)
    print(f"[2/3] Tai embedding model: {EMBEDDING_MODEL} ...")
    t0 = time.time()
    embeddings = get_embeddings()
    print(f"      Model san sang sau {time.time() - t0:.1f}s")

    # 3) Luu ChromaDB (xoa index cu truoc -> re-index sach)
    print(f"[3/3] Luu vector store tai {VECTORSTORE_DIR}/ ...")
    if VECTORSTORE_DIR.exists():
        shutil.rmtree(VECTORSTORE_DIR)

    from langchain_community.vectorstores import Chroma

    # add_documents chia batch nho de tranh gioi han request cua Chroma
    vs = Chroma(collection_name=COLLECTION_NAME,
                embedding_function=embeddings,
                persist_directory=str(VECTORSTORE_DIR))
    for i in range(0, len(docs), BATCH_SIZE):
        vs.add_documents(docs[i:i + BATCH_SIZE])
        done = min(i + BATCH_SIZE, len(docs))
        if done % 128 == 0 or done == len(docs):
            print(f"      {done}/{len(docs)} chunks")

    return len(docs)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build vector store quy che")
    ap.add_argument("--save-chunks", action="store_true",
                    help="Luu them chunks ra data/processed/chunks.json")
    args = ap.parse_args()

    files = collect_source_files(DATA_RAW_DIR)
    n = build_index(files)
    print(f"\nHoan tat: {n} chunks trong {VECTORSTORE_DIR}/ "
          f"(collection '{COLLECTION_NAME}')")

    if args.save_chunks:
        from src.ingestion.loader import load_docx
        from src.ingestion.chunker import chunk_by_article, save_chunks
        docs = chunk_by_article([load_docx(f) for f in files
                                 if f.suffix.lower() == ".docx"])
        save_chunks(docs, Path("data/processed/chunks.json"))
        print(f"Da luu {len(docs)} chunks -> data/processed/chunks.json")

    # Test nhanh retrieval khong can embed lai
    print("\nKiem tra nhanh: truy van 'Sinh vien bi cam thi khi nao?'")
    from langchain_community.vectorstores import Chroma

    vs = Chroma(collection_name=COLLECTION_NAME,
                embedding_function=get_embeddings(),
                persist_directory=str(VECTORSTORE_DIR))
    hits = vs.similarity_search("Sinh viên bị cấm thi trong trường hợp nào?", k=3)
    for i, d in enumerate(hits, 1):
        m = d.metadata
        src = ", ".join(x for x in (m.get("muc", "")[:50], m.get("dieu", ""),
                                    m.get("khoan", "")) if x)
        print(f"  [{i}] {src} | tr.~{m.get('so_trang')}")
        print(f"      {d.page_content[:120]}...")


if __name__ == "__main__":
    main()
