"""
Extract approximate readable text from legacy MS Word .doc (OLE Compound File).

This repo sometimes contains tutorials authored as .doc. In environments without
Microsoft Word/LibreOffice/antiword, we fall back to a best-effort extraction:
we read the largest OLE streams and decode as UTF-16LE, then keep runs of
printable CJK/ASCII characters. Output is *not* guaranteed to be perfectly
ordered, but is usually good enough to reconstruct the document.

Usage:
  python scripts/extract_doc_ole_text.py <input.doc> <output.txt>
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path


def _is_ok_char(ch: str) -> bool:
    if ch in "\r\n\t":
        return True
    o = ord(ch)
    if 0x20 <= o <= 0x7E:
        return True
    # CJK Unified Ideographs + Ext A, CJK punctuation, fullwidth forms
    if (0x4E00 <= o <= 0x9FFF) or (0x3400 <= o <= 0x4DBF) or (0x3000 <= o <= 0x303F) or (0xFF00 <= o <= 0xFFEF):
        return True
    cat = unicodedata.category(ch)
    if cat.startswith("P"):  # punctuation
        return True
    return False


def extract_text_from_blob(blob: bytes) -> str:
    # Legacy Word text is often UTF-16LE; this is best-effort.
    s = blob.decode("utf-16le", errors="ignore")
    out: list[str] = []
    run: list[str] = []

    def flush() -> None:
        nonlocal run
        if len(run) >= 6:
            out.append("".join(run))
        run = []

    for ch in s:
        if _is_ok_char(ch):
            run.append(ch)
        else:
            flush()
    flush()

    text = "\n".join(out)
    text = re.sub(r"[\t ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python scripts/extract_doc_ole_text.py <input.doc> <output.txt>", file=sys.stderr)
        return 2

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    try:
        import olefile  # type: ignore
    except Exception as e:  # pragma: no cover
        print(f"Missing dependency: olefile ({e}). Install with: pip install olefile", file=sys.stderr)
        return 3

    ole = olefile.OleFileIO(str(in_path))
    streams = ole.listdir(streams=True, storages=False)

    blobs: list[tuple[int, str, bytes]] = []
    for s in streams:
        name = "/".join(s)
        try:
            data = ole.openstream(s).read()
        except Exception:
            continue
        blobs.append((len(data), name, data))

    blobs.sort(reverse=True, key=lambda x: x[0])
    selected = blobs[:8]  # heuristic: the biggest ones tend to hold the text

    parts: list[str] = []
    parts.append(f"INPUT: {in_path}")
    parts.append(f"STREAMS: {len(streams)} (showing top {len(selected)} by size)")
    for size, name, _ in selected:
        parts.append(f"- {name} (size {size})")

    for size, name, data in selected:
        t = extract_text_from_blob(data)
        if len(t) < 200:
            continue
        parts.append("")
        parts.append(f"===== STREAM {name} (size {size}) =====")
        parts.append("")
        parts.append(t)

    ole.close()
    out_path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())









