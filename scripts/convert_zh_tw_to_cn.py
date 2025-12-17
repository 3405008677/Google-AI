"""
批次将专案中的繁体中文转为简体中文（OpenCC t2s）。

特性：
- 只处理常见文字档（可用 --ext 追加/覆写）
- 自动略过二进位档（含 NUL byte）与常见忽略目录
- 保留 UTF-8 BOM（若原档有）
- 只在内容有变化时才覆写，降低无意义 diff
"""

from __future__ import annotations

import argparse
import codecs
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple

from opencc import OpenCC


DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "log",
    "logs",
}

DEFAULT_TEXT_EXTS = {
    ".py",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
    ".example",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".sh",
    ".bat",
    ".ps1",
}


@dataclass(frozen=True)
class ConvertResult:
    path: Path
    changed: bool
    skipped: bool
    reason: str = ""


def _detect_text_encoding(raw: bytes) -> Tuple[Optional[str], bytes]:
    """
    回传 (encoding, bom_bytes)。
    - 有 BOM 的 UTF 系列一律视为文字档
    - 无法判断则回传 (None, b"")
    """
    if raw.startswith(codecs.BOM_UTF8):
        return "utf-8", codecs.BOM_UTF8
    if raw.startswith(codecs.BOM_UTF16_LE):
        return "utf-16-le", codecs.BOM_UTF16_LE
    if raw.startswith(codecs.BOM_UTF16_BE):
        return "utf-16-be", codecs.BOM_UTF16_BE
    if raw.startswith(codecs.BOM_UTF32_LE):
        return "utf-32-le", codecs.BOM_UTF32_LE
    if raw.startswith(codecs.BOM_UTF32_BE):
        return "utf-32-be", codecs.BOM_UTF32_BE
    return None, b""


def _looks_like_binary(raw: bytes) -> bool:
    # 先排除有 BOM 的 UTF 档（UTF-16/32 会大量出现 NUL byte）
    enc, _ = _detect_text_encoding(raw)
    if enc is not None:
        return False
    # 粗略判断：含 NUL 多半是二进位；但也可能是没有 BOM 的 UTF-16
    if b"\x00" not in raw:
        return False
    nul_ratio = raw.count(b"\x00") / max(len(raw), 1)
    if nul_ratio < 0.05:
        # 少量 NUL 也可能是压缩/图片/等
        return True
    # 尝试以 UTF-16 解码看看（无 BOM 的情况）
    for enc_try in ("utf-16-le", "utf-16-be"):
        try:
            _ = raw.decode(enc_try)
            return False
        except UnicodeDecodeError:
            continue
    return True


def _should_process(path: Path, exts: set[str]) -> bool:
    # 只处理档案
    if not path.is_file():
        return False
    # 只处理指定副档名
    return path.suffix.lower() in exts


def _iter_files(root: Path, exclude_dirs: set[str]) -> Iterable[Path]:
    for p in root.rglob("*"):
        # 任何一层目录命中 exclude 就跳过
        if any(part in exclude_dirs for part in p.parts):
            continue
        yield p


def convert_file(path: Path, cc: OpenCC, dry_run: bool) -> ConvertResult:
    try:
        raw = path.read_bytes()
    except Exception as e:
        return ConvertResult(path=path, changed=False, skipped=True, reason=f"read_failed: {e}")

    if _looks_like_binary(raw):
        return ConvertResult(path=path, changed=False, skipped=True, reason="binary")

    enc, bom = _detect_text_encoding(raw)
    try:
        if enc is not None and bom:
            text = raw[len(bom) :].decode(enc)
        else:
            # 无 BOM：预设 UTF-8
            enc = "utf-8"
            bom = b""
            text = raw.decode(enc)
    except UnicodeDecodeError:
        return ConvertResult(path=path, changed=False, skipped=True, reason="decode_failed")

    converted = cc.convert(text)
    if converted == text:
        return ConvertResult(path=path, changed=False, skipped=False)

    if dry_run:
        return ConvertResult(path=path, changed=True, skipped=False, reason="dry_run")

    try:
        out = bom + converted.encode(enc or "utf-8")
        path.write_bytes(out)
        return ConvertResult(path=path, changed=True, skipped=False)
    except Exception as e:
        return ConvertResult(path=path, changed=False, skipped=True, reason=f"write_failed: {e}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert Traditional Chinese to Simplified Chinese across a repo.")
    parser.add_argument("--root", default=".", help="Repo root directory (default: .)")
    parser.add_argument("--dry-run", action="store_true", help="Do not write changes, only report.")
    parser.add_argument(
        "--ext",
        action="append",
        default=[],
        help="File extension to include (repeatable). If omitted, uses a safe default set.",
    )
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Directory name to exclude (repeatable).",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    exts = {e if e.startswith(".") else f".{e}" for e in (args.ext or [])}
    if not exts:
        exts = set(DEFAULT_TEXT_EXTS)
    exclude_dirs = set(DEFAULT_EXCLUDE_DIRS) | set(args.exclude_dir or [])

    cc = OpenCC("t2s")

    changed_files: list[Path] = []
    skipped: list[ConvertResult] = []
    scanned = 0

    for p in _iter_files(root, exclude_dirs):
        if not _should_process(p, exts):
            continue
        scanned += 1
        r = convert_file(p, cc=cc, dry_run=args.dry_run)
        if r.skipped and r.reason:
            skipped.append(r)
        if r.changed:
            changed_files.append(p)

    print(f"root={root}")
    print(f"scanned={scanned}")
    print(f"changed={len(changed_files)}")
    if args.dry_run:
        print("mode=dry_run")
    else:
        print("mode=write")

    if changed_files:
        print("\nChanged files:")
        for p in changed_files:
            print(f"- {p.relative_to(root)}")

    if skipped:
        # 只列前 50 个避免输出爆炸
        print("\nSkipped (first 50):")
        for r in skipped[:50]:
            print(f"- {r.path.relative_to(root)} ({r.reason})")
        if len(skipped) > 50:
            print(f"... and {len(skipped) - 50} more")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


