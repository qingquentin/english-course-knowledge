# 协作指南

课程文献与案例库，线上版本在 <https://english-course-knowledge-2.onrender.com>。这份文件写给新加入的人，按顺序做完就能开工，不用先问谁。

## 本地跑起来

需要 Python 3.10 以上。

```bash
git clone https://github.com/qingquentin/english-course-knowledge.git
cd english-course-knowledge/backend

python -m venv .venv
.venv\Scripts\pip install -r requirements.txt     # Windows
# .venv/bin/pip install -r requirements.txt       # macOS / Linux

copy ..\.env.example ..\.env                      # 填入自己的 DEEPSEEK_API_KEY
.venv\Scripts\python -m uvicorn app:app --reload
```

打开 <http://127.0.0.1:8000>。首次启动会自动从 `data/*.json` 建库并建索引，约一秒。

没有 key 也能跑：浏览、检索、推荐都正常，只有问答会提示未配置。

文献 PDF 已随仓库提供，在 `papers_pdf/{编目号}.pdf`，clone 下来就能读，不需要额外下载。只有重新提取全文或处理原始资料时，才需要 650MB 的课程资料目录；`extract_papers.py` 找不到它会回退到 `papers_pdf/`。

提交前跑一遍离线测试，不花额度：

```bash
.venv\Scripts\python test_offline.py
```

## 目录职责

| 路径 | 负责什么 | 注意 |
|---|---|---|
| `data/*.json` | 唯一真值：模块、文献、案例 | 只由内容负责人修改 |
| `scripts/` | 数据管线与构建 | 改完跑 `build.py` |
| `backend/*.py` | 接口、存储、检索、模型调用 | 改接口要通知前端 |
| `backend/static/` | 线上前端 | **唯一维护的前端** |
| `index.html` | 离线双击入口 | 冻结，由构建生成，勿手改 |
| `template/` | 静态页模板 | 仅在重建静态页时用 |
| `docs/` | 决策记录与接口契约 | 有取舍就记一笔 |

## 分工

按接口切，不按文件切。三块可以并行：

- **内容与数据**：补文献摘要、纳入新材料、标注来源性质。产物在 `data/`。
- **后端与 AI**：检索、提示词、评估集。产物在 `backend/*.py`。
- **前端**：浏览、详情、引用交互。产物在 `backend/static/`。

跨块改动先在小群里说一声，尤其是 `/api/*` 的请求或返回结构。

## 数据规则

- `data/*.json` 是唯一真值，网页和数据库都是派生物。
- 改完数据跑 `python scripts/build.py` 重建离线页；后端重启后自动重建数据库。
- 不要手改 `index.html`，它会被下一次构建覆盖。
- 新增案例按现有字段填，字段说明见 README「数据字段」。学生学号不入库。

## 分支与提交

- `main` 已加保护，禁止直推。
- 分支名用 `feat/`、`fix/`、`data/`、`docs/` 开头，例如 `feat/export-citation`。
- 提交信息第一行说做了什么，正文说为什么。不要写「update」这种。
- PR 用仓库模板填：改了什么、为什么、怎么验证。CI 绿了、有人看过再合。

## 接口

`docs/api.md` 是前后端的契约。改动请求或返回结构，先改文档，再改代码，再通知对方。

## 密钥

- 每人本地 `.env` 填自己的 DeepSeek key，`.env` 不入库。
- 线上 Render 的 key 归部署者，费用也归部署者。协作者本地跑，不碰线上配置。
- key 泄露过一次，如果发现异常用量，去 DeepSeek 控制台换一个。

## 部署

推送 `main` 后 Render 自动重新构建。免费实例 15 分钟无请求会休眠，下次访问约 30 秒。

改了数据不用手动迁移数据库：每次启动都从 `data/*.json` 重建。
