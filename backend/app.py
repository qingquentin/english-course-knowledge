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
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import ai
import db
import retriever

STATIC = Path(__file__).resolve().parent / "static"

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.seed()
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
    return db.list_papers(m=m, sub=sub, q=q)


@app.get("/api/cases")
def cases(m: str | None = None, sub: str | None = None,
          q: str | None = Query(None, max_length=100)):
    return db.list_cases(m=m, sub=sub, q=q)


@app.get("/api/papers/{cat}")
def paper(cat: str):
    d = db.get_paper(cat)
    if not d:
        raise HTTPException(404, "文献不存在")
    return d


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
