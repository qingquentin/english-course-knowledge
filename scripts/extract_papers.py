# -*- coding: utf-8 -*-
"""从课程 PDF 提取文献全文，写入 data/papers_fulltext.json。

两栏排版是这里的主要麻烦：直接按内容流取字会左右栏交错。做法是按块取文字，
用块的坐标把页面切成「通栏块 + 分栏带」，每个带内先左栏后右栏，恢复阅读顺序。

依赖 pymupdf（不是标准库，需装在 backend 的 venv 里）：
    backend/.venv/Scripts/pip install pymupdf

用法：
    python scripts/extract_papers.py
    python scripts/extract_papers.py --base "D:/桌面/1/专业英语/2020-2025年专业文献及政策案例作业"
    python scripts/extract_papers.py --force      # 已提取的也重做
"""
import json
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SRC = DATA / "papers.json"
OUT = DATA / "papers_fulltext.json"
LOCAL_BASE = ROOT / "2020-2025年专业文献及政策案例作业"
DEFAULT_BASE = LOCAL_BASE if LOCAL_BASE.exists() else ROOT.parent / "2020-2025年专业文献及政策案例作业"

FULL_WIDTH = 0.62   # 块宽超过页宽这个比例，视为通栏
MID = 0.53          # 块中心线超过页宽这个比例，归右栏


def page_text(page) -> str:
    blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
    if not blocks:
        return ""
    w = page.rect.width
    ordered, band = [], []

    def flush():
        if not band:
            return
        left = [b for b in band if (b[0] + b[2]) / 2 < w * MID]
        right = [b for b in band if (b[0] + b[2]) / 2 >= w * MID]
        ordered.extend(sorted(left, key=lambda b: b[1]))
        ordered.extend(sorted(right, key=lambda b: b[1]))
        band.clear()

    for b in sorted(blocks, key=lambda b: b[1]):
        if (b[2] - b[0]) > w * FULL_WIDTH:
            flush()
            ordered.append(b)
        else:
            band.append(b)
    flush()
    return "\n".join(b[4].strip() for b in ordered)


def to_paragraphs(text: str) -> str:
    """把逐行文字并回段落。句末且够长就断段，冒号结尾的短行视为小标题。"""
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]
    paras, buf = [], []
    for ln in lines:
        buf.append(ln)
        joined = " ".join(buf)
        if len(joined) >= 160 and re.search(r"[.!?][\"'”’)\]]?$", ln):
            paras.append(joined)
            buf = []
        elif len(joined) <= 80 and re.search(r"[:：]$", ln):
            paras.append(joined)
            buf = []
    if buf:
        paras.append(" ".join(buf))
    return "\n\n".join(p for p in paras if p)


def clean(text: str) -> str:
    text = re.sub(r"([a-z])-\n([a-z])", r"\1\2", text)   # 行末断词
    text = re.sub(r"[ \t]+\n", "\n", text)
    return to_paragraphs(text)


def extract(pdf: Path) -> str:
    parts = []
    with pymupdf.open(pdf) as doc:
        for page in doc:
            t = page_text(page)
            if t:
                parts.append(t)
    return clean("\n".join(parts))


def main():
    args = sys.argv[1:]
    base = DEFAULT_BASE
    if "--base" in args:
        base = Path(args[args.index("--base") + 1])
    force = "--force" in args

    papers = json.loads(SRC.read_text(encoding="utf-8"))
    old = {}
    if OUT.exists() and not force:
        old = json.loads(OUT.read_text(encoding="utf-8"))

    result, ok, missing, failed, skipped = {}, 0, [], [], 0
    for i, p in enumerate(papers, 1):
        cat, rel = p["cat"], p.get("path") or ""
        prev = old.get(cat)
        if prev and prev.get("extracted") and not force:
            result[cat] = prev
            skipped += 1
            continue

        pdf = base / rel
        if not pdf.exists():
            # 没有课程资料目录时，退回仓库内的 papers_pdf/{cat}.pdf
            pdf = ROOT / "papers_pdf" / f"{cat}.pdf"
        if not pdf.exists():
            result[cat] = {"body": "", "char_count": 0, "extracted": False,
                           "note": f"文件缺失：{rel}"}
            missing.append(cat)
            continue
        try:
            body = extract(pdf)
        except Exception as e:                       # 加密、损坏等
            result[cat] = {"body": "", "char_count": 0, "extracted": False,
                           "note": f"提取失败：{type(e).__name__} {e}"}
            failed.append(cat)
            print(f"  [{i}/{len(papers)}] {cat} 失败：{e}")
            continue
        result[cat] = {"body": body, "char_count": len(body),
                       "extracted": bool(body), "note": "" if body else "未提取到文字，可能是扫描件"}
        if body:
            ok += 1
        else:
            failed.append(cat)
        if i % 10 == 0:
            print(f"  ... {i}/{len(papers)}")

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(v["char_count"] for v in result.values())
    print(f"\n成功 {ok} 篇，跳过 {skipped} 篇，缺文件 {len(missing)} 篇，失败 {len(failed)} 篇")
    if missing:
        print("缺文件：", "、".join(missing))
    if failed:
        print("失败：", "、".join(failed))
    print(f"正文合计 {total/10000:.1f} 万字，输出 {OUT} "
          f"（{OUT.stat().st_size/1024/1024:.1f} MB）")


if __name__ == "__main__":
    main()
