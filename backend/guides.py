# -*- coding: utf-8 -*-
"""文献导读：加载与合并。

导读内容存 data/guides/{cat}.json，只放分类、分析、审阅状态；书目信息仍在
data/papers.json（唯一真值），这里只按 cat 合并。阅读状态、笔记、书签是每个
用户自己的东西，放浏览器 localStorage，不进这里。

导读 JSON 结构（每篇一个文件）：

    {
      "cat": "B-004",
      "classification": {"fields": [], "keywords": []},
      "guide": {
        "overview":    {"research_motivation", "research_question", "hypotheses",
                        "main_findings", "contributions"},
        "mechanism":   {"theoretical_foundations", "key_assumptions", "mechanisms",
                        "variable_relationships", "flow"},
        "methods":     {"paper_type", "data_sources", "sample_period", "variables",
                        "econometric_models", "identification_strategy",
                        "endogeneity_treatments", "robustness_checks",
                        "key_tables_figures"},
        "critique":    {"theoretical_contributions", "methodological_strengths",
                        "limitations", "identification_problems",
                        "alternative_explanations", "unresolved_questions",
                        "follow_up_topics"},
        "key_concepts": [], "reading_recommendations": []
      },
      "review": {"status", "last_updated", "note"}
    }

review.status 取值 pending | draft | reviewed。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUIDES_DIR = ROOT / "data" / "guides"


def list_guides():
    """扫描 data/guides/*.json，返回 {cat: guide_dict}。坏文件跳过并提示。"""
    out = {}
    if not GUIDES_DIR.is_dir():
        return out
    for p in sorted(GUIDES_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            print(f"导读解析失败，已跳过：{p.name}")
            continue
        cat = d.get("cat") or p.stem
        if cat:
            out[cat] = d
    return out


def get_guide(cat):
    """取单篇导读；文件不存在或解析失败返回 None。"""
    p = GUIDES_DIR / f"{cat}.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def guide_overview(guide):
    """卡片上的一行研究概述，取 overview.research_motivation。"""
    if not guide:
        return ""
    ov = (guide.get("guide") or {}).get("overview") or {}
    return ov.get("research_motivation") or ""


def guide_fields(guide):
    """研究领域标签，取 classification.fields。"""
    if not guide:
        return []
    return (guide.get("classification") or {}).get("fields") or []


# ---------- 校验 ----------

# 四个 Tab 的字段类型：str 字符串，list 字符串数组。所有字段都要求存在。
_GUIDE_SECTIONS = {
    "overview": {
        "research_motivation": "str",
        "research_question": "str",
        "hypotheses": "list",
        "main_findings": "list",
        "contributions": "list",
    },
    "mechanism": {
        "theoretical_foundations": "str",
        "key_assumptions": "list",
        "mechanisms": "list",
        "variable_relationships": "str",
        "flow": "list",
    },
    "methods": {
        "paper_type": "str",
        "data_sources": "str",
        "sample_period": "str",
        "variables": "list",
        "econometric_models": "str",
        "identification_strategy": "str",
        "endogeneity_treatments": "str",
        "robustness_checks": "str",
        "key_tables_figures": "list",
    },
    "critique": {
        "theoretical_contributions": "str",
        "methodological_strengths": "str",
        "limitations": "list",
        "identification_problems": "str",
        "alternative_explanations": "str",
        "unresolved_questions": "list",
        "follow_up_topics": "list",
    },
}

VALID_STATUS = {"pending", "draft", "reviewed"}


def validate_guide(guide):
    """校验导读结构，返回 (ok, errors)。

    只做结构校验：必需的顶层键、四个 Tab、字段类型与存在性。空字符串/空列表
    视为结构合法——内容完整度由 generation.completeness 与人工审阅把关。
    """
    errors = []
    if not isinstance(guide, dict):
        return False, ["导读不是 JSON 对象"]

    if not guide.get("cat"):
        errors.append("缺少 cat")

    g = guide.get("guide")
    if not isinstance(g, dict):
        errors.append("缺少 guide 对象")
    else:
        for section, spec in _GUIDE_SECTIONS.items():
            sec = g.get(section)
            if not isinstance(sec, dict):
                errors.append(f"guide.{section} 缺失或不是对象")
                continue
            for field, ftype in spec.items():
                if field not in sec:
                    errors.append(f"guide.{section}.{field} 缺失")
                    continue
                val = sec[field]
                if ftype == "str" and not isinstance(val, str):
                    errors.append(f"guide.{section}.{field} 应为字符串")
                elif ftype == "list" and not isinstance(val, list):
                    errors.append(f"guide.{section}.{field} 应为列表")
        for field in ("key_concepts", "reading_recommendations"):
            if field not in g:
                errors.append(f"guide.{field} 缺失")
            elif not isinstance(g[field], list):
                errors.append(f"guide.{field} 应为列表")

    review = guide.get("review")
    if not isinstance(review, dict):
        errors.append("缺少 review 对象")
    elif review.get("status") not in VALID_STATUS:
        errors.append(f"review.status 取值非法：{review.get('status')!r}")

    return (len(errors) == 0), errors
