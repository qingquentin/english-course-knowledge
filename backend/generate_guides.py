# -*- coding: utf-8 -*-
"""文献导读生成 CLI。

用法（在 backend 目录下）：

    python generate_guides.py preview                 # 全部论文状态，不调 API
    python generate_guides.py preview --cat A-010
    python generate_guides.py preview --module C

    python generate_guides.py check                   # 校验全部导读
    python generate_guides.py check --cat B-004

    python generate_guides.py generate --cat A-010
    python generate_guides.py generate --cats A-010,C-009
    python generate_guides.py generate --module B --limit 5

preview / check 只读，绝不调用 API。generate 才会调 DeepSeek。

覆盖规则：
    - 已有 review.status == "reviewed" 的导读，永远拒绝覆盖。
    - 已有 draft 的导读，必须显式 --force 才覆盖。
    - 不存在导读才直接生成。

生成前自动跳过：无正文、正文过短、提取失败的论文。
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import ai
import guide_prompt
import guides

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
GUIDES_DIR = DATA / "guides"

PROMPT_VERSION = "guide-v1"
GENERATED_SECTIONS = ["overview", "mechanism", "methods", "critique",
                      "key_concepts", "reading_recommendations"]
ANALYTICAL_SECTIONS = ["critique"]


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_papers():
    return {p["cat"]: p for p in _load(DATA / "papers.json")}


def load_fulltext():
    p = DATA / "papers_fulltext.json"
    return _load(p) if p.exists() else {}


def select_cats(args, papers):
    """按 --cat / --cats / --module / 默认全部 选择论文。"""
    if getattr(args, "cat", None):
        return [args.cat]
    if getattr(args, "cats", None):
        return [c.strip() for c in args.cats.split(",") if c.strip()]
    if getattr(args, "module", None):
        cats = sorted(p["cat"] for p in papers.values() if p["m"] == args.module.upper())
    else:
        cats = sorted(papers.keys())
    limit = getattr(args, "limit", None)
    return cats[:limit] if limit else cats


def normalize_guide(payload):
    """把模型偶尔的类型漂移（字符串↔数组）归一化到 Schema 要求的类型。

    只做无损纠正：数组转字符串用「；」连接，字符串转数组包成单元素数组。
    不改变内容，只保证存储类型与前端渲染一致。
    """
    g = payload.get("guide")
    if not isinstance(g, dict):
        return payload
    for section, spec in guides._GUIDE_SECTIONS.items():
        sec = g.get(section)
        if not isinstance(sec, dict):
            continue
        for field, ftype in spec.items():
            if field not in sec:
                continue
            val = sec[field]
            if ftype == "str":
                if isinstance(val, list):
                    sec[field] = "；".join(str(x) for x in val if str(x).strip())
                elif val is None:
                    sec[field] = ""
                elif not isinstance(val, str):
                    sec[field] = str(val)
            elif ftype == "list":
                if isinstance(val, str):
                    sec[field] = [val] if val.strip() else []
                elif val is None:
                    sec[field] = []
    for field in ("key_concepts", "reading_recommendations"):
        val = g.get(field)
        if isinstance(val, str):
            g[field] = [val] if val.strip() else []
        elif val is None:
            g[field] = []
    return payload


def atomic_write_json(path, data):
    """临时文件 + os.replace 原子替换，失败不留半成品。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


# ---------- preview ----------

def _status_of(cat, papers, fulltext, args):
    p = papers.get(cat)
    if not p:
        return {"cat": cat, "kind": "不存在"}
    ft = fulltext.get(cat, {})
    body = (ft.get("body") or "").strip()
    note = ft.get("note") or ""
    chars = ft.get("char_count") or len(body)
    existing = guides.get_guide(cat)

    if not body:
        full = "无正文"
    elif ft.get("extracted") is False or "未提取" in note or "文件缺失" in note:
        full = f"提取不完整（{note}）"
    elif chars < args.min_chars:
        full = f"正文过短（{chars} 字）"
    else:
        full = f"正文 {chars} 字"

    if existing:
        st = (existing.get("review") or {}).get("status")
        guide_state = f"已有导读[{st}]"
    else:
        guide_state = "无导读"

    return {"cat": cat, "kind": "paper", "title": p["title"], "module": p["m"],
            "year": p.get("year"), "fulltext": full, "guide": guide_state}


def cmd_preview(args, papers, fulltext):
    cats = select_cats(args, papers)
    if not cats:
        print("没有匹配的论文。")
        return
    rows = [_status_of(c, papers, fulltext, args) for c in cats]
    print(f"共 {len(rows)} 篇（preview，未调用 API）\n")
    for r in rows:
        if r["kind"] == "不存在":
            print(f"  {r['cat']}  不存在")
            continue
        print(f"  {r['cat']}  [{r['module']}] {r['year']}  {r['title'][:52]}")
        print(f"        {r['fulltext']}  |  {r['guide']}")


# ---------- check ----------

def cmd_check(args, papers, fulltext):
    cats = select_cats(args, papers) if (getattr(args, "cat", None) or getattr(args, "module", None)) \
        else sorted(p.stem for p in GUIDES_DIR.glob("*.json"))
    if not cats:
        print("没有可检查的导读。")
        return
    ok_n = fail_n = 0
    for c in cats:
        g = guides.get_guide(c)
        if g is None:
            print(f"  {c}  无导读文件")
            continue
        ok, errs = guides.validate_guide(g)
        if ok:
            ok_n += 1
            print(f"  ok   {c}")
        else:
            fail_n += 1
            print(f"  FAIL {c}")
            for e in errs:
                print(f"        - {e}")
    print(f"\n通过 {ok_n} 篇，失败 {fail_n} 篇（check 未修改任何文件）")


# ---------- generate ----------

def generate_one(cat, papers, fulltext, args):
    p = papers[cat]
    ft = fulltext.get(cat, {})
    body = (ft.get("body") or "").strip()
    note = ft.get("note") or ""
    chars = ft.get("char_count") or len(body)

    # 安全门：全文
    if not body:
        return {"cat": cat, "status": "skip", "reason": "无正文"}
    if ft.get("extracted") is False or "未提取" in note or "文件缺失" in note:
        return {"cat": cat, "status": "skip", "reason": f"提取不完整：{note or '未提取到文字'}"}
    if chars < args.min_chars:
        return {"cat": cat, "status": "skip", "reason": f"正文过短（{chars} 字 < {args.min_chars}）"}

    # 安全门：已有导读
    existing = guides.get_guide(cat)
    if existing:
        st = (existing.get("review") or {}).get("status")
        if st == "reviewed":
            return {"cat": cat, "status": "skip", "reason": "reviewed，禁止覆盖"}
        if not args.force:
            return {"cat": cat, "status": "skip", "reason": f"已有 {st} 导读，需 --force 覆盖"}

    # 分块 + 完整性
    digest = guide_prompt.digest_paper(body, args.budget)
    completeness, reasons = guide_prompt.judge_completeness(ft, digest, args.min_chars)
    if completeness == "insufficient":
        return {"cat": cat, "status": "skip", "reason": "insufficient：" + "；".join(reasons)}

    # 生成（解析与校验失败都重试，最多 3 次）
    system = guide_prompt.build_system_prompt()
    user = guide_prompt.build_user_prompt(p, digest["text"], completeness, digest["missing_sections"])
    last_reason = ""
    full = data = usage = duration = None
    for vtry in range(3):
        t0 = time.time()
        try:
            data, usage = ai.complete_json(system, user, max_tokens=args.max_tokens, retries=args.retries)
        except ai.GenerationError as e:
            return {"cat": cat, "status": "error", "reason": str(e)}
        duration = round(time.time() - t0, 1)

        # 组装完整导读（cat / review / generation 由程序填写，不由模型填写）
        data = normalize_guide(data)
        guide_body = data.get("guide")
        classification = data.get("classification")
        if not isinstance(classification, dict):
            classification = {"fields": [], "keywords": []}
        full = {
            "cat": cat,
            "classification": classification,
            "guide": guide_body,
            "review": {"status": "draft", "last_updated": None,
                       "note": "AI 生成初稿，未经人工复核"},
        }

        ok, errs = guides.validate_guide(full)
        if ok:
            break
        last_reason = "Schema 校验失败：" + "；".join(errs[:5])
        if vtry < 2:
            print(f"  重试 {cat}（第 {vtry + 2} 次）：{last_reason[:80]}")
    else:
        return {"cat": cat, "status": "error", "reason": last_reason}

    full["generation"] = {
        "model": ai.MODEL,
        "prompt_version": args.prompt_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_chars": chars,
        "processed_chars": digest["processed_chars"],
        "completeness": completeness,
        "included_sections": digest["included_sections"],
        "missing_sections": digest["missing_sections"],
        "generated_sections": GENERATED_SECTIONS,
        "analytical_sections": ANALYTICAL_SECTIONS,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "duration_seconds": duration,
    }

    atomic_write_json(GUIDES_DIR / f"{cat}.json", full)
    return {"cat": cat, "status": "ok", "completeness": completeness,
            "tokens": f"{usage.get('input_tokens')}/{usage.get('output_tokens')}",
            "duration": duration}


def _print_result(r):
    if r["status"] == "ok":
        print(f"  ok     {r['cat']}  ({r['completeness']})  tokens={r['tokens']}  {r['duration']}s")
    elif r["status"] == "skip":
        print(f"  跳过   {r['cat']}  {r['reason']}")
    else:
        print(f"  失败   {r['cat']}  {r['reason']}")


def cmd_generate(args, papers, fulltext):
    if not (args.cat or args.cats or args.module):
        print("generate 需指定 --cat / --cats / --module 之一。")
        sys.exit(2)

    cats = select_cats(args, papers)
    if not cats:
        print("没有匹配的论文。")
        return

    if len(cats) > 1 and not args.yes:
        print(f"将对 {len(cats)} 篇生成导读，会调用 DeepSeek 并产生费用。")
        ans = input("确认继续？[y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("已取消。")
            return

    print(f"待生成 {len(cats)} 篇，workers={args.workers}，model={ai.MODEL}\n")

    if args.workers == 1:
        for c in cats:
            _print_result(generate_one(c, papers, fulltext, args))
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(generate_one, c, papers, fulltext, args): c for c in cats}
            for f in as_completed(futs):
                _print_result(f.result())
    print("\n完成。")


# ---------- 入口 ----------

def main(argv=None):
    ap = argparse.ArgumentParser(description="文献导读生成 CLI")
    sub = ap.add_subparsers(dest="command", required=True)

    for name in ("preview", "check"):
        sp = sub.add_parser(name)
        sp.add_argument("--cat")
        sp.add_argument("--module")
        sp.add_argument("--limit", type=int)
        sp.set_defaults(min_chars=guide_prompt.MIN_CHARS)

    gp = sub.add_parser("generate")
    gp.add_argument("--cat")
    gp.add_argument("--cats")
    gp.add_argument("--module")
    gp.add_argument("--limit", type=int)
    gp.add_argument("--force", action="store_true", help="覆盖已有 draft")
    gp.add_argument("--yes", "-y", action="store_true", help="批量生成免确认")
    gp.add_argument("--workers", type=int, default=1, choices=[1, 2, 3])
    gp.add_argument("--min-chars", type=int, default=guide_prompt.MIN_CHARS)
    gp.add_argument("--budget", type=int, default=guide_prompt.DEFAULT_BUDGET)
    gp.add_argument("--max-tokens", type=int, default=6000)
    gp.add_argument("--retries", type=int, default=3)
    gp.add_argument("--prompt-version", default=PROMPT_VERSION)
    gp.set_defaults(min_chars=None)

    args = ap.parse_args(argv)
    if args.command == "generate":
        args.min_chars = args.min_chars or guide_prompt.MIN_CHARS

    papers = load_papers()
    fulltext = load_fulltext()

    if args.command == "preview":
        cmd_preview(args, papers, fulltext)
    elif args.command == "check":
        cmd_check(args, papers, fulltext)
    elif args.command == "generate":
        cmd_generate(args, papers, fulltext)


if __name__ == "__main__":
    main()
