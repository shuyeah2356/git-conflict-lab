#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def iter_files(root: Path, exts: tuple[str, ...]):
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in exts:
            yield path


def replace_in_file(path: Path, old: str, new: str, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 0:
        return 0
    if not dry_run:
        path.write_text(text.replace(old, new), encoding="utf-8")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch replace text in source files.")
    parser.add_argument("--root", default=".", help="Root directory to scan.")
    parser.add_argument("--old", default="left-v5", help="Text to replace.")
    parser.add_argument("--new", default="left-v6", help="Replacement text.")
    parser.add_argument(
        "--ext",
        nargs="+",
        default=[".py"],
        help="File extensions to include, e.g. .py .md",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview changes only.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    exts = tuple(e.lower() if e.startswith(".") else f".{e.lower()}" for e in args.ext)

    files_changed = 0
    replacements = 0
    for file_path in iter_files(root, exts):
        count = replace_in_file(file_path, args.old, args.new, args.dry_run)
        if count > 0:
            files_changed += 1
            replacements += count
            print(f"{file_path}: {count}")

    action = "Would replace" if args.dry_run else "Replaced"
    print(f"{action} '{args.old}' -> '{args.new}' in {files_changed} file(s), {replacements} occurrence(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
