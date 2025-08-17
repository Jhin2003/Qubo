#!/usr/bin/env python3
"""
ingest_pdfs.py
--------------
Ingest PDFs from a file or folder, extract text + metadata, chunk into passages,
and write a JSONL ready for RAG (one chunk per line).

Dependencies:
    pip install pypdf tqdm

Usage examples:
    python ingest_pdfs.py --input /path/to/file.pdf --out chunks.jsonl
    python ingest_pdfs.py --input /path/to/folder --out chunks.jsonl --chunk-size 800 --overlap 120

JSONL schema per line:
{
  "id": "unique-id",
  "text": "chunk text",
  "metadata": {
     "source_path": "...",
     "page_start": 3,
     "page_end": 4,
     "pdf_title": "...",
     "pdf_author": "...",
     "created": "YYYY-MM-DDTHH:MM:SSZ",
     "modified": "YYYY-MM-DDTHH:MM:SSZ",
     "filesize": 12345
  }
}
"""
import argparse
import hashlib
import io
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from tqdm import tqdm

try:
    from pypdf import PdfReader
except Exception as e:
    print("ERROR: pypdf is required. Install with: pip install pypdf", file=sys.stderr)
    raise


def utc_iso(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0).isoformat()
    except Exception:
        return None


def read_pdf(path: str) -> Tuple[List[str], Dict[str, Optional[str]]]:
    """Read a PDF, returning page-wise text and core metadata."""
    reader = PdfReader(path)
    pages_text = []
    for page in reader.pages:
        # extract_text() preserves basic layout; set visitor if needed
        text = page.extract_text() or ""
        pages_text.append(text)

    info = reader.metadata or {}
    # Normalize common fields
    meta = {
        "pdf_title": getattr(info, "title", None) or (info.get("/Title") if isinstance(info, dict) else None),
        "pdf_author": getattr(info, "author", None) or (info.get("/Author") if isinstance(info, dict) else None),
        "pdf_creator": getattr(info, "creator", None) or (info.get("/Creator") if isinstance(info, dict) else None),
        "pdf_producer": getattr(info, "producer", None) or (info.get("/Producer") if isinstance(info, dict) else None),
        "created": None,
        "modified": None,
    }

    # Try creation/mod dates if available (can be in PDF date format D:YYYYMMDDHHmmSS)
    def _parse_pdf_date(val: Optional[str]) -> Optional[str]:
        if not val:
            return None
        # Strip leading D: and timezone tails
        s = str(val)
        if s.startswith("D:"):
            s = s[2:]
        s = re.sub(r"[Zz].*$", "", s)  # drop trailing Z or timezone
        # Pad to at least YYYYMMDDHHMMSS
        s = s.ljust(14, "0")
        try:
            dt = datetime.strptime(s[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
            return dt.replace(microsecond=0).isoformat()
        except Exception:
            return None

    created_raw = getattr(info, "creation_date", None) or (info.get("/CreationDate") if isinstance(info, dict) else None)
    modified_raw = getattr(info, "mod_date", None) or (info.get("/ModDate") if isinstance(info, dict) else None)
    meta["created"] = _parse_pdf_date(created_raw)
    meta["modified"] = _parse_pdf_date(modified_raw)
    return pages_text, meta


def clean_text(s: str) -> str:
    # Normalize whitespace, trim extra newlines
    s = s.replace("\u00A0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def sentence_split(text: str) -> List[str]:
    """Lightweight sentence splitter using punctuation; avoids heavy dependencies."""
    if not text:
        return []
    # Protect common abbreviations to reduce oversplitting
    protected = {"e.g.", "i.e.", "Dr.", "Mr.", "Ms.", "Mrs.", "vs.", "cf.", "etc."}
    # Simple approach: split on ., ?, ! followed by space/newline and capital
    # We'll re-attach punctuation.
    parts: List[str] = []
    start = 0
    for m in re.finditer(r"([\.!?])(\s+)", text):
        end = m.end()
        segment = text[start:end]
        # Skip splits inside protected tokens
        tail = segment[-5:]
        if any(segment.endswith(p) for p in protected):
            continue
        parts.append(segment.strip())
        start = end
    last = text[start:].strip()
    if last:
        parts.append(last)
    # Fallback if no clear sentence boundaries
    if not parts:
        return [text.strip()]
    # Remove empty
    return [p for p in parts if p]


def chunk_sentences(sentences: List[str], chunk_size: int = 800, overlap: int = 120, min_chars: int = 150) -> List[str]:
    """Greedy pack sentences up to chunk_size chars, with overlap between chunks."""
    chunks: List[str] = []
    buf: List[str] = []
    cur_len = 0

    def flush():
        nonlocal buf, cur_len
        if buf:
            chunk = " ".join(buf).strip()
            if len(chunk) >= min_chars or not chunks:  # keep tiny first chunk
                chunks.append(chunk)
            buf, cur_len = [], 0

    for sent in sentences:
        s = sent.strip()
        if not s:
            continue
        if cur_len + len(s) + 1 > chunk_size and cur_len > 0:
            flush()
            # create overlap from tail of previous chunk
            if overlap > 0 and chunks:
                tail = chunks[-1][-overlap:]
                buf = [tail]
                cur_len = len(tail)
        # add sentence
        buf.append(s)
        cur_len += len(s) + 1
    flush()
    return chunks


@dataclass
class Record:
    id: str
    text: str
    metadata: Dict[str, Optional[str]]


def hash_id(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8", errors="ignore"))
        h.update(b"|")
    return h.hexdigest()[:32]


def iter_pdf_chunks(
    path: str,
    chunk_size: int = 800,
    overlap: int = 120,
    min_chars: int = 150,
) -> Iterator[Record]:
    pages_text, pdf_meta = read_pdf(path)

    try:
        stat = os.stat(path)
        filesize = stat.st_size
        mtime = stat.st_mtime
    except Exception:
        filesize, mtime = None, None

    base_meta = {
        "source_path": os.path.abspath(path),
        "pdf_title": pdf_meta.get("pdf_title"),
        "pdf_author": pdf_meta.get("pdf_author"),
        "pdf_creator": pdf_meta.get("pdf_creator"),
        "pdf_producer": pdf_meta.get("pdf_producer"),
        "created": pdf_meta.get("created"),
        "modified": pdf_meta.get("modified") or utc_iso(mtime),
        "filesize": filesize,
    }

    for page_idx, raw in enumerate(pages_text, start=1):
        text = clean_text(raw)
        sents = sentence_split(text)
        chunks = chunk_sentences(sents, chunk_size=chunk_size, overlap=overlap, min_chars=min_chars)
        for ci, chunk in enumerate(chunks):
            rid = hash_id(base_meta["source_path"], str(page_idx), str(ci), chunk[:64])
            meta = dict(base_meta)
            meta.update({"page_start": page_idx, "page_end": page_idx})
            yield Record(id=rid, text=chunk, metadata=meta)


def discover_pdfs(input_path: str) -> List[str]:
    if os.path.isfile(input_path):
        return [input_path] if input_path.lower().endswith(".pdf") else []
    pdfs: List[str] = []
    for root, _, files in os.walk(input_path):
        for f in files:
            if f.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, f))
    return sorted(pdfs)


def write_jsonl(out_path: str, records: Iterable[Record]) -> int:
    n = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for rec in records:
            obj = {"id": rec.id, "text": rec.text, "metadata": rec.metadata}
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description="Ingest PDFs → JSONL chunks for RAG.")
    ap.add_argument("--input", required=True, help="PDF file or folder")
    ap.add_argument("--out", required=True, help="Output JSONL file path")
    ap.add_argument("--chunk-size", type=int, default=800, help="Max characters per chunk")
    ap.add_argument("--overlap", type=int, default=120, help="Character overlap between chunks")
    ap.add_argument("--min-chars", type=int, default=150, help="Minimum characters to keep a chunk")
    args = ap.parse_args()

    pdf_paths = discover_pdfs(args.input)
    if not pdf_paths:
        print("No PDFs found in input.", file=sys.stderr)
        sys.exit(2)

    def recs():
        for p in tqdm(pdf_paths, desc="Processing PDFs"):
            for r in iter_pdf_chunks(p, chunk_size=args.chunk_size, overlap=args.overlap, min_chars=args.min_chars):
                yield r

    out_dir = os.path.dirname(args.out)
    if not out_dir:
        out_dir = os.getcwd()
    out_path = os.path.join(out_dir, os.path.basename(args.out))
    os.makedirs(out_dir, exist_ok=True)
    total = write_jsonl(out_path, recs())
    print(f"Wrote {total} chunks to {out_path}")
    total = write_jsonl(args.out, recs())
    print(f"Wrote {total} chunks to {args.out}")

if __name__ == "__main__":
    main()
