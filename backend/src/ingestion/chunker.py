"""
chunker.py — Buoc 2 roadmap: Chia nho tai lieu theo don vi logic.

Nguyen tac (muc 7 project.md):
- Moi DIEU la 1 chunk; dieu dai thi chia nho theo khoan/diem.
- Khong cat giua cau; chunk ~300-500 tokens, overlap ~50-100 tokens.
  (Tieng Viet: uoc tinh 1 token ~ 1.7 ky tu)
- Luu metadata cho moi chunk: phan, chuong, chuong_con, muc, trich,
  dieu, ten_dieu, khoan, so_trang, nguon.

Diem xu ly thuc te cua tai lieu (So tay sinh vien ICTU):
- So Dieu danh lai tu 1 trong moi van ban con (muc A/B/C/D...) -> metadata
  kem theo muc de phan biet "Dieu 1" cua quy che nao.
- Mot quy che co the keo dai qua nhieu Chuong (VD: hoc bong: Dieu 1-10 o
  Chuong II, Dieu 11-22 o Chuong III/IV/VI) -> section bi mat muc se duoc
  ke thua muc cua section truoc do.
- Section khong co Dieu (gioi thieu, tieu de) duoc gop vao chunk lien truoc
  neu nho, hoac tach thanh chunk rieng co header lam ngu canh.

Dau ra: list[Document] (LangChain) san sang cho embedding.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from langchain_core.documents import Document

from src.ingestion.loader import ParsedDocument, Section

# Uoc tinh so ky tu / token cho tieng Viet
CHARS_PER_TOKEN = 1.7

MIN_CHUNK_CHARS = 280     # ~165 tokens — chunk ngan hon se duoc gop
MAX_CHUNK_CHARS = 850     # ~500 tokens — chunk dai hon se chia theo khoan
TARGET_CHUNK_CHARS = 680  # ~400 tokens — muc tieu khi gop nhieu khoan
OVERLAP_CHARS = 150       # ~88 tokens — overlap khi chia dieu dai

# Đầu khoản: "1." / "2." (mức 1) và "a)" / "b." (mức 2, chỉ tách trong bảng)
RE_KHOAN_1 = re.compile(r"^\s*(\d{1,2})\.\s+\S")
RE_KHOAN_2 = re.compile(r"^\s*([a-d])\)\s+\S")

# Viết tắt trong sổ tay -> dạng đầy đủ. Chunk chỉ dùng dạng tắt sẽ được chú
# thích thêm dạng đầy đủ để embedding khớp với câu hỏi dùng tên đầy đủ
# (VD: hỏi "học bổng khuyến khích học tập" nhưng Điều 8 chỉ viết "HB KKHT").
ABBREVIATIONS = [
    ("HB KKHT", "học bổng khuyến khích học tập"),
    ("HSSV", "học sinh, sinh viên"),
    ("CTHSSV", "công tác học sinh sinh viên"),
    ("KTX", "ký túc xá"),
]


def _annotate_abbreviations(text: str) -> str:
    """Thêm chú thích viết tắt ngay sau điều có xuất hiện dạng tắt."""
    notes = [f"{full} ({abb})" for abb, full in ABBREVIATIONS
             if abb in text and full not in text.lower()]
    return f"{text}\n[Chú thích viết tắt: {'; '.join(notes)}]" if notes else text

MAX_CONTEXT_CHARS = 350  # tối đa ký tự header ngữ cảnh nhồi vào chunk


def _header_context(s: Section, extra: str = "") -> str:
    """Header ngữ cảnh: Phần/Chương/Mục để LLM biết chunk thuộc quy chế nào."""
    parts = [x for x in (s.phan, s.chuong, s.chuong_con, s.muc, s.trich) if x]
    if s.dieu:
        label = s.dieu if not s.ten_dieu else f"{s.dieu}. {s.ten_dieu}"
        parts.append(label)
    if extra:
        parts.append(extra)
    header = " > ".join(parts)
    if len(header) > MAX_CONTEXT_CHARS:
        header = header[:MAX_CONTEXT_CHARS] + "…"
    return header


def _split_into_units(text: str) -> list[tuple[str, str]]:
    """Tách nội dung (sau dòng 'Điều N.') thành [(khoan_label, text)].

    - Xong dòng bảng "[BẢNG]" thì mức 2 (a) b) c)) cũng được coi là khoản.
    - Không cắt giữa câu: chỉ tách tại đầu dòng khớp RE_KHOAN_*.
    """
    lines = text.split("\n")
    units: list[tuple[str, str]] = []
    cur_label, cur_lines = "", []
    in_table = False

    for line in lines:
        if line.strip() == "[BẢNG]":
            in_table = True
        m = RE_KHOAN_1.match(line) or (RE_KHOAN_2.match(line) if in_table else None)
        if m:
            if cur_lines:
                units.append((cur_label, "\n".join(cur_lines)))
            label = m.group(1)
            cur_label = f"khoản {label}" if label.isdigit() else f"điểm {label}"
            cur_lines = [line]
        else:
            cur_lines.append(line)
    if cur_lines:
        units.append((cur_label, "\n".join(cur_lines)))
    return units


def _merge_units(units: list[tuple[str, str]], header: str, s: Section) -> list[str]:
    """Gộp các khoản thành chunk ~TARGET_CHUNK_CHARS; chunk đầu kèm header."""
    chunks: list[str] = []
    cur, cur_label = "", ""
    for label, text in units:
        text = text.strip()
        if not text:
            continue
        candidate = (cur + "\n" + text).strip() if cur else text
        if cur and len(candidate) > TARGET_CHUNK_CHARS:
            chunks.append(cur)
            cur, cur_label = text, label
        else:
            cur, cur_label = candidate, label
    if cur:
        chunks.append(cur)

    out = []
    for i, body in enumerate(chunks):
        if i == 0:
            out.append(f"{header}\n{body}")
        else:
            out.append(f"{header} (tiếp theo)\n{body}")
    return out


def _chunk_dieu(s: Section) -> list[dict]:
    """1 Điều -> 1 hoặc nhiều chunk. Trả về list[{text, khoan, ...meta}]."""
    s.text = _annotate_abbreviations(s.text)   # chu thich HB KKHT, HSSV...
    header = _header_context(s)
    lines = s.text.split("\n", 1)
    body = lines[1].strip() if len(lines) > 1 else ""
    meta = dict(phan=s.phan, chuong=s.chuong, chuong_con=s.chuong_con,
                muc=s.muc, trich=s.trich, dieu=s.dieu, ten_dieu=s.ten_dieu,
                so_trang=s.so_trang, nguon=s.nguon)

    if len(s.text) <= MAX_CHUNK_CHARS:
        return [{"text": f"{header}\n{s.text}", "khoan": "", **meta}]

    units = _split_into_units(body)
    if len(units) <= 1:
        # Điều dài nhưng không tách được theo khoản (VD: toàn văn bản dài)
        # -> cắt cứng theo đoạn văn, gối đầu OVERLAP_CHARS
        out, start = [], 0
        while start < len(body):
            end = min(start + TARGET_CHUNK_CHARS, len(body))
            if end < len(body):
                cut = body.rfind("\n", start + TARGET_CHUNK_CHARS // 2, end)
                if cut > start:
                    end = cut
            out.append(f"{header}\n{body[start:end].strip()}")
            start = len(body) if end >= len(body) else max(end - OVERLAP_CHARS, start + 1)
        return [{"text": t, "khoan": "", **meta} for t in out]

    out = []
    for text in _merge_units(units, header, s):
        labels = re.findall(r"^(?:khoản|điểm) ([\w]+)", text, re.M)
        khoan = (", ".join(dict.fromkeys(labels)))[:60]
        out.append({"text": text, "khoan": khoan, **meta})
    return out


def _chunk_section(s: Section) -> list[dict]:
    """Section không có Điều (tiêu đề/giới thiệu) -> chunk riêng kèm header."""
    header = _header_context(s)
    return [{"text": f"{header}\n{s.text}", "khoan": "",
             "phan": s.phan, "chuong": s.chuong, "chuong_con": s.chuong_con,
             "muc": s.muc, "trich": s.trich, "dieu": "", "ten_dieu": "",
             "so_trang": s.so_trang, "nguon": s.nguon}]


def _chunk_small_section(s: Section, prev: Document | None) -> Document | None:
    """Gộp section nhỏ không Điều vào cuối chunk liền trước (giữ ngữ cảnh)."""
    if prev is None:
        return None
    header = _header_context(s)
    tail = f"\n\n{header}\n{s.text}"
    if len(prev.page_content) + len(tail) > MAX_CHUNK_CHARS + 200:
        return None
    prev.page_content += tail
    return prev


def _enforce_max_size(doc: Document) -> list[Document]:
    """Chunk vượt MAX_CHUNK_CHARS -> cắt tiếp theo đoạn văn, gối đầu overlap.

    Áp dụng cho cả chunk giới thiệu lớn và khoản chứa bảng dài.
    """
    text = doc.page_content
    if len(text) <= MAX_CHUNK_CHARS + 200:
        return [doc]
    header_line = text.split("\n", 1)[0]   # dòng header ngữ cảnh đầu tiên
    out: list[Document] = []
    start = 0
    while start < len(text):
        end = min(start + TARGET_CHUNK_CHARS, len(text))
        if end < len(text):
            cut = text.rfind("\n", start + TARGET_CHUNK_CHARS // 2, end)
            if cut > start:
                end = cut
        piece = text[start:end].strip()
        if start > 0 and piece:
            piece = f"{header_line} (tiếp theo)\n{piece}"
        if piece:
            out.append(Document(page_content=piece, metadata=dict(doc.metadata)))
        start = len(text) if end >= len(text) else max(end - OVERLAP_CHARS, start + 1)
    return out


def chunk_by_article(parsed_docs: list[ParsedDocument]) -> list[Document]:
    """Chuyển các ParsedDocument thành list[Document] sẵn sàng cho embedding."""
    raw_docs: list[Document] = []

    for doc in parsed_docs:
        last_muc, last_trich, last_dieu_n = "", "", 0   # ke thua muc trong 1 quy che
        for s in doc.sections:
            if s.muc:
                last_muc, last_trich = s.muc, s.trich
            m = re.match(r"Điều\s+(\d+)", s.dieu) if s.dieu else None
            dieu_n = int(m.group(1)) if m else 0
            if s.dieu:
                if not s.muc and last_muc and dieu_n == last_dieu_n + 1:
                    # Dieu khong muc nhung danh so lien tiep -> tiep tuc cung
                    # quy che (VD: hoc bong Dieu 11-22 o chuong khac muc)
                    s.muc, s.trich = last_muc, last_trich
                elif not s.muc:
                    # Dieu mo dau quy che moi khong co muc heading -> ngung
                    last_muc = ""
                last_dieu_n = dieu_n
            elif last_muc and not s.muc:
                # Dong tieu de giua quy che (VD: tieu de chuong con cua cung
                # quy che hoc bong) — giu muc de chunk gioi thieu co ngu canh
                s.muc, s.trich = last_muc, last_trich

            if s.dieu:
                for c in _chunk_dieu(s):
                    raw_docs.append(Document(page_content=c.pop("text"),
                                             metadata=c))
            elif len(s.text) < MIN_CHUNK_CHARS and raw_docs:
                merged = _chunk_small_section(s, raw_docs[-1])
                if merged is None:
                    raw_docs.extend(
                        Document(page_content=c.pop("text"), metadata=c)
                        for c in _chunk_section(s))
            else:
                raw_docs.extend(
                    Document(page_content=c.pop("text"), metadata=c)
                    for c in _chunk_section(s))

    # Bước cuối: cắt mọi chunk vượt kích thước (bảng dài, phần giới thiệu)
    documents: list[Document] = []
    for d in raw_docs:
        documents.extend(_enforce_max_size(d))
    return documents


def save_chunks(documents: list[Document], out_path: str | Path) -> None:
    """Lưu chunks ra JSON (data/processed) để kiểm tra/debug không cần embed."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [{"text": d.page_content, "metadata": d.metadata} for d in documents]
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                        encoding="utf-8")


if __name__ == "__main__":
    import sys

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    from src.ingestion.loader import load_docx

    raw_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw")
    files = sorted(raw_dir.glob("*.docx")) + sorted(raw_dir.glob("*.pdf"))
    parsed = [load_docx(f) for f in files if not f.name.startswith("~$")]
    docs = chunk_by_article(parsed)

    print(f"So file: {len(parsed)} | So chunk: {len(docs)}")
    sizes = [len(d.page_content) for d in docs]
    print(f"Kich thuoc chunk: min={min(sizes)} max={max(sizes)} "
          f"tb={sum(sizes)//len(sizes)} chars")
    print()
    print("=== 5 chunk mau ===")
    for d in docs[10:15]:
        m = d.metadata
        meta = " | ".join(x for x in (m["phan"], m["chuong"], m["muc"][:40],
                                      m["dieu"], m["khoan"]) if x)
        print(f"[{meta} | tr.~{m['so_trang']}] ({len(d.page_content)} chars)")
        print(f"  {d.page_content[:150]}...")
        print()

    out = Path("data/processed/chunks.json")
    save_chunks(docs, out)
    print(f"Da luu {len(docs)} chunks -> {out}")
