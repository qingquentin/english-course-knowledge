# -*- coding: utf-8 -*-
"""把案例作者替换为匿名编号。

默认写到 data/cases.anon.json，不碰原文件；确认要公开脱敏版本后再加 --in-place。
只处理 author 字段。正文段落里如果出现姓名，本脚本不扫描，需人工确认。

用法：
    python scripts/anonymize_authors.py            # 输出 data/cases.anon.json
    python scripts/anonymize_authors.py --in-place # 覆盖 data/cases.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "cases.json"
OUT = ROOT / "data" / "cases.anon.json"


def anon_name(case_id: str) -> str:
    """CASE-003 -> 匿名作者003。与案例编号绑定，稳定可回溯。"""
    return f"匿名作者{case_id.split('-')[-1]}"


def main():
    inplace = "--in-place" in sys.argv
    cases = json.loads(SRC.read_text(encoding="utf-8"))

    changed = 0
    for c in cases:
        if c.get("author"):
            c["author"] = anon_name(c["id"])
            changed += 1

    target = SRC if inplace else OUT
    target.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"共 {len(cases)} 条案例，替换作者 {changed} 条，未署名的不动")
    print(f"已写入 {target}")
    if inplace:
        print("原文件已覆盖。重建页面：python scripts/build.py；后端下次启动自动重建数据库。")


if __name__ == "__main__":
    main()
