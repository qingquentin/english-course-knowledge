# -*- coding: utf-8 -*-
"""不调模型的离线测试。

CI 和提交前跑这个，验证切词、检索门槛与推荐仍然符合预期，不花 API 额度。
真调模型的端到端验收另见 smoke_test.py。

用法（在 backend 目录）：
    python test_offline.py
"""
import sys

import db
import retriever

passed, failed = 0, 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}" + (f"  -> {detail}" if detail else ""))


def main():
    db.seed()
    engine = retriever.engine()
    print(f"\n索引就绪：{len(engine.docs)} 条\n")

    # 切词
    t = retriever.tokens("宽带中国 machine learning")
    check("汉字二元组", "宽带" in t and "中国" in t, str(t[:8]))
    check("整段中文保留", "宽带中国" in t, str(t[:8]))
    check("拉丁词", "machine" in t and "learning" in t, str(t[:8]))
    check("单字不入索引", retriever.tokens("的") == [])

    # 检索：命中与排序
    rs = retriever.search("宽带中国战略的实施效果如何", 3)
    check("宽带中国命中案例正文", bool(rs) and rs[0]["id"] == "CASE-012",
          str([r["id"] for r in rs]))

    rs = retriever.search("税收激励与财政竞争", 6)
    check("税收激励召回不少于 4 条", len(rs) >= 4, str(len(rs)))
    check("税收激励结果都在模块 C", all(r["module"] == "C" for r in rs),
          str([(r["id"], r["module"]) for r in rs]))

    rs = retriever.search("机器学习识别城市", 5)
    check("机器学习命中 B-014/B-015",
          {r["id"] for r in rs[:2]} == {"B-014", "B-015"},
          str([r["id"] for r in rs]))

    # 检索：拒答门槛
    check("库外问题返回空（火星）", retriever.search("火星殖民的可行性") == [])
    check("库外问题返回空（天气）", retriever.search("今天天气怎么样") == [])
    check("单字查询不抛错", isinstance(retriever.search("的"), list))

    # 推荐
    recs = retriever.recommend("CASE-012", 5)
    check("推荐有结果", len(recs) >= 3, str(len(recs)))
    check("推荐不含自身", all(r["id"] != "CASE-012" for r in recs),
          str([r["id"] for r in recs]))

    print(f"\n通过 {passed} 项，失败 {failed} 项")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
