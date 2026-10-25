# -*- coding: utf-8 -*-
"""DeepSeek 问答。

流程：retriever 先查出库内相关材料，再把材料连同问题交给模型，要求逐条标注来源。
模型只看见检索结果，答不出就说没有，不给它自由发挥的空间。
"""
import json
import os
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    """读项目根目录 .env，不覆盖已存在的环境变量。"""
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()

BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

SYSTEM = """你是「专业英语课程文献与案例库」的检索助手，服务对象是区域经济学研究生。

回答规则：
1. 只依据给定的库内材料作答，不得补充材料以外的知识、数字、文献或作者。
2. 每条结论后用方括号标注来源编号，如 [1]、[2][3]，编号必须对应材料序号。
3. 材料不足以回答时，直接说明「库中没有找到足以回答这个问题的内容」，并指出库里最接近的条目是什么，不要推测。
4. 标明为「题录」的文献只有标题作者出处，没有正文。不要根据题录推测论文的观点、数据或结论。
5. 用中文回答，直接说事，不复述问题，不写开场白和总结套话。
6. 需要时按「结论—依据—出处」的顺序组织，但不要为了对称硬凑成三段。
7. 涉及条目数量时，只采用材料说明里给出的统计，不要自行清点，也不要推断库里还有多少条未提供的材料。

---

库内材料：

{materials}
"""


def build_materials(sources):
    n_case = sum(1 for s in sources if s["kind"] == "case")
    n_paper = len(sources) - n_case
    header = (f"本次共检索到 {len(sources)} 条材料：案例 {n_case} 条（有正文），"
              f"文献题录 {n_paper} 条（无正文）。这是本次提供的全部材料。\n\n")
    blocks = []
    for i, s in enumerate(sources, 1):
        kind = "案例" if s["kind"] == "case" else "文献题录"
        blocks.append(
            f"[{i}] {s['id']}（{kind}）《{s['title']}》\n"
            f"模块 {s['module']} · 子类 {s['sub']}\n"
            f"{s.get('excerpt') or s.get('snippet') or ''}"
        )
    return header + "\n\n".join(blocks)


async def stream_answer(question: str, sources: list[dict]):
    """异步产出 (event, data)。事件类型：delta / done / error。"""
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        yield "error", {"message": "未配置 DEEPSEEK_API_KEY。请在项目根目录 .env 中填入后再试。"}
        return

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM.format(materials=build_materials(sources))},
            {"role": "user", "content": question},
        ],
        "temperature": 0.2,
        "max_tokens": 1200,
        "stream": True,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    try:
        timeout = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", f"{BASE_URL}/chat/completions",
                                     json=payload, headers=headers) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", "replace")[:400]
                    yield "error", {"message": f"DeepSeek 返回 {resp.status_code}：{body}"}
                    return
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                        delta = obj["choices"][0]["delta"].get("content") or ""
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if delta:
                        yield "delta", {"text": delta}
        yield "done", {}
    except httpx.HTTPError as e:
        yield "error", {"message": f"调用 DeepSeek 失败：{type(e).__name__} {e}"}
