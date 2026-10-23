# -*- coding: utf-8 -*-
"""把拆出的案例映射到四模块二十子类，清理模板字样，抽取作者。"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "cases_raw.json"
OUT = ROOT / "data" / "cases.json"

# 标题关键词 -> (模块, 子类)。按顺序匹配，先命中者生效。
MAPPING = [
    ("蒙古经济发展状况", "B", "区域差距与区域发展"),
    ("越南区域经济差距", "B", "区域差距与区域发展"),
    ("哈萨克斯坦区域经济差异研究", "B", "区域差距与区域发展"),
    ("哈萨克斯坦区域经济差异与均衡发展", "B", "区域差距与区域发展"),
    ("中巴经济走廊", "C", "跨区域一体化与边界效应"),
    ("长三角地区对口合作", "C", "跨区域一体化与边界效应"),
    ("俄罗斯远东地区发展政策", "C", "区域政策与地方导向政策"),
    ("田纳西流域", "C", "区域政策与地方导向政策"),
    ("加纳区域经济发展挑战", "C", "区域政策与地方导向政策"),
    ("德国创新区域政策", "A", "科技创新空间"),
    ("摩城为例", "A", "科技创新空间"),
    ("宽带中国", "A", "科技创新空间"),
    ("罗切斯特高科技集群", "A", "科技创新空间"),
    ("法国竞争力集群", "A", "科技创新空间"),
    ("拉各斯城市化", "A", "城市政策与空间干预"),
    ("冈比亚的城市化", "A", "城市空间结构与密度"),
    ("俄罗斯城市化进程", "A", "城市空间结构与密度"),
    ("河内快速公交", "D", "交通与可达性"),
    ("金边市解决城市拥堵", "D", "基础设施投融资"),
    ("卡拉奇城市治理", "A", "城市政策与空间干预"),
    ("基里巴斯气候变化", "A", "城市政策与空间干预"),
    ("土耳其城市综合发展战略", "A", "城市政策与空间干预"),
    ("榴莲发展框架", "A", "城市政策与空间干预"),
    ("巴基斯坦主要城市", "A", "城市政策与空间干预"),
    ("越南智慧城市", "A", "城市政策与空间干预"),
    ("低碳城市试点", "A", "城市政策与空间干预"),
    ("津巴布韦城市土地政策", "D", "土地价值与建筑高度"),
    ("越南城市化进程中的土地利用", "D", "土地价值与建筑高度"),
    ("阿塞拜疆工业园区", "C", "开发区与经济特区"),
    ("泰国经济特区", "C", "开发区与经济特区"),
    ("波兰经济特区", "C", "开发区与经济特区"),
    ("苏联科学城", "C", "开发区与经济特区"),
    ("深圳经济特区", "C", "开发区与经济特区"),
    ("坦桑尼亚迁都", "C", "区域政策与地方导向政策"),
    ("缅甸迁都", "C", "区域政策与地方导向政策"),
    ("密歇根州研发贷款", "C", "税收激励与财政竞争"),
    ("底特律社区企业区", "C", "税收激励与财政竞争"),
    ("德国区域财政政策", "C", "税收激励与财政竞争"),
    ("挪威差异化工资税", "C", "税收激励与财政竞争"),
    ("法国ZFU计划", "C", "税收激励与财政竞争"),
    ("印度北阿坎德", "C", "区域政策与地方导向政策"),
    ("意大利", "B", "创业生态与知识网络"),
    ("EPSCoR", "B", "创业生态与知识网络"),
    ("斯坦福大学", "B", "创业生态与知识网络"),
]

# 跨主题副标签
EXTRA_TAGS = {
    "宽带中国": ["数字经济与数字空间"],
    "越南智慧城市": ["数字经济与数字空间"],
    "田纳西流域": ["基础设施投融资"],
    "苏联科学城": ["科技创新空间"],
    "EPSCoR": ["区域政策与地方导向政策"],
    "金边市解决城市拥堵": ["交通与可达性"],
}

BOILERPLATE = re.compile(r"^(课程信息|任课老师|由任课老师)")
HEAD_LIKE = re.compile(
    r"^(摘要|关键词|一[、．.]|二[、．.]|三[、．.]|第\d+章|第[一二三四五六七八九十]+章|"
    r"\d+[、．.]|背景|引言|研究背景|政策背景)"
)

# 脱敏：学号不进入公开数据，姓名保留
SID_LABELED = re.compile(r"(?:学\s*号)\s*[：:]\s*\d{6,}")
SID_BARE = re.compile(r"(?<!\d)\d{8,}(?!\d)")
NAME_LABEL = re.compile(r"^姓名\s*[：:]\s*")


def sanitize(text: str) -> str:
    """去掉学号，并清理删除后留下的多余空格与空括号。"""
    s = SID_LABELED.sub("", text)
    s = SID_BARE.sub("", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"[（(]\s*[）)]", "", s)
    s = re.sub(r"[ \t]+(?=[）)。，、；：])", "", s)
    s = NAME_LABEL.sub("", s.strip())
    return s.strip()


def looks_like_author(p: str) -> bool:
    s = p.strip()
    if not s or len(s) > 40:
        return False
    # 姓名：X 学号：Y 形式，先于标点判断
    if "姓名" in s or "学号" in s:
        return True
    if re.search(r"[。！？；：]", s):
        return False
    if HEAD_LIKE.match(s):
        return False
    if s.startswith(("论文", "本文", "该论文", "围绕", "《", "摘要")):
        return False
    # 纯人名：中文 2-4 字，或拉丁字母组合，可能带学号
    if re.fullmatch(r"[一-龥]{2,4}\s*\d{6,}", s):
        return True
    if re.fullmatch(r"[一-龥]{2,4}", s):
        return True
    if re.fullmatch(r"[A-Za-z][A-Za-z .,，·\-]{2,38}", s):
        return True
    return False


def clean_author(s: str) -> dict:
    """只保留姓名，学号一律不写入数据。"""
    name = sanitize(s)
    name = re.sub(r"\d{6,}", "", name)
    name = name.strip(" ，,、·")
    return {"author": name, "student_id": ""}


def main():
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    cases = []
    unmatched = []

    for i, c in enumerate(raw, start=1):
        title = c["title"]
        hit = next(((m, s) for kw, m, s in MAPPING if kw in title), None)
        if not hit:
            unmatched.append(title)
            hit = ("", "")
        m, sub = hit

        paras = [p for p in c["paragraphs"] if not BOILERPLATE.match(p.strip())]
        author = {"author": "", "student_id": ""}
        if paras and looks_like_author(paras[0]):
            author = clean_author(paras[0])
            paras = paras[1:]
        paras = [sanitize(p) for p in paras]
        paras = [p for p in paras if p]

        extra = next((v for kw, v in EXTRA_TAGS.items() if kw in title), [])
        body = "\n".join(paras)

        cases.append({
            "id": f"CASE-{i:03d}",
            "m": m,
            "sub": sub,
            "source_topic": c["topic"],
            "title": title,
            "author": author["author"],
            "student_id": author["student_id"],
            "page": c["page"],
            "tags": extra,
            "paragraphs": paras,
            "char_count": len(body),
        })

    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"案例 {len(cases)} 条，已写入 {OUT}")
    if unmatched:
        print("未匹配模块的案例：", unmatched)

    from collections import Counter
    print("\n模块分布：", Counter(c["m"] for c in cases))
    print("子类分布：")
    for (m, sub), n in sorted(Counter((c["m"], c["sub"]) for c in cases).items()):
        print(f"  {m} {sub}: {n}")
    print("\n作者抽取：")
    for c in cases:
        flag = "" if c["author"] else "  ← 未识别"
        print(f"  {c['id']} {c['title'][:26]:<28} {c['author'] or '—'}{flag}")


if __name__ == "__main__":
    main()
