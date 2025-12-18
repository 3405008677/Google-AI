"""
Project usage audit (static, best-effort).

Outputs:
- Unused internal Python modules under `src/` (based on import reachability)
- Third-party top-level imports seen in `src/` (helps prune requirements)

Notes:
- This is conservative and does not attempt to understand dynamic imports.
- It treats several entry points as roots: src.main, src.server.*, src.router.index
"""

from __future__ import annotations

import ast
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"


ROOT_MODULES = [
    "src.main",
    "src.server.server",
    "src.server.app",
    "src.router.index",
]


@dataclass(frozen=True)
class ModuleInfo:
    name: str
    path: Path
    is_package_init: bool


def _path_to_module(path: Path) -> Optional[str]:
    try:
        rel = path.relative_to(REPO_ROOT)
    except ValueError:
        return None
    if rel.parts[0] != "src":
        return None
    if rel.suffix != ".py":
        return None
    parts = list(rel.with_suffix("").parts)  # src, ...
    return ".".join(parts)


def _build_internal_index() -> Dict[str, ModuleInfo]:
    index: Dict[str, ModuleInfo] = {}
    for p in SRC_DIR.rglob("*.py"):
        mod = _path_to_module(p)
        if not mod:
            continue
        index[mod] = ModuleInfo(
            name=mod,
            path=p,
            is_package_init=p.name == "__init__.py",
        )
    return index


def _resolve_relative(base_module: str, level: int, module: Optional[str]) -> Optional[str]:
    """
    Resolve 'from ...foo import bar' relative import target to an absolute module.
    """
    if level <= 0:
        return module
    base_parts = base_module.split(".")
    # base_module includes the file module; relative import is relative to its package
    if not base_parts:
        return module
    # If we're in a module (not package __init__), drop last part to get package
    pkg_parts = base_parts[:-1]
    if len(pkg_parts) < (level - 1):
        return None
    parent_parts = pkg_parts[: len(pkg_parts) - (level - 1)]
    if module:
        return ".".join(parent_parts + module.split("."))
    return ".".join(parent_parts)


def _iter_imports(tree: ast.AST, base_module: str) -> Iterable[Tuple[str, bool]]:
    """
    Yield (imported_module, is_third_party_guess).
    - For internal, we mainly care about modules under "src.".
    - For third-party, we yield top-level package names (best-effort).
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name.startswith("src."):
                    yield name, False
                else:
                    yield name.split(".")[0], True
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve_relative(base_module, node.level or 0, node.module)
            if not resolved:
                continue
            if resolved.startswith("src."):
                yield resolved, False
            else:
                yield resolved.split(".")[0], True


def _parse_file(path: Path) -> Optional[ast.AST]:
    try:
        src = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        src = path.read_text(encoding="utf-8-sig")
    try:
        return ast.parse(src, filename=str(path))
    except SyntaxError:
        return None


def audit() -> Dict[str, object]:
    internal = _build_internal_index()

    reachable: Set[str] = set()
    to_visit: List[str] = [m for m in ROOT_MODULES if m in internal]
    third_party_top: Set[str] = set()

    while to_visit:
        mod = to_visit.pop()
        if mod in reachable:
            continue
        info = internal.get(mod)
        if not info:
            continue
        reachable.add(mod)

        tree = _parse_file(info.path)
        if tree is None:
            continue

        for imported, is_third_party in _iter_imports(tree, base_module=mod):
            if is_third_party:
                # Skip stdlib-ish obvious ones by a cheap heuristic:
                # if it is a built-in module name or in stdlib list env var.
                third_party_top.add(imported)
                continue

            # Only traverse within src.*
            if imported in internal:
                to_visit.append(imported)
            else:
                # Try package __init__ fallback: importing src.a.b might actually
                # reference src.a.b.__init__
                pkg_init = f"{imported}.__init__"
                if pkg_init in internal:
                    to_visit.append(pkg_init)

    # Anything under src/ not reachable is "unused" (best-effort).
    unused_modules = sorted(
        [
            {"module": name, "path": str(info.path.relative_to(REPO_ROOT)), "is_init": info.is_package_init}
            for name, info in internal.items()
            if name not in reachable
        ],
        key=lambda x: x["path"],
    )

    reachable_modules = sorted(
        [{"module": m, "path": str(internal[m].path.relative_to(REPO_ROOT))} for m in reachable],
        key=lambda x: x["path"],
    )

    return {
        "repo_root": str(REPO_ROOT),
        "roots": ROOT_MODULES,
        "reachable_count": len(reachable_modules),
        "unused_count": len(unused_modules),
        "reachable_modules": reachable_modules,
        "unused_modules": unused_modules,
        "third_party_top_level_imports_seen_in_src": sorted(third_party_top),
    }


def main() -> int:
    result = audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


