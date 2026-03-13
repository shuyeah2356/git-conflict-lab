#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path


START = "<<<<<<<"
MID = "======="
END = ">>>>>>>"
TEXT_SUFFIX = {".py", ".js", ".ts", ".tsx", ".java", ".go", ".rs", ".md", ".txt", ".json", ".yaml", ".yml"}


def run_git(repo: Path, args):
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "git {} failed\nstdout:\n{}\nstderr:\n{}".format(" ".join(args), proc.stdout, proc.stderr)
        )
    return proc.stdout.strip()


def tracked_text_files(repo: Path):
    out = run_git(repo, ["ls-files"])
    for rel in out.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        p = repo / rel
        if p.suffix.lower() in TEXT_SUFFIX and p.is_file():
            yield p


def conflict_files(repo: Path):
    files = set()
    for p in tracked_text_files(repo):
        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lines = content.splitlines()
        has_start = any(line.startswith(START) for line in lines)
        has_mid = any(line.startswith(MID) for line in lines)
        has_end = any(line.startswith(END) for line in lines)
        if has_start and has_mid and has_end:
            files.add(str(p.relative_to(repo)))
    return sorted(files)


def resolve_text(content: str, strategy: str):
    lines = content.splitlines(keepends=True)
    i = 0
    out = []
    blocks = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith(START):
            out.append(line)
            i += 1
            continue
        blocks += 1
        i += 1
        ours, theirs = [], []
        while i < len(lines) and not lines[i].startswith(MID):
            ours.append(lines[i])
            i += 1
        if i < len(lines):
            i += 1
        while i < len(lines) and not lines[i].startswith(END):
            theirs.append(lines[i])
            i += 1
        if i < len(lines):
            i += 1
        if strategy == "ours":
            out.extend(ours)
        elif strategy == "theirs":
            out.extend(theirs)
        else:
            merged = []
            for block in (ours, theirs):
                for bline in block:
                    if bline not in merged:
                        merged.append(bline)
            out.extend(merged)
    return "".join(out), blocks


def cmd_detect(args):
    repo = Path(args.repo).resolve()
    files = conflict_files(repo)
    print(json.dumps({"conflict_files": files, "count": len(files)}, ensure_ascii=False, indent=2))


def cmd_autoresolve(args):
    repo = Path(args.repo).resolve()
    files = conflict_files(repo)
    changed = []
    blocks_total = 0
    for rel in files:
        p = repo / rel
        old = p.read_text(encoding="utf-8")
        new, blocks = resolve_text(old, args.strategy)
        if new != old:
            p.write_text(new, encoding="utf-8")
            changed.append(rel)
            blocks_total += blocks
            if args.stage:
                run_git(repo, ["add", rel])
    print(
        json.dumps(
            {"strategy": args.strategy, "files_changed": changed, "block_count": blocks_total},
            ensure_ascii=False,
            indent=2,
        )
    )


def ensure_clean(repo: Path):
    status = run_git(repo, ["status", "--porcelain"])
    if status.strip():
        raise RuntimeError("working tree is not clean, please commit/stash first")


def write_case_file(path: Path, flavor: str, idx: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "def case_{0}():\n"
        "    return \"{1} version {0}\"\n".format(idx, flavor),
        encoding="utf-8",
    )


def cmd_generate(args):
    repo = Path(args.repo).resolve()
    if not args.allow_dirty:
        ensure_clean(repo)
    root = Path(args.case_dir)
    base = args.base_branch
    left = args.left_branch
    right = args.right_branch

    run_git(repo, ["checkout", base])
    for i in range(1, args.count + 1):
        write_case_file(repo / root / ("module_{:03d}.py".format(i)), "base", i)
    run_git(repo, ["add", str(root)])
    run_git(repo, ["commit", "-m", "seed conflict cases ({})".format(args.count)])

    run_git(repo, ["checkout", "-B", left, base])
    for i in range(1, args.count + 1):
        write_case_file(repo / root / ("module_{:03d}.py".format(i)), "left", i)
    run_git(repo, ["add", str(root)])
    run_git(repo, ["commit", "-m", "left branch conflicting edits"])

    run_git(repo, ["checkout", "-B", right, base])
    for i in range(1, args.count + 1):
        write_case_file(repo / root / ("module_{:03d}.py".format(i)), "right", i)
    run_git(repo, ["add", str(root)])
    run_git(repo, ["commit", "-m", "right branch conflicting edits"])

    merge = subprocess.run(
        ["git", "merge", left],
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=False,
    )
    result = {
        "count": args.count,
        "base": base,
        "left": left,
        "right": right,
        "merge_exit_code": merge.returncode,
        "merge_conflicted": merge.returncode != 0,
        "conflict_files": conflict_files(repo),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_history(args):
    repo = Path(args.repo).resolve()
    since = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%d")

    all_files = run_git(repo, ["log", "--name-only", "--pretty=format:"]).splitlines()
    merge_files = run_git(repo, ["log", "--merges", "--name-only", "--pretty=format:"]).splitlines()
    recent_files = run_git(repo, ["log", "--since", since, "--name-only", "--pretty=format:"]).splitlines()

    def top(items):
        cnt = Counter([x.strip() for x in items if x.strip()])
        return cnt.most_common(args.top)

    print(
        json.dumps(
            {
                "days": args.days,
                "touch_hot_files": top(all_files),
                "merge_hot_files": top(merge_files),
                "recent_hot_files": top(recent_files),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def cmd_predict(args):
    repo = Path(args.repo).resolve()
    since = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%d")

    all_files = Counter(
        [x.strip() for x in run_git(repo, ["log", "--name-only", "--pretty=format:"]).splitlines() if x.strip()]
    )
    merge_files = Counter(
        [x.strip() for x in run_git(repo, ["log", "--merges", "--name-only", "--pretty=format:"]).splitlines() if x.strip()]
    )
    recent_files = Counter(
        [x.strip() for x in run_git(repo, ["log", "--since", since, "--name-only", "--pretty=format:"]).splitlines() if x.strip()]
    )

    scores = {}
    all_keys = set(all_files) | set(merge_files) | set(recent_files)
    for f in all_keys:
        scores[f] = round(all_files[f] * 0.5 + merge_files[f] * 1.2 + recent_files[f] * 1.0, 2)

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[: args.top]
    print(json.dumps({"days": args.days, "predicted_conflict_top": ranked}, ensure_ascii=False, indent=2))


def cmd_ci_check(args):
    repo = Path(args.repo).resolve()
    files = conflict_files(repo)
    payload = {"ok": len(files) == 0, "conflict_files": files}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if files:
        return 1
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="Git conflict lab helper")
    p.add_argument("--repo", default=".", help="repo path")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("detect")

    ar = sub.add_parser("autoresolve")
    ar.add_argument("--strategy", choices=["ours", "theirs", "union"], default="union")
    ar.add_argument("--stage", action="store_true")

    gen = sub.add_parser("generate")
    gen.add_argument("--count", type=int, default=30)
    gen.add_argument("--base-branch", default="main")
    gen.add_argument("--left-branch", default="conflict-left")
    gen.add_argument("--right-branch", default="conflict-right")
    gen.add_argument("--case-dir", default="conflict_cases")
    gen.add_argument("--allow-dirty", action="store_true")

    hs = sub.add_parser("history")
    hs.add_argument("--days", type=int, default=90)
    hs.add_argument("--top", type=int, default=10)

    pr = sub.add_parser("predict")
    pr.add_argument("--days", type=int, default=90)
    pr.add_argument("--top", type=int, default=10)

    sub.add_parser("ci-check")
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.cmd == "detect":
        cmd_detect(args)
    elif args.cmd == "autoresolve":
        cmd_autoresolve(args)
    elif args.cmd == "generate":
        cmd_generate(args)
    elif args.cmd == "history":
        cmd_history(args)
    elif args.cmd == "predict":
        cmd_predict(args)
    elif args.cmd == "ci-check":
        raise SystemExit(cmd_ci_check(args))
    else:
        parser.print_help()
        raise SystemExit(2)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
