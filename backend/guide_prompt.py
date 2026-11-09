# -*- coding: utf-8 -*-
"""导读生成：论文分块、完整性判断与 Prompt。

分块原则：优先保留摘要、引言、理论框架、数据、研究设计、识别策略、实证结果、
稳健性检验与结论。章节识别失败时不假装完整，如实标记缺失章节；完整性判断
必须基于实际识别出的章节，而不是只看字符数量。
"""
import re

DEFAULT_BUDGET = 45000
MIN_CHARS = 5000

# 章节类别 → 字符预算。references/appendix 为 0 表示丢弃。
SECTION_BUDGET = {
    "abstract": 3000,
    "intro": 9000,
    "theory": 9000,
    "data": 6000,
    "methods": 9000,
    "results": 7000,
    "robustness": 5000,
    "conclusion": 4000,
    "other": 2500,
    "references": 0,
    "appendix": 0,
}

# 用于报告「缺失章节」的标准章节集合
STANDARD_SECTIONS = [
    "abstract", "intro", "theory", "data", "methods", "results", "robustness", "conclusion",
]

# 章节关键词 → 类别。匹配时按 key 长度从长到短。
_SECTION_WORDS = {
    "abstract": "abstract",
    "introduction": "intro",
    "background": "intro",
    "motivation": "intro",
    "literature review": "intro",
    "related literature": "intro",
    "theoretical framework": "theory",
    "conceptual framework": "theory",
    "theory": "theory",
    "econometric model": "methods",
    "empirical model": "methods",
    "empirical strategy": "methods",
    "identification strategy": "methods",
    "identification": "methods",
    "estimation": "methods",
    "methodology": "methods",
    "methods": "methods",
    "model": "theory",
    "data and descriptive statistics": "data",
    "descriptive statistics": "data",
    "data": "data",
    "sample": "data",
    "variables": "data",
    "variable definitions": "data",
    "main results": "results",
    "empirical results": "results",
    "results": "results",
    "findings": "results",
    "robustness checks": "robustness",
    "robustness": "robustness",
    "sensitivity": "robustness",
    "conclusions": "conclusion",
    "conclusion": "conclusion",
    "discussion": "conclusion",
    "references": "references",
    "appendices": "appendix",
    "appendix": "appendix",
}

_KEYWORD_ORDER = sorted(_SECTION_WORDS.keys(), key=len, reverse=True)

# 这些词很少作为正文句首，允许「标题 + 正文」并在一行时按标题切分
_MERGED_HEADERS = ["introduction", "conclusion", "conclusions",
                   "references", "appendix", "appendices", "abstract"]


def _classify(low):
    """按关键词给一行文本归类。"""
    for kw in _KEYWORD_ORDER:
        if kw in low:
            return _SECTION_WORDS[kw]
    return "other"


def _header(s):
    """判断一行是否是章节标题，返回 (is_header, category)。

    带点的编号（1. / 3.1 / I.）直接当标题；无点的裸编号（1 Introduction 或
    脚注 3 See）只有短行或含章节关键词时才当标题，排除脚注编号。
    """
    low = s.lower()
    if re.match(r'^\d{1,2}(?:\.\d{1,2})*\.\s+\S', s) or re.match(r'^[IVX]{1,5}\.\s+\S', s):
        return True, _classify(low)
    if re.match(r'^\d{1,2}\s+\S', s):
        cat = _classify(low)
        if len(s) <= 60 or cat != "other":
            return True, cat
        return False, None
    # 标题与正文并在一行：「Introduction Regional science has turned 40...」
    for kw in _MERGED_HEADERS:
        if low.startswith(kw + " "):
            return True, _SECTION_WORDS[kw]
    if len(s) <= 90:
        for kw, cat in _SECTION_WORDS.items():
            if low.startswith(kw):
                rest = low[len(kw):]
                if rest == "" or rest[0] in " :.·-–—(":
                    return True, cat
    return False, None


def digest_paper(text, budget=DEFAULT_BUDGET):
    """章节感知分块。返回：

    text            分块后的正文
    processed_chars 实际送入模型的字符数
    included_sections  识别并保留的章节类别
    missing_sections   标准章节中未识别到的
    section_split_ok   章节识别是否可信（识别出 >= 2 个标题）
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    tagged = []
    for ln in lines:
        s = ln.strip()
        if not s:
            tagged.append((False, None, ln))
            continue
        is_h, cat = _header(s)
        tagged.append((is_h, cat, ln))

    sections = []
    cur_cat, cur_lines = "front", []
    header_count = 0
    for is_h, cat, ln in tagged:
        if is_h:
            if cur_lines:
                sections.append((cur_cat, cur_lines))
            cur_cat = cat or "other"
            cur_lines = [ln]
            header_count += 1
        else:
            cur_lines.append(ln)
    if cur_lines:
        sections.append((cur_cat, cur_lines))

    # 若最前面是 front（无标题的前置内容），且含 abstract 字样，则当作摘要。
    # 有的提取把标签写成 "a b s t r a c t"，去掉空格再判断。
    if sections and sections[0][0] == "front":
        front_text = "\n".join(sections[0][1]).lower()
        if "abstract" in front_text or "abstract" in re.sub(r"\s+", "", front_text):
            sections[0] = ("abstract", sections[0][1])

    section_split_ok = header_count >= 2
    whole = "\n".join(ln for _, _, ln in tagged)

    def whole_text():
        clipped = whole[:min(budget, 30000)]
        return {
            "text": clipped,
            "processed_chars": len(clipped),
            "included_sections": [],
            "missing_sections": list(STANDARD_SECTIONS),
            "section_split_ok": False,
        }

    # 无章节标题（如 JEP 杂志体例）：不给模型 2500 字碎片，给足预算，
    # 但如实标记 partial —— 没有章节证据，只依据正文内容保守填写。
    if not section_split_ok:
        return whole_text()

    # 预算分配：每段先给一个下限，剩余按优先级填充。保证 results / robustness /
    # conclusion 等靠后章节也有内容，不被前面的摘要与引言吃光。
    FLOOR = 800
    PRIORITY = ["intro", "methods", "results", "theory", "conclusion",
                "robustness", "data", "abstract", "other", "front"]
    alloc = {}
    remaining = budget
    idxs = []
    for i, (cat, lns) in enumerate(sections):
        cap = SECTION_BUDGET.get(cat, SECTION_BUDGET["other"])
        if cap == 0:
            alloc[i] = 0
            continue
        a = min(cap, FLOOR)
        alloc[i] = a
        remaining -= a
        idxs.append(i)

    for cat in PRIORITY:
        if remaining <= 0:
            break
        for i in idxs:
            if sections[i][0] != cat:
                continue
            cap = SECTION_BUDGET.get(cat, SECTION_BUDGET["other"])
            gap = cap - alloc[i]
            if gap <= 0:
                continue
            give = min(gap, remaining)
            alloc[i] += give
            remaining -= give
            if remaining <= 0:
                break

    kept, seen = [], set()
    for i, (cat, lns) in enumerate(sections):
        a = alloc.get(i, 0)
        if a <= 0:
            continue
        block = "\n".join(lns)[:a]
        kept.append(block)
        if block.strip():
            seen.add(cat)

    assembled = "\n\n".join(kept)

    # 结构章节太少、实际用上的正文不足，说明分块没覆盖论文主体。
    # 与其给模型一点碎片，不如给全文（上限 3 万字），并如实标 partial。
    if len(assembled) < 12000 and len(whole) > 30000:
        return whole_text()

    included = sorted(c for c in seen if c not in ("front", "other"))
    missing = [c for c in STANDARD_SECTIONS if c not in seen]

    return {
        "text": assembled,
        "processed_chars": len(assembled),
        "included_sections": included,
        "missing_sections": missing,
        "section_split_ok": section_split_ok,
    }


def judge_completeness(ft, digest, min_chars=MIN_CHARS):
    """判断正文完整度，返回 (level, reasons)。

    full         关键章节基本齐备，可支撑完整导读
    partial      有正文，但部分关键章节缺失
    insufficient 不足以支撑可靠导读，禁止生成
    """
    body = (ft.get("body") or "").strip()
    note = ft.get("note") or ""
    char_count = ft.get("char_count") or len(body)

    if not body:
        return "insufficient", ["无正文"]
    if ft.get("extracted") is False or "未提取" in note or "文件缺失" in note:
        return "insufficient", [f"提取不完整：{note or '未提取到文字'}"]
    if char_count < min_chars:
        return "insufficient", [f"正文过短（{char_count} 字 < {min_chars}）"]

    if not digest.get("section_split_ok"):
        return "partial", ["章节识别失败，无法确认各章节齐备"]

    inc = set(digest.get("included_sections") or [])
    has_intro = "abstract" in inc or "intro" in inc
    has_analysis = bool({"data", "methods", "theory"} & inc)   # 能写 Methods / Mechanism
    has_outcome = bool({"results", "conclusion"} & inc)         # 能写主要发现

    if not has_intro:
        # 正文充足但识别不到摘要/引言标题，多半是标题与正文合并或标签丢失，
        # 归为 partial 而非 insufficient——正文仍在，模型仍可读到。
        return "partial", ["未识别到摘要/引言标题（可能已包含在正文前部）"]

    if has_intro and has_analysis and has_outcome:
        return "full", []

    reasons = []
    if not has_analysis:
        reasons.append("缺少方法与理论内容")
    if not has_outcome:
        reasons.append("缺少结果与结论")
    missing = [c for c in ("methods", "results", "robustness", "conclusion") if c not in inc]
    if missing:
        reasons.append("缺少章节：" + "、".join(missing))
    return "partial", reasons


# ---------- Prompt ----------

_OUTPUT_SCHEMA = """{
  "classification": { "fields": ["研究领域"], "keywords": ["关键词"] },
  "guide": {
    "overview": {
      "research_motivation": "研究动机",
      "research_question": "核心研究问题",
      "hypotheses": ["研究假说"],
      "main_findings": ["主要发现"],
      "contributions": ["学术贡献"]
    },
    "mechanism": {
      "theoretical_foundations": "理论基础",
      "key_assumptions": ["关键假设"],
      "mechanisms": ["核心经济机制"],
      "variable_relationships": "变量间关系",
      "flow": ["机制链，如：A → B"]
    },
    "methods": {
      "paper_type": "empirical 或 theoretical",
      "data_sources": "数据来源",
      "sample_period": "样本区间",
      "variables": ["变量定义"],
      "econometric_models": "计量模型",
      "identification_strategy": "识别策略",
      "endogeneity_treatments": "内生性处理",
      "robustness_checks": "稳健性检验",
      "key_tables_figures": ["重要图表"]
    },
    "critique": {
      "theoretical_contributions": "理论贡献",
      "methodological_strengths": "方法优势",
      "limitations": ["研究局限"],
      "identification_problems": "识别问题",
      "alternative_explanations": "替代解释",
      "unresolved_questions": ["未解决问题"],
      "follow_up_topics": ["后续研究方向"]
    },
    "key_concepts": ["核心概念"],
    "reading_recommendations": ["延伸阅读"]
  }
}"""


def build_system_prompt():
    return (
        "你是区域经济学课程的学术文献导读助手。根据给定的论文文本，生成结构化的文献导读。\n\n"
        "## 硬性规则\n"
        "1. 所有事实性陈述必须能在给定原文中找到依据，不得补充原文没有的信息。\n"
        "2. 不得编造样本量、变量定义、回归结果、计量模型、识别策略、研究结论、作者与引用。\n"
        "3. 无法从原文确认的内容，一律写「原文未说明」或「无法从现有文本确认」，不要猜测。\n"
        "4. 严格区分作者原文观点与你的分析判断。critique 一栏完全是你的分析，不是作者观点。\n"
        "5. 理论论文用理论模型框架（假设、均衡条件、命题）填写 methods，实证字段填「不适用（理论论文）」；"
        "实证论文才填写数据、识别、内生性、稳健性。\n"
        "6. 如果正文不完整，只填能确认的内容，无法确认的字段写「原文未说明」，并在 critique 的 limitations 里说明导读的局限。\n"
        "7. 只输出一个 JSON 对象，不要输出任何解释、前言或 markdown 代码围栏。字段名必须与 Schema 完全一致。\n"
        "8. 字段类型必须严格遵循 Schema：Schema 中示例为字符串的字段（如 robustness_checks、"
        "identification_strategy）必须返回单个字符串，不得返回数组；示例为数组的字段必须返回数组。\n\n"
        "## 输出 Schema（严格 JSON）\n"
        + _OUTPUT_SCHEMA
    )


def build_user_prompt(paper, digest_text, completeness, missing_sections):
    """构造 user 消息：元数据 + 完整性说明 + 分块正文。"""
    missing = "、".join(missing_sections) if missing_sections else "无"
    meta = (
        f"- 编目号：{paper.get('cat')}\n"
        f"- 标题：{paper.get('title')}"
        + (f"（{paper.get('cn')}）" if paper.get("cn") else "") + "\n"
        f"- 作者：{paper.get('authors') or '未记录'}\n"
        f"- 年份：{paper.get('year') or '未记录'}\n"
        f"- 期刊：{paper.get('venue') or '未记录'}\n"
        f"- 类型：{paper.get('type') or '未记录'}\n"
    )
    return (
        "## 论文信息\n" + meta +
        "\n## 正文完整性\n"
        f"完整性：{completeness}。缺失章节：{missing}。\n"
        "若标注为 partial，只依据已给出的文本填写，缺失信息写「原文未说明」。\n"
        "\n## 论文正文（已按章节分块节选，顺序保留）\n" + digest_text
    )
