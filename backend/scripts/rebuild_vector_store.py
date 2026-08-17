"""
rebuild_vector_store.py — Dựng lại vector store bằng Voyage AI embedding API.

Vector store cũ nhúng bằng model KHÁC (sentence-transformers local trước đây,
Gemini embedding-001 giai đoạn 08/2026) KHÔNG dùng được với Voyage — mỗi
model là một không gian vector riêng, phải nhúng lại toàn bộ. Vì vậy script
này xóa collection cũ trước khi nạp toàn bộ chunk mới (đã nhúng xong bằng
Voyage) — lỗi giữa chừng thì vector store cũ vẫn còn nguyên, không bị phá.

Luồng xử lý (giữ nguyên logic parse + chunk cũ):
  data/raw/*.docx -> load_docx -> chunk_by_article
                  -> Voyage v1/embeddings (batch, input_type="document",
                     qua embedding_service)
                  -> ChromaDB collection.add(embeddings=[...], documents=[...],
                     ids=[...]) — vector truyền tường minh, KHÔNG để Chroma
                     tự nhúng.

Cach chay (tu backend/, can .env co VOYAGE_API_KEY):
  python scripts/rebuild_vector_store.py                 # build lai toan bo
  python scripts/rebuild_vector_store.py --resume        # tiep tuc sau khi loi/gian doan (dung cache vector)
  python scripts/rebuild_vector_store.py --save-chunks   # luu them data/processed/chunks.json
  python scripts/rebuild_vector_store.py --delay 30      # tang thoi gian cho giua cac batch
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Windows console mac dinh cp1252 khong in duoc tieng Viet
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Chay truc tiep "python scripts/rebuild_vector_store.py" van import duoc app/*
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATA_RAW_DIR = Path(os.getenv("DATA_RAW_DIR", "data/raw"))
VECTORSTORE_DIR = Path(os.getenv("VECTORSTORE_DIR", "vectorstore"))
COLLECTION_NAME = "quy_che"

# Voyage free tier CHƯA thêm phương thức thanh toán bị bóp về 3 request/phút
# (10K token/phút) — phải chờ ~20s giữa các batch, không thì 429 liên tục
# (embedding_service tự retry 2 lần, nhưng backoff 1-2s không đủ cho quota này)
DEFAULT_DELAY_SEC = 20.5
CHUNK_ADD_BATCH = 64
# File cache vector đã nhúng — cho phép --resume sau khi lỗi/gián đoạn 429
# mà không phải trả lại quota cho các batch đã xong
EMBED_CACHE_FILE = VECTORSTORE_DIR / ".embed_cache_v1.json"


def collect_source_files(raw_dir: Path) -> list[Path]:
    """Quét file quy chế trong data/raw (bỏ file tạm ~$ của Word)."""
    files = sorted(raw_dir.glob("*.docx")) + sorted(raw_dir.glob("*.pdf"))
    files = [f for f in files if not f.name.startswith("~$")]
    if not files:
        raise FileNotFoundError(
            f"Không tìm thấy file PDF/DOCX nào trong {raw_dir}/ — "
            "hãy copy file quy chế (DOCX) vào thư mục này trước.")
    return files


def _embed_cache_key(texts: list[str]) -> str:
    """Vân tay của (model + toàn bộ text) — đổi tài liệu/model là cache tự hết hạn."""
    import hashlib

    from app.core.config import settings
    h = hashlib.sha256(settings.VOYAGE_MODEL.encode())
    h.update(f":{len(texts)}:".encode())
    for t in texts:
        h.update(t.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def _load_embed_cache(key: str) -> list[list[float]] | None:
    """Đọc vector đã nhúng từ cache; None nếu không có/lỗi/khác key."""
    try:
        data = json.loads(EMBED_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("key") != key:
        return None
    return data.get("vectors", [])


def _save_embed_cache(key: str, vectors: list[list[float]]) -> None:
    """Ghi cache nguyên tử (file .tmp rồi replace) để lỗi giữa chừng không hỏng cache."""
    tmp = EMBED_CACHE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"key": key, "vectors": vectors}), encoding="utf-8")
    tmp.replace(EMBED_CACHE_FILE)


async def embed_all(texts: list[str], delay_sec: float, resume: bool) -> list[list[float]]:
    """Nhúng từng batch, log tiến độ + delay giữa các batch (rate-limit).

    Mỗi batch xong được ghi cache; khi lỗi/gián đoạn chạy lại --resume sẽ
    tiếp từ batch dở mà không gọi lại API cho phần đã nhúng.
    """
    from app.services.embedding_service import EMBED_BATCH_SIZE, get_embeddings

    n_batches = (len(texts) + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE
    cache_key = _embed_cache_key(texts)
    vectors: list[list[float]] = []
    if resume:
        cached = _load_embed_cache(cache_key)
        if cached:
            vectors = cached[:len(texts)]
            if len(vectors) >= len(texts):
                print(f"      Cache đủ {len(vectors)}/{len(texts)} chunk — bỏ qua gọi API")
                return vectors
            print(f"      [RESUME] Đã có {len(vectors)}/{len(texts)} chunk trong cache — "
                  f"tiếp từ batch {len(vectors) // EMBED_BATCH_SIZE + 1}/{n_batches}")
        else:
            print("      [RESUME] Không có cache hợp lệ — nhúng từ đầu")

    for i in range(len(vectors), len(texts), EMBED_BATCH_SIZE):
        batch = texts[i:i + EMBED_BATCH_SIZE]
        batch_no = i // EMBED_BATCH_SIZE + 1
        try:
            # input_type="document": nhúng chunk lúc BUILD index (khác "query"
            # lúc tìm kiếm — Voyage khuyến nghị phân biệt để tối ưu retrieval)
            vectors.extend(await get_embeddings(batch, input_type="document"))
        except BaseException as e:
            _save_embed_cache(cache_key, vectors)
            print(f"\n[LOI] Batch {batch_no}/{n_batches}: {type(e).__name__}: {e}")
            print(f"      Đã cache {len(vectors)}/{len(texts)} chunk — "
                  f"chạy lại với --resume để tiếp tục.")
            print("      Vector store cũ GIỮ NGUYÊN (chưa xóa collection).")
            raise
        done = min(i + EMBED_BATCH_SIZE, len(texts))
        print(f"      [{batch_no}/{n_batches}] đã nhúng {done}/{len(texts)} chunk")
        if done < len(texts):
            _save_embed_cache(cache_key, vectors)
            if delay_sec > 0:
                await asyncio.sleep(delay_sec)
    return vectors


def rebuild(files: list[Path], delay_sec: float, resume: bool = False) -> int:
    from src.ingestion.chunker import chunk_by_article
    from src.ingestion.loader import load_docx

    # 1) Parse + chunk (logic cũ — src/ingestion)
    print(f"[1/4] Parse {len(files)} file tài liệu tại {DATA_RAW_DIR}/ ...")
    parsed = []
    for f in files:
        if f.suffix.lower() == ".docx":
            p = load_docx(f)
            print(f"      {f.name}: {p.n_sections} sections, ~{p.tong_so_trang} trang")
            parsed.append(p)
        else:
            print(f"      [BO QUA] {f.name}: parser PDF chưa triển khai "
                  "(chuyển sang DOCX nếu có thể)")
    if not parsed:
        raise ValueError("Không có tài liệu DOCX nào để build index")

    docs = chunk_by_article(parsed)
    texts = [d.page_content for d in docs]
    metadatas = [d.metadata for d in docs]
    sizes = [len(t) for t in texts]
    print(f"      -> {len(docs)} chunks (min={min(sizes)} max={max(sizes)} "
          f"tb={sum(sizes) // len(sizes)} chars)")

    # 2) Nhúng bằng Voyage API (mang online — can VOYAGE_API_KEY)
    from app.core.config import settings
    print(f"[2/4] Nhúng {len(docs)} chunk bằng Voyage embedding API "
          f"({settings.VOYAGE_MODEL}, input_type=document) ...")
    t0 = time.time()
    vectors = asyncio.run(embed_all(texts, delay_sec, resume))
    dim = len(vectors[0])
    print(f"      Xong sau {time.time() - t0:.1f}s — vector {dim} chiều")

    # 3) Xóa collection cũ RỒI mới nạp (vector cũ khác không gian — phải xóa)
    print(f"[3/4] Xóa collection '{COLLECTION_NAME}' cũ và tạo mới ...")
    import chromadb

    client = chromadb.PersistentClient(path=str(VECTORSTORE_DIR))
    try:
        client.delete_collection(COLLECTION_NAME)
        print("      Đã xóa collection cũ")
    except Exception:
        print("      Chưa có collection cũ — tạo mới")

    # 4) Nạp chunk + vector tuong minh (KHONG de Chroma tu nhúng)
    print(f"[4/4] Nạp {len(docs)} chunk vào ChromaDB tại {VECTORSTORE_DIR}/ ...")
    collection = client.get_or_create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine",
                  "embedding_model": settings.VOYAGE_MODEL})
    ids = [f"quy_che_{i}" for i in range(len(docs))]
    for i in range(0, len(docs), CHUNK_ADD_BATCH):
        end = min(i + CHUNK_ADD_BATCH, len(docs))
        collection.add(ids=ids[i:end],
                       embeddings=vectors[i:end],
                       documents=texts[i:end],
                       metadatas=metadatas[i:end])
        print(f"      {end}/{len(docs)} chunks")

    return len(docs)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Rebuild vector store quy che bang Voyage embedding API")
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY_SEC,
                    help=f"Giây chờ giữa các batch embed (mặc định {DEFAULT_DELAY_SEC})")
    ap.add_argument("--resume", action="store_true",
                    help="Tiếp tục từ cache vector (.embed_cache_v1.json) sau khi lỗi/gián đoạn")
    ap.add_argument("--save-chunks", action="store_true",
                    help="Lưu thêm chunks ra data/processed/chunks.json để kiểm tra")
    args = ap.parse_args()

    voyage_key = os.getenv("VOYAGE_API_KEY", "")
    if not voyage_key or "PASTE" in voyage_key:
        print("[LOI] Chưa có VOYAGE_API_KEY trong backend/.env — embedding Voyage "
              "bắt buộc phải có key (tạo tại dash.voyageai.com/api-keys).")
        sys.exit(1)

    files = collect_source_files(DATA_RAW_DIR)
    n = rebuild(files, args.delay, resume=args.resume)
    print(f"\nHoàn tất: {n} chunks trong {VECTORSTORE_DIR}/ "
          f"(collection '{COLLECTION_NAME}', nhúng bằng Voyage AI)")
    print("Nhớ commit thư mục vectorstore/ để deploy có index mới.")
    try:
        EMBED_CACHE_FILE.unlink(missing_ok=True)
    except OSError:
        pass

    if args.save_chunks:
        from src.ingestion.chunker import save_chunks
        from src.ingestion.loader import load_docx
        from src.ingestion.chunker import chunk_by_article

        docs = chunk_by_article([load_docx(f) for f in files
                                 if f.suffix.lower() == ".docx"])
        save_chunks(docs, Path("data/processed/chunks.json"))
        print(f"Đã lưu {len(docs)} chunks -> data/processed/chunks.json")


if __name__ == "__main__":
    main()
