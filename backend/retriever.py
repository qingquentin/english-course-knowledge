# -*- coding: utf-8 -*-
"""库内检索。

不用 SQLite FTS：默认分词器不切中文。语料只有 44 篇案例正文加 100 条文献题录，
启动时在内存里建一张倒排索引，按拉丁词与汉字二元组打分即可，秒级完成。

对外两个入口：
  search(query, k)       按问题找材料
  recommend(item_id, k)  按一条材料找相近材料
"""
import math
import re
from collections import Counter, defaultdict

import db

CJK = re.compile(r"[一-鿿]+")
LATIN = re.compile(r"[a-z][a-z0-9\-]+")

# 只过滤纯功能词，专业词一律保留
STOP = {
    "什么", "如何", "哪些", "怎么", "怎样", "请问", "介绍", "一下", "这个", "那个",
    "我们", "你们", "他们", "可以", "是否", "关于", "以及", "还有", "一个", "一些",
    "没有", "主要", "内容", "相关", "文献", "案例", "知识", "库里", "库中", "讲的",
    "说了", "意思", "有没", "是不", "不是", "就是", "并且", "或者", "但是", "因为",
    "所以", "如果", "其中", "进行", "通过", "对于", "问题", "方面", "情况", "研究",
    "分析", "文章", "论文", "作者", "出处", "来源", "告诉", "解释", "说明", "总结",
}
SINGLE_KEEP = set()  # 单字不入索引

FIELD_WEIGHT = {"title": 8.0, "keywords": 5.0, "sub": 3.0, "meta": 2.5, "body": 1.0}


def tokens(text):
    """拉丁词 + 汉字二元组（连写 2—8 字的整体也保留）。"""
    low = text.lower()
    out = [w for w in LATIN.findall(low) if len(w) > 1]
    for run in CJK.findall(low):
        if len(run) == 1:
            continue
        if len(run) <= 8:
            out.append(run)
        out.extend(run[i:i + 2] for i in range(len(run) - 1))
    return [t for t in out if t not in STOP]


class Retriever:
    def __init__(self):
        self.docs = {}          # key -> doc dict
        self.index = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        # index[token][doc_key][field] = tf
        self.df = Counter()     # token -> 文档数
        self._built = False

    # ---------- 建索引 ----------

    def _doc_fields(self, d):
        if d["kind"] == "paper":
            return {
                "title": d["title"] or "",
                "keywords": " ".join(d.get("keywords") or []),
                "sub": d.get("sub") or "",
                "meta": " ".join(filter(None, [d.get("cn"), d.get("authors"),
                                               d.get("venue"), str(d.get("year") or ""),
                                               d.get("type")])),
                "body": "",
            }
        return {
            "title": d["title"] or "",
            "keywords": " ".join(d.get("tags") or []),
            "sub": " ".join(filter(None, [d.get("sub"), d.get("source_topic")])),
            "meta": d.get("author") or "",
            "body": d.get("body") or "",
        }

    def build(self):
        if self._built:
            return self
        for p in db.list_papers():
            p["body"] = ""
            self.docs[p["id"]] = p
        conn = db.connect()
        try:
            rows = conn.execute("SELECT * FROM cases").fetchall()
        finally:
            conn.close()
        for r in rows:
            c = db._case_dict(r, with_body=True)
            c["body"] = "\n".join(c.pop("paragraphs"))
            self.docs[c["id"]] = c

        for key, d in self.docs.items():
            fields = self._doc_fields(d)
            d["_fields"] = fields
            d["_paras"] = [p for p in (fields["body"] or "").split("\n") if p.strip()]
            seen = set()
            for name, text in fields.items():
                if not text:
                    continue
                cnt = Counter(tokens(text))
                for tok, tf in cnt.items():
                    self.index[tok][key][name] = tf
                    seen.add(tok)
            for tok in seen:
                self.df[tok] += 1
        self._built = True
        return self

    # ---------- 打分 ----------

    def _idf(self, tok):
        return math.log(1 + len(self.docs) / (1 + self.df[tok])) + 0.6

    def _score(self, query, exclude=None, weights=None):
        w = weights or FIELD_WEIGHT
        result = defaultdict(float)
        matched = defaultdict(set)
        # 全库都查不到的词不进入分母，否则生僻的查询切分会把覆盖率压得很低
        q_toks = {t for t in tokens(query) if t in self.index}
        for tok in q_toks:
            post = self.index.get(tok)
            if not post:
                continue
            idf = self._idf(tok)
            for key, fields in post.items():
                if key == exclude:
                    continue
                s = 0.0
                for name, tf in fields.items():
                    s += w.get(name, 1.0) * (1 + math.log(tf))
                result[key] += s * idf
                matched[key].add(tok)
        q_weight = sum(self._idf(t) for t in q_toks) or 1.0
        coverage = {k: sum(self._idf(t) for t in v) / q_weight for k, v in matched.items()}
        return result, matched, coverage

    # 命中查询词的加权比例低于此值，视为不相关。宁可返回“没有”，不给凑数的出处。
    MIN_COVERAGE = 0.25
    # 相对最高分太低的条目同样丢掉；多词长句的最高分若仍很低，说明库里没有对应主题。
    MIN_REL = 0.25
    MIN_TOP_LONG = 40.0

    def search(self, query, k=6, kinds=None):
        self.build()
        q_all = {t for t in tokens(query) if t in self.index}
        if not q_all:
            return []
        scores, matched, coverage = self._score(query)
        top = max(scores.values(), default=0.0)
        if len(q_all) >= 3 and top < self.MIN_TOP_LONG:
            return []
        if len(q_all) == 2 and top < 20:
            return []
        floor = top * self.MIN_REL
        picks = sorted(scores.items(), key=lambda kv: -kv[1])
        out = []
        for key, score in picks:
            d = self.docs[key]
            if kinds and d["kind"] not in kinds:
                continue
            if score < floor or coverage.get(key, 0) < self.MIN_COVERAGE:
                continue
            out.append(self._present(d, score, matched[key], limit=3600 if not out else 1200))
            if len(out) >= k:
                break
        return out

    def recommend(self, item_id, k=5):
        self.build()
        target = self.docs.get(item_id)
        if not target:
            return []
        f = target["_fields"]
        # 标题、关键词、子类权重高；正文取出现频繁且在库中不止一篇的二元组，避免噪声词
        profile = " ".join([f["title"], f["keywords"], f["sub"]])
        body_tf = Counter(tokens(f["body"]))
        extra = [t for t, tf in body_tf.most_common(40)
                 if self.df[t] >= 2 and len(t) >= 2][:10]
        profile += " " + " ".join(extra)
        scores, matched, _ = self._score(profile, exclude=item_id)
        picks = sorted(scores.items(), key=lambda kv: -kv[1])[:k]
        return [self._present(self.docs[key], score, matched[key]) for key, score in picks]

    # ---------- 输出 ----------

    def _present(self, d, score, toks, limit=1200):
        f = d["_fields"]
        out = {
            "id": d["id"], "kind": d["kind"], "title": d["title"],
            "sub": d.get("sub") or "", "module": d.get("m") or "",
            "score": round(score, 1),
        }
        if d["kind"] == "paper":
            out["authors"] = d.get("authors") or ""
            out["year"] = d.get("year")
            out["venue"] = d.get("venue") or ""
            out["cn"] = d.get("cn") or ""
            out["url"] = d.get("url") or ""
            out["snippet"] = _clip("；".join(filter(None, [
                d.get("cn"), d.get("authors"), d.get("venue"),
                str(d.get("year") or ""), "、".join(d.get("keywords") or []),
            ])), 220)
            out["excerpt"] = (
                f"题录：{d['title']}（{d.get('cn') or ''}）\n"
                f"作者：{d.get('authors') or '未记录'}\n"
                f"出处：{d.get('venue') or ''} {d.get('year') or ''}　类型：{d.get('type') or ''}\n"
                f"关键词：{'、'.join(d.get('keywords') or []) or '无'}\n"
                f"说明：本条只有题录信息，没有正文。"
            )
        else:
            out["author"] = d.get("author") or ""
            out["page"] = d.get("page")
            out["source_topic"] = d.get("source_topic") or ""
            paras = self._best_paras(d, toks, n=2)
            out["snippet"] = _clip(" … ".join(paras), 320)
            out["excerpt"] = _clip("\n".join(self._best_paras(d, toks, n=8)), limit)
        return out

    def _best_paras(self, d, toks, n=2):
        paras = d.get("_paras") or []
        if not paras:
            return []
        toks = [t for t in toks if len(t) >= 2]
        scored = []
        for p in paras:
            low = p.lower()
            s = sum(low.count(t) * (2 if len(t) >= 4 else 1) for t in toks)
            scored.append((s, len(p), p))
        hot = [p for s, _, p in sorted(scored, key=lambda x: (-x[0], -x[1])) if s > 0][:n]
        if not hot:
            hot = [p for _, _, p in sorted(scored, key=lambda x: -x[1])[:n]]
        return hot


def _clip(s, n):
    s = s.strip()
    return s if len(s) <= n else s[:n].rstrip() + "…"


_engine = Retriever()


def engine():
    return _engine.build()


def search(query, k=6, kinds=None):
    return engine().search(query, k=k, kinds=kinds)


def recommend(item_id, k=5):
    return engine().recommend(item_id, k=k)


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "宽带中国战略"
    for i, r in enumerate(search(q, 5), 1):
        print(f"{i}. [{r['id']}] {r['title']}  ({r['score']})")
        print("   ", r["snippet"][:120])
    print("\n推荐自 CASE-012：")
    for r in recommend("CASE-012", 5):
        print(" -", r["id"], r["title"], r["score"])
