# -*- coding: utf-8 -*-
"""把《区域与城市经济政策案例库.docx》按目录与正文拆成单条案例。"""
import json
import re
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ROOT = Path(__file__).resolve().parent.parent
DOCX = ROOT.parent / "区域与城市经济政策案例库.docx"
OUT = ROOT / "data" / "cases_raw.json"

PUNCT = "，。、：；！？（）()【】《》“”‘’—-…·,. :;!?\"'"

# 脱敏：学号不进入任何派生产物。与 map_cases.py 中的 sanitize 保持一致。
SID_LABELED = re.compile(r"(?:学\s*号)\s*[：:]\s*\d{6,}")
SID_BARE = re.compile(r"(?<!\d)\d{8,}(?!\d)")


def sanitize(text: str) -> str:
    s = SID_LABELED.sub("", text)
    s = SID_BARE.sub("", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"[（(]\s*[）)]", "", s)
    s = re.sub(r"[ \t]+(?=[）)。，、；：])", "", s)
    s = re.sub(r"^姓名\s*[：:]\s*", "", s.strip())
    return s.strip()


def norm(s: str) -> str:
    """标题归一化：全半角统一、去空白和标点。"""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace(" ", " ")
    return "".join(ch for ch in s if ch not in PUNCT and not ch.isspace())


def read_paragraphs():
    with zipfile.ZipFile(DOCX) as z:
        tree = ET.fromstring(z.read("word/document.xml"))
    body = tree.find(W + "body")
    out = []
    for el in body:
        if el.tag == W + "p":
            txt = "".join(x.text or "" for x in el.iter(W + "t")).strip()
            if txt:
                out.append(txt)
    return out


def parse_toc(texts):
    """目录结束于首个正文专题标记（第二个【...】出现处）。"""
    marks = [i for i, t in enumerate(texts) if re.fullmatch(r"【.+?】\d*", t)]
    # 目录里是【专题】页码，正文里是【专题】无页码
    toc_start = None
    for i, t in enumerate(texts):
        if re.fullmatch(r"【.+?】\d+", t):
            toc_start = i
            break
    if toc_start is None:
        raise SystemExit("找不到目录起点")

    toc = []
    topic = None
    for t in texts[toc_start:]:
        m = re.fullmatch(r"【(.+?)】(\d*)", t)
        if m and m.group(2):
            topic = m.group(1)
            continue
        if re.fullmatch(r"【.+?】", t):
            break
        m2 = re.match(r"^(.*?)(\d+)$", t)
        if m2 and topic:
            toc.append({"topic": topic, "title": m2.group(1).strip(), "page": int(m2.group(2))})
    return toc


def split_cases(texts, toc):
    first_topic = None
    for i, t in enumerate(texts):
        if re.fullmatch(r"【.+?】", t) and i > len(texts) * 0.02:
            first_topic = i
            break
    body = texts[first_topic:]

    index = {}
    for item in toc:
        index.setdefault(norm(item["title"]), []).append(item)

    cases = []
    cur_topic = None
    cur = None
    unmatched = []

    for t in body:
        m = re.fullmatch(r"【(.+?)】", t)
        if m:
            cur_topic = m.group(1)
            if cur:
                cases.append(cur)
                cur = None
            continue

        key = norm(t)
        hit = index.get(key)
        if hit:
            item = hit.pop(0)
            if cur:
                cases.append(cur)
            cur = {
                "topic": item["topic"],
                "title": item["title"],
                "page": item["page"],
                "paragraphs": [],
            }
            continue

        if cur:
            cur["paragraphs"].append(t)
        elif t.strip():
            unmatched.append(t)

    if cur:
        cases.append(cur)

    return cases, unmatched


def main():
    texts = read_paragraphs()
    toc = parse_toc(texts)
    cases, unmatched = split_cases(texts, toc)

    print(f"目录条目 {len(toc)}，正文拆出 {len(cases)}")
    matched = {norm(c["title"]) for c in cases}
    missing = [t for t in toc if norm(t["title"]) not in matched]
    if missing:
        print(f"未在正文定位到的目录条目 {len(missing)}：")
        for m in missing:
            print("   ", m["topic"], "|", m["title"])

    for c in cases:
        c["paragraphs"] = [sanitize(p) for p in c["paragraphs"]]
        c["paragraphs"] = [p for p in c["paragraphs"] if p]
        c["char_count"] = sum(len(p) for p in c["paragraphs"])

    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {OUT}")
    print("\n各专题案例数与字数：")
    stat = {}
    for c in cases:
        s = stat.setdefault(c["topic"], [0, 0])
        s[0] += 1
        s[1] += c["char_count"]
    for k, (n, ch) in stat.items():
        print(f"  {k}: {n} 个，{ch} 字")


if __name__ == "__main__":
    main()
