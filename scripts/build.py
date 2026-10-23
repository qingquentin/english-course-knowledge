# -*- coding: utf-8 -*-
"""合并数据并渲染 index.html。资料更新后重跑本脚本即可。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TPL = ROOT / "template" / "index.template.html"
OUT = ROOT / "index.html"


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def main():
    modules = load("modules.json")
    papers = load("papers.json")
    cases = load("cases.json")

    for m in modules:
        m["count"] = sum(1 for p in papers if p["m"] == m["id"])
        m["caseCount"] = sum(1 for c in cases if c["m"] == m["id"])

    payload = {"modules": modules, "papers": papers, "cases": cases}

    tpl = TPL.read_text(encoding="utf-8")

    # 先替换标量占位符，再注入 JSON（避免 JSON 里的字样被误替换）
    for mid in "ABCD":
        n = next(m["count"] for m in modules if m["id"] == mid)
        tpl = tpl.replace(f"__N{mid}__", str(n))

    tpl = tpl.replace("__N_PAPERS__", str(len(papers)))
    tpl = tpl.replace("__N_CASES__", str(len(cases)))

    if "__DATA__" not in tpl:
        raise SystemExit("模板缺少 __DATA__ 占位符")

    data_js = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # 防止 JSON 内的 </script> 提前闭合
    data_js = data_js.replace("</", "<\\/")

    tpl = tpl.replace("__DATA__", data_js)
    OUT.write_text(tpl, encoding="utf-8")

    print(f"已生成 {OUT}")
    print(f"  文献 {len(papers)} 篇，案例 {len(cases)} 个，文件 {OUT.stat().st_size/1024:.0f} KB")
    for m in modules:
        print(f"  {m['id']} {m['name']}: {m['count']} 篇 + {m['caseCount']} 例")


if __name__ == "__main__":
    main()
