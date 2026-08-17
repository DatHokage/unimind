Dat file PDF/DOCX quy che moi vao day roi chay (tu backend/, can VOYAGE_API_KEY trong .env):
  python scripts/rebuild_vector_store.py
  python scripts/rebuild_vector_store.py --resume   # tiep tuc neu loi/gian doan giua chung

(Lenh cu `python -m src.ingestion.build_index` van chay duoc — shim tu chuyen sang script moi.)
