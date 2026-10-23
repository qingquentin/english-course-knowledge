# -*- coding: utf-8 -*-
"""从线上部署页提取 DATA，拆成 modules.json / papers.json，并把页面拆成模板。"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "template" / "_source.html"
DATA_DIR = ROOT / "data"


def brace_slice(text: str, start: int) -> str:
    """从 text[start] 处的 { 开始，返回配平的 JSON 对象字符串。"""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("未找到配平的 JSON 对象")


def main():
    html = SRC.read_text(encoding="utf-8")
    idx = html.find("const DATA = ")
    if idx < 0:
        raise SystemExit("页面里没有 const DATA")
    brace = html.find("{", idx)
    raw = brace_slice(html, brace)
    data = json.loads(raw)

    modules = data["modules"]
    papers = data["papers"]

    # 统计校正：module.count 以实际条目为准
    for m in modules:
        m["count"] = sum(1 for p in papers if p["m"] == m["id"])

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "modules.json").write_text(
        json.dumps(modules, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DATA_DIR / "papers.json").write_text(
        json.dumps(papers, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 生成模板：把 DATA 字面量替换成占位符
    tpl = html[:brace] + "__DATA__" + html[brace + len(raw) :]
    (ROOT / "template" / "index.template.html").write_text(tpl, encoding="utf-8")

    print(f"模块 {len(modules)} 个，文献 {len(papers)} 篇")
    print("模板已生成 template/index.template.html")
    for m in modules:
        print(f"  {m['id']} {m['name']} {m['count']}")


if __name__ == "__main__":
    main()
