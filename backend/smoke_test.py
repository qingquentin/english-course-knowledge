# -*- coding: utf-8 -*-
"""端到端验收：对着运行中的服务跑几个真实问题，检查检索、引用与拒答。

用法（服务已启动）：
    python smoke_test.py [http://127.0.0.1:8000]
"""
import json
import re
import sys
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")

CASES = [
    ("宽带中国战略的实施效果如何？", "命中案例正文，答案带 [n] 引用"),
    ("哪些案例讨论了税收激励与财政竞争？", "命中多条 C 模块材料"),
    ("库里有关于机器学习识别城市的文献吗？", "命中 B-014 / B-015，只复述题录"),
    ("火星殖民的可行性", "拒答，来源为空"),
]


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def ask(question):
    req = urllib.request.Request(
        BASE + "/api/ask",
        data=json.dumps({"question": question}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    answer, sources, err = "", [], ""
    event = ""
    with urllib.request.urlopen(req, timeout=180) as r:
        for raw in r:
            line = raw.decode("utf-8").strip()
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip() or "{}")
                if event == "sources":
                    sources = data.get("sources", [])
                elif event == "delta":
                    answer += data.get("text", "")
                elif event == "error":
                    err = data.get("message", "")
                elif event == "done" and data.get("empty"):
                    answer = data.get("answer", "")
    return answer, sources, err


def main():
    stats = get("/api/stats")
    print(f"服务 {BASE}")
    print(f"模块 {stats['modules']} · 文献 {stats['papers']} · 案例 {stats['cases']} · "
          f"模型 {stats['model']} · key {'已配置' if stats['aiConfigured'] else '未配置'}\n")
    if not stats["aiConfigured"]:
        print("未配置 DEEPSEEK_API_KEY，问答无法实测。")
        return 1

    failed = 0
    for q, expect in CASES:
        answer, sources, err = ask(q)
        should_refuse = "拒答" in expect
        cited = sorted({int(n) for n in re.findall(r"\[(\d{1,2})\]", answer)})
        print(f"问：{q}")
        print(f"  预期：{expect}")
        print(f"  来源：{len(sources)} 条  " + "、".join(s["id"] for s in sources[:6]))
        print(f"  答案：{(answer or err or '（空）')[:240].replace(chr(10), ' ')}")
        print()

        if err:
            print(f"  ✗ 调用失败：{err}\n")
            failed += 1
            continue
        if should_refuse:
            if sources:
                print("  ✗ 应拒答却返回了来源\n")
                failed += 1
        else:
            if not sources:
                print("  ✗ 没有检索到来源\n")
                failed += 1
            elif not cited:
                print("  ✗ 答案没标引用编号\n")
                failed += 1
            elif max(cited) > len(sources):
                print(f"  ✗ 引用了不存在的来源 [{max(cited)}]\n")
                failed += 1

    print("全部通过" if not failed else f"{failed} 项不符合预期")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
