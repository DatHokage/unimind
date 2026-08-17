"""
chain.py — Helpers dinh dang cho pipeline RAG (khong con LCEL/LangChain).

Pipeline hien tai: app/services/rag_service.py dieu phoi
    question -> Gemini embedding API -> ChromaDB (query_embeddings tuong minh)
    -> format_context + SYSTEM_PROMPT (src/rag/prompts.py)
    -> llm_service.call_llm_text (Gemini -> OpenRouter fallback)

Module nay chi giu cac buoc dinh dang van ban: ghep ngu canh, dinh dang
sources, don dep cau tra loi. Luu y: khong con ham ask()/build_chain() —
logic fallback LLM da chuyen thanh httpx thuan trong app/services/llm_service.py.
"""
from __future__ import annotations

import re

__all__ = ["format_context", "format_sources", "clean_answer", "strip_markdown"]


def format_context(texts: list[str]) -> str:
    """Ghep cac chunk thanh ngu canh cho prompt (header da co san trong chunk)."""
    return "\n\n".join(f"[Đoạn {i}]\n{t}" for i, t in enumerate(texts, 1))


def format_sources(texts: list[str], metadatas: list[dict]) -> list[dict]:
    """Dinh danh sources tu metadata chunk (loai trung lap).

    Khop dung cau truc RegulationSource trong app/schemas/ai.py.
    """
    sources, seen = [], set()
    for text, m in zip(texts, metadatas):
        key = (m.get("muc", ""), m.get("dieu", ""), m.get("khoan", ""),
               text[:60])
        if key in seen:
            continue
        seen.add(key)
        sources.append({
            "phan": m.get("phan", ""),
            "chuong": m.get("chuong", ""),
            "chuong_con": m.get("chuong_con", ""),
            "muc": m.get("muc", ""),
            "trich": m.get("trich", ""),
            "dieu": m.get("dieu", ""),
            "ten_dieu": m.get("ten_dieu", ""),
            "khoan": m.get("khoan", ""),
            "so_trang": m.get("so_trang", 0) or 0,
            "nguon": m.get("nguon", ""),
            "text": text,
        })
    return sources


# Nhac nho "template" cua model :free hay xuat hien o cuoi cau tra loi
# (vi du Gemini free tier: "Ghi chu: ...", "Nguon: ...", "Translated by ...")
# — cat bo vi khong thuoc noi dung tra loi. Chi ap dung cho dong cuoi.
_NOTE_RE = re.compile(
    r"\n\s*(Ghi chu|Lưu ý|Note|Chú thích|Nguồn|Nguon|Tai lieu tham khao|"
    r"Xem them|Dich boi|Translated|Generated|Mien phi)\s*[:\.\-]?\s*.*$",
    re.IGNORECASE | re.DOTALL)
# Markdown con sot o cuoi (vi du "**Nguon:" chua kip co noi dung, "___"...)
_TRAILING_MD_RE = re.compile(
    r"\s*(\*{2,}|\[[^\]\n]*\]\([^)\n]*\)|_{2,}|#{1,6})\s*$")
# Gemini free tier hay xuat LaTeX don gian ($\ge$, $\le$...) — UI chat khong
# render LaTeX -> doi sang ki tu Unicode tuong ung cho de doc.
_LATEX_SIMPLE = [
    (re.compile(r"\$\\geq?\$"), "≥"),
    (re.compile(r"\$\\leq?\$"), "≤"),
    (re.compile(r"\$\\gt\$"), ">"),
    (re.compile(r"\$\\lt\$"), "<"),
    (re.compile(r"\$\\times\$"), "×"),
]


def strip_markdown(text: str) -> str:
    """Chuyen markdown sang van ban thuong (UI chat dang hien thi plain text).

    Giu lai noi dung va URL trich dan, chi bo ki tu dinh dang:
      **dam** / *** / **** -> bo dau sao, giu chu
      [text](url)          -> text (url)
      `code`               -> code
      # Tieu de            -> Tieu de
    """
    text = re.sub(r"\*{2,}", "", text)                       # bold/italic/HR
    text = re.sub(r"\[([^\]\n]+)\]\(([^)\n]+)\)", r"\1 (\2)", text)  # link
    text = re.sub(r"`([^`\n]*)`", r"\1", text)               # inline code
    text = re.sub(r"(?m)^#{1,6}\s+", "", text)               # heading
    return re.sub(r"\n{3,}", "\n\n", text)


def clean_answer(text: str) -> str:
    r"""Don dep cac ki tu rac hay gap o cau tra loi cua model mien phi.

    Buoc 1: cat nhac nho template + markdown con sot o CUOI cau tra loi
    (khong dong vao than bai). Buoc 2: chuyen markdown con lai trong bai
    thanh van ban thuong de UI khong hien thi dau ***, **, `, #...
    Buoc 3: doi LaTeX don gian ($\ge$, $\le$...) sang ki tu Unicode.
    """
    if not text:
        return text
    cleaned = text.rstrip()
    for _ in range(4):
        prev = cleaned
        cleaned = _NOTE_RE.sub("", cleaned)
        cleaned = _TRAILING_MD_RE.sub("", cleaned)
        cleaned = cleaned.rstrip()
        if cleaned == prev:
            break
    cleaned = strip_markdown(cleaned)
    for pat, repl in _LATEX_SIMPLE:
        cleaned = pat.sub(repl, cleaned)
    return cleaned.strip()
