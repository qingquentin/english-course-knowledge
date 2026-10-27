# -*- coding: utf-8 -*-
"""FastAPI 入口。

启动：uvicorn app:app --reload（在 backend 目录下）
首启自动从 data/*.json 建库并导入，同时建好内存检索索引。
"""
import json
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import ai
import db
import retriever

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"

# 原始 PDF 不在仓库里，优先读项目内的课程资料目录，其次读上一级同名目录。
# 部署到没有这些文件的机器时，详情页显示「没有可读的 PDF」，不影响题录浏览。
_REPO_PDFS = ROOT / "papers_pdf"          # 随仓库提交的 97 篇 PDF，线上用这个
_LOCAL_PDFS = ROOT / "2020-2025年专业文献及政策案例作业"
_LEGACY_PDFS = ROOT.parent / "2020-2025年专业文献及政策案例作业"
PDF_BASE = Path(os.environ.get("PDF_BASE") or
                (_LOCAL_PDFS if _LOCAL_PDFS.exists() else _LEGACY_PDFS))
_pdf_index: dict[str, int] = {}

# 配了 R2（或任意对象存储）的公开地址后，PDF 请求直接 307 到那里；
# 没配就读本地文件。清单由 scripts/upload_pdfs_r2.py 生成并入库。
PDF_BASE_URL = os.environ.get("PDF_BASE_URL", "").rstrip("/")
PDF_MANIFEST = ROOT / "data" / "pdf_manifest.json"
_remote_pdf: dict[str, dict] = {}

# 公网的 AI 接口按 IP 限流，防止 key 被刷。本地验收不受影响。
ASK_LIMIT = int(os.environ.get("ASK_LIMIT_PER_HOUR", "30"))
ASK_WINDOW = 3600
_hits = defaultdict(deque)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _allow(ip: str) -> bool:
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > ASK_WINDOW:
        q.popleft()
    if len(q) >= ASK_LIMIT:
        return False
    q.append(now)
    if len(_hits) > 5000:  # 顺手清掉过期的 IP 记录
        for k in [k for k, v in _hits.items() if not v]:
            _hits.pop(k, None)
    return True


def _pdf_file(cat: str, rel: str) -> Path | None:
    """优先仓库内的 papers_pdf/{cat}.pdf，其次课程资料目录。"""
    repo = _REPO_PDFS / f"{cat}.pdf"
    if repo.is_file():
        return repo
    if rel:
        f = PDF_BASE / rel
        if f.is_file():
            return f
    return None


def _build_pdf_index():
    """启动时扫本地目录，并合并对象存储清单，得到哪些文献可读及其大小。"""
    _pdf_index.clear()
    _remote_pdf.clear()
    if PDF_MANIFEST.exists():
        try:
            _remote_pdf.update(json.loads(PDF_MANIFEST.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            print(f"清单解析失败：{PDF_MANIFEST}")

    for p in db.list_papers():
        f = _pdf_file(p["id"], p.get("path") or "")
        if f and f.is_file():
            _pdf_index[p["id"]] = f.stat().st_size
    for cat, info in _remote_pdf.items():
        _pdf_index.setdefault(cat, int(info.get("bytes") or 0))
    src = f"R2 {PDF_BASE_URL}" if PDF_BASE_URL else f"本地（{_REPO_PDFS.name} 优先）"
    print(f"可读 PDF {len(_pdf_index)} 篇（{src}）")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.seed()
    _build_pdf_index()
    retriever.engine()
    yield


app = FastAPI(title="专业英语课程知识库", lifespan=lifespan)

# 前后端同源时不需要 CORS；只有把前端单独部署出去时，用 ALLOWED_ORIGINS 指定来源
_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )


@app.get("/healthz")
def health():
    return {"ok": True, "model": ai.MODEL, "aiConfigured": bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())}


# ---------- 浏览 ----------

@app.get("/api/modules")
def modules():
    return db.list_modules()


@app.get("/api/papers")
def papers(m: str | None = None, sub: str | None = None,
           q: str | None = Query(None, max_length=100)):
    items = db.list_papers(m=m, sub=sub, q=q)
    for it in items:
        it["hasPdf"] = it["id"] in _pdf_index
    return items


@app.get("/api/cases")
def cases(m: str | None = None, sub: str | None = None,
          q: str | None = Query(None, max_length=100)):
    return db.list_cases(m=m, sub=sub, q=q)


@app.get("/api/papers/{cat}")
def paper(cat: str):
    d = db.get_paper(cat)
    if not d:
        raise HTTPException(404, "文献不存在")
    d.pop("body", None)
    d["hasPdf"] = cat in _pdf_index
    d["pdfSize"] = _pdf_index.get(cat, 0)
    return d


@app.get("/api/papers/{cat}/pdf")
def paper_pdf(cat: str):
    rel = db.get_paper_path(cat)
    if rel is None:
        raise HTTPException(404, "文献不存在")
    info = _remote_pdf.get(cat)
    if PDF_BASE_URL and info and info.get("key"):
        return RedirectResponse(f"{PDF_BASE_URL}/{info['key']}", status_code=307)
    f = _pdf_file(cat, rel)
    if f is None:
        raise HTTPException(404, "PDF 不可用：原文件缺失")
    return FileResponse(f, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{cat}.pdf"',
        "Cache-Control": "private, max-age=3600",
    })


@app.get("/api/cases/{cid}")
def case(cid: str):
    d = db.get_case(cid)
    if not d:
        raise HTTPException(404, "案例不存在")
    return d


@app.get("/api/recommend/{item_id}")
def recommend(item_id: str, k: int = Query(5, ge=1, le=10)):
    if not (db.get_paper(item_id) or db.get_case(item_id)):
        raise HTTPException(404, "条目不存在")
    return retriever.recommend(item_id, k=k)


@app.get("/api/stats")
def stats():
    mods = db.list_modules()
    return {
        "modules": len(mods),
        "papers": sum(m["paperCount"] for m in mods),
        "cases": sum(m["caseCount"] for m in mods),
        "aiConfigured": bool(os.environ.get("DEEPSEEK_API_KEY", "").strip()),
        "model": ai.MODEL,
    }


# ---------- 问答 ----------

class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    k: int = Field(6, ge=1, le=10)


@app.post("/api/ask")
async def ask(body: Ask, request: Request):
    if not _allow(_client_ip(request)):
        raise HTTPException(429, f"提问过于频繁，每小时最多 {ASK_LIMIT} 次，请稍后再试。")
    question = body.question.strip()
    sources = retriever.search(question, k=body.k)

    def sse(event, data):
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    public = [{k: v for k, v in s.items() if k != "excerpt"} for s in sources]

    async def gen():
        yield sse("sources", {"sources": public})
        if not sources:
            yield sse("done", {"answer": "库中没有找到与这个问题相关的材料。可以换一个说法，或先浏览模块找找相近主题。", "empty": True})
            return
        async for event, data in ai.stream_answer(question, sources):
            yield sse(event, data)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


# ---------- 前端 ----------

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
