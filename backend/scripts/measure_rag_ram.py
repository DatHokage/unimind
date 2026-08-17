"""
measure_rag_ram.py — Đo RAM của pipeline RAG để xác nhận chạy được trên
Render free tier 512MB (không còn tải model embedding local).

Cach chay (tu backend/):
  python scripts/measure_rag_ram.py
  python scripts/measure_rag_ram.py --query "Sinh viên bị cấm thi khi nào?"

Không cần key LLM: embedding được MÔ PHỎNG bằng vector giả — phép đo chỉ
quan tâm RAM của phía server (mở ChromaDB + truy vấn), không quan tâm nội
dung câu trả lời. Muốn đo cả lúc trả lời thật thì thêm --live (cần
VOYAGE_API_KEY + 1 key LLM; --live trả lời thật qua LLM OpenRouter
(fallback Gemini).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import psutil
except ImportError:
    print("Cần psutil để đo RAM: pip install psutil")
    sys.exit(1)

process = psutil.Process()


def rss_mb() -> float:
    return process.memory_info().rss / (1024 * 1024)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Do RAM pipeline RAG")
    ap.add_argument("--query", default="Sinh viên bị cấm thi khi nào?",
                    help="Câu hỏi dùng để truy vấn vector store")
    ap.add_argument("--live", action="store_true",
                    help="Gọi pipeline thật (embed + LLM) — cần API key")
    args = ap.parse_args()

    os.environ["RAG_WARMUP"] = "0"

    baseline = rss_mb()
    print(f"RAM trước khi import:        {baseline:7.1f} MB")

    from app.main import app  # noqa: F401  (đo cả app FastAPI + ORM)
    after_app = rss_mb()
    print(f"Sau khi import app FastAPI:  {after_app:7.1f} MB")

    from app.services.rag_service import is_configured, rag_status, warmup
    print(f"rag_status: {rag_status()} | is_configured: {is_configured()}")

    warmup()  # mở ChromaDB (nếu vectorstore chưa build thì bỏ qua)
    after_chroma = rss_mb()
    print(f"Sau warmup (mở ChromaDB):    {after_chroma:7.1f} MB")

    if not args.live:
        # Mô phỏng truy vấn: vector giả (voyage-4 = 1024 chiều), KHÔNG
        # gọi API — chỉ đo RAM phía server khi ChromaDB thực hiện query.
        fake_vector = [0.01] * 1024
        from src.rag.retriever import get_collection
        try:
            result = get_collection().query(query_embeddings=[fake_vector],
                                            n_results=5,
                                            include=["documents", "metadatas"])
            n = len(result.get("documents", [[]])[0])
            after_query = rss_mb()
            print(f"Sau query ChromaDB ({n} hits): {after_query:7.1f} MB")
        except FileNotFoundError as e:
            print(f"[BO QUA query] {e}")

    else:
        import asyncio
        from app.services.rag_service import answer_regulation_question
        r = asyncio.run(answer_regulation_question(args.query))
        print(f"Câu trả lời ({r['provider']}/{r['model']}): {r['answer'][:200]}...")
        print(f"Sau pipeline trả lời thật:   {rss_mb():7.1f} MB")

    print(f"\nTăng thêm do RAG: {rss_mb() - baseline:+.1f} MB "
          f"(tổng {rss_mb():.1f} MB)")
    print("Render free tier = 512 MB. Không tải model local nên pipeline này "
          "chỉ tốn RAM cho ChromaDB mở file vector store.")


if __name__ == "__main__":
    main()
