# -*- coding: utf-8 -*-
"""把 papers.json 引用的 PDF 收拢到 papers_pdf/{编目号}.pdf，供仓库与线上服务使用。

源目录保持不动，只复制被引用的 97 篇，不包含学生作业和其他材料。

用法：
    python scripts/collect_pdfs.py
    python scripts/collect_pdfs.py --force   # 已存在的也覆盖
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "papers_pdf"
LOCAL_BASE = ROOT / "2020-2025年专业文献及政策案例作业"
LEGACY_BASE = ROOT.parent / "2020-2025年专业文献及政策案例作业"


def main():
    force = "--force" in sys.argv
    base = LOCAL_BASE if LOCAL_BASE.exists() else LEGACY_BASE
    papers = json.loads((DATA / "papers.json").read_text(encoding="utf-8"))
    OUT.mkdir(exist_ok=True)

    copied, skipped, missing, total = 0, 0, [], 0
    for p in papers:
        rel = p.get("path") or ""
        src = base / rel
        dst = OUT / f"{p['cat']}.pdf"
        if not rel or not src.is_file():
            missing.append(p["cat"])
            continue
        if dst.exists() and not force:
            skipped += 1
            total += dst.stat().st_size
            continue
        shutil.copy2(src, dst)
        total += dst.stat().st_size
        copied += 1

    print(f"复制 {copied} 篇，已存在跳过 {skipped} 篇，缺失 {len(missing)} 篇")
    if missing:
        print("缺失：", "、".join(missing))
    print(f"输出目录 {OUT}，合计 {total/1024/1024:.1f} MB")


if __name__ == "__main__":
    main()
