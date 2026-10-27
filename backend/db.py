# -*- coding: utf-8 -*-
"""SQLite 存储层。

data/*.json 是唯一真值来源，本模块只负责把它导入 SQLite 供服务端查询。
库里没有数据时自动导入；改过 JSON 后可跑 `python db.py --rebuild` 重建。
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FULLTEXT = DATA / "papers_fulltext.json"
DB_PATH = Path(__file__).resolve().parent / "knowledge.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS modules (
    id      TEXT PRIMARY KEY,
    name    TEXT NOT NULL,
    en      TEXT,
    color   TEXT,
    descr   TEXT,
    subs    TEXT,              -- JSON 数组，子类
    seq     INTEGER
);
CREATE TABLE IF NOT EXISTS papers (
    cat         TEXT PRIMARY KEY,
    n           INTEGER,
    module_id   TEXT NOT NULL,
    sub         TEXT,
    title       TEXT,
    cn          TEXT,
    authors     TEXT,
    year        INTEGER,
    venue       TEXT,
    type        TEXT,
    keywords    TEXT,          -- JSON 数组
    archive     TEXT,
    path        TEXT,
    url         TEXT,
    link_kind   TEXT,
    note        TEXT,
    body        TEXT,          -- 文献全文，由 scripts/extract_papers.py 提取
    has_body    INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS cases (
    id          TEXT PRIMARY KEY,
    module_id   TEXT NOT NULL,
    sub         TEXT,
    source_topic TEXT,
    title       TEXT,
    author      TEXT,
    page        INTEGER,
    tags        TEXT,          -- JSON 数组
    body        TEXT,
    char_count  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_papers_mod ON papers(module_id);
CREATE INDEX IF NOT EXISTS idx_cases_mod ON cases(module_id);
"""


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_paper(p, fulltext):
    body = fulltext.get(p["cat"], {}).get("body") or ""
    return (
        p["cat"], p.get("n"), p["m"], p.get("sub"), p.get("title"), p.get("cn"),
        p.get("authors"), p.get("year"), p.get("venue"), p.get("type"),
        json.dumps(p.get("keywords") or [], ensure_ascii=False),
        p.get("archive"), p.get("path"), p.get("url"), p.get("linkKind"),
        p.get("note") or "", body, 1 if body else 0,
    )


def _row_case(c):
    return (
        c["id"], c["m"], c.get("sub"), c.get("source_topic"), c.get("title"),
        c.get("author") or "", c.get("page"), json.dumps(c.get("tags") or [], ensure_ascii=False),
        "\n".join(c.get("paragraphs") or []), c.get("char_count") or 0,
    )


def _schema_ok():
    """旧版本库缺列时自动重建，免得改一次表结构就要手动删库。"""
    if not DB_PATH.exists():
        return False
    conn = connect()
    try:
        mcols = {r[1] for r in conn.execute("PRAGMA table_info(modules)")}
        pcols = {r[1] for r in conn.execute("PRAGMA table_info(papers)")}
        return "subs" in mcols and "body" in pcols
    except sqlite3.DatabaseError:
        return False
    finally:
        conn.close()


def seed(force: bool = False):
    """建表并从 JSON 导入。force=True 或库结构过旧时清空重建。"""
    if DB_PATH.exists() and not _schema_ok():
        DB_PATH.unlink()
    if force and DB_PATH.exists():
        DB_PATH.unlink()

    modules = json.loads((DATA / "modules.json").read_text(encoding="utf-8"))
    papers = json.loads((DATA / "papers.json").read_text(encoding="utf-8"))
    cases = json.loads((DATA / "cases.json").read_text(encoding="utf-8"))
    fulltext = {}
    if FULLTEXT.exists():
        fulltext = json.loads(FULLTEXT.read_text(encoding="utf-8"))

    conn = connect()
    try:
        conn.executescript(SCHEMA)
        n_mod = conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0]
        if n_mod and not force:
            return

        conn.executemany(
            "INSERT OR REPLACE INTO modules VALUES (?,?,?,?,?,?,?)",
            [(m["id"], m["name"], m.get("en"), m.get("color"), m.get("desc"),
              json.dumps(m.get("subs") or [], ensure_ascii=False), i)
             for i, m in enumerate(modules)],
        )
        conn.executemany(
            "INSERT OR REPLACE INTO papers VALUES (" + ",".join("?" * 18) + ")",
            [_row_paper(p, fulltext) for p in papers],
        )
        conn.executemany(
            "INSERT OR REPLACE INTO cases VALUES (" + ",".join("?" * 10) + ")",
            [_row_case(c) for c in cases],
        )
        conn.commit()
        n_body = sum(1 for p in papers if fulltext.get(p["cat"], {}).get("body"))
        print(f"已导入 {len(modules)} 模块 / {len(papers)} 文献（全文 {n_body} 篇）/ "
              f"{len(cases)} 案例 → {DB_PATH}")
    finally:
        conn.close()


# ---------- 查询 ----------

PAPER_COLS = ("cat,n,module_id,sub,title,cn,authors,year,venue,type,"
              "keywords,archive,path,url,link_kind,note,has_body")


def _paper_dict(r, with_body=False):
    d = {
        "id": r["cat"], "kind": "paper", "n": r["n"], "m": r["module_id"],
        "sub": r["sub"], "title": r["title"], "cn": r["cn"], "authors": r["authors"],
        "year": r["year"], "venue": r["venue"], "type": r["type"],
        "keywords": json.loads(r["keywords"] or "[]"), "archive": r["archive"],
        "path": r["path"], "url": r["url"], "linkKind": r["link_kind"],
        "note": r["note"], "hasBody": bool(r["has_body"]),
    }
    if with_body:
        d["body"] = r["body"] or ""
    return d


def _case_dict(r, with_body=False):
    d = {
        "id": r["id"], "kind": "case", "m": r["module_id"], "sub": r["sub"],
        "source_topic": r["source_topic"], "title": r["title"], "author": r["author"],
        "page": r["page"], "tags": json.loads(r["tags"] or "[]"),
        "char_count": r["char_count"],
    }
    if with_body:
        d["paragraphs"] = [p for p in (r["body"] or "").split("\n") if p]
    return d


def list_modules():
    conn = connect()
    try:
        mods = [dict(r) for r in conn.execute("SELECT * FROM modules ORDER BY seq")]
        pcount = {r[0]: r[1] for r in conn.execute("SELECT module_id, COUNT(*) FROM papers GROUP BY 1")}
        ccount = {r[0]: r[1] for r in conn.execute("SELECT module_id, COUNT(*) FROM cases GROUP BY 1")}
        for m in mods:
            m["subs"] = json.loads(m.pop("subs") or "[]")
            m["paperCount"] = pcount.get(m["id"], 0)
            m["caseCount"] = ccount.get(m["id"], 0)
        return mods
    finally:
        conn.close()


def list_papers(m=None, sub=None, q=None, with_body=False):
    cols = "*" if with_body else PAPER_COLS
    sql = f"SELECT {cols} FROM papers WHERE 1=1"
    args = []
    if m:
        sql += " AND module_id=?"
        args.append(m)
    if sub:
        sql += " AND sub=?"
        args.append(sub)
    if q:
        sql += (" AND (title LIKE ? OR cn LIKE ? OR authors LIKE ? OR venue LIKE ?"
                " OR keywords LIKE ? OR sub LIKE ? OR cat LIKE ?)")
        args += [f"%{q}%"] * 7
    sql += " ORDER BY cat"
    conn = connect()
    try:
        return [_paper_dict(r, with_body) for r in conn.execute(sql, args)]
    finally:
        conn.close()


def list_cases(m=None, sub=None, q=None):
    sql = "SELECT * FROM cases WHERE 1=1"
    args = []
    if m:
        sql += " AND module_id=?"
        args.append(m)
    if sub:
        sql += " AND sub=?"
        args.append(sub)
    if q:
        sql += (" AND (title LIKE ? OR sub LIKE ? OR source_topic LIKE ? OR author LIKE ?"
                " OR body LIKE ? OR id LIKE ?)")
        args += [f"%{q}%"] * 6
    sql += " ORDER BY id"
    conn = connect()
    try:
        return [_case_dict(r) for r in conn.execute(sql, args)]
    finally:
        conn.close()


def get_paper(cat):
    conn = connect()
    try:
        r = conn.execute("SELECT * FROM papers WHERE cat=?", (cat,)).fetchone()
        return _paper_dict(r, with_body=True) if r else None
    finally:
        conn.close()


def get_paper_path(cat):
    """只取原文路径，供 PDF 路由用，避免把整篇正文读出来。"""
    conn = connect()
    try:
        r = conn.execute("SELECT path FROM papers WHERE cat=?", (cat,)).fetchone()
        return r["path"] if r else None
    finally:
        conn.close()


def get_case(cid):
    conn = connect()
    try:
        r = conn.execute("SELECT * FROM cases WHERE id=?", (cid,)).fetchone()
        return _case_dict(r, with_body=True) if r else None
    finally:
        conn.close()


def module_map():
    return {m["id"]: {k: m[k] for k in ("id", "name", "en", "color")} for m in list_modules()}


if __name__ == "__main__":
    seed(force="--rebuild" in sys.argv)
    conn = connect()
    print("模块", conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0])
    print("文献", conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0])
    print("案例", conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0])
    conn.close()
