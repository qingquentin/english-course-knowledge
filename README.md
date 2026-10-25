# 专业英语课程 · 文献与案例库

把 2020—2025 届专业英语文献（100 篇）和《区域与城市经济政策案例库》（44 个案例）
合并成一个按四模块组织的静态知识库，文献与案例分栏浏览。

## 目录

```
知识库项目/
├── index.html                生成的页面，双击即可打开（也可直接部署到 Cloudflare Pages）
├── backend/                  全栈服务：检索、AI 问答、前端
│   ├── app.py                FastAPI 路由与静态托管
│   ├── db.py                 SQLite 建库与查询
│   ├── retriever.py          库内检索与相关推荐
│   ├── ai.py                 DeepSeek 问答
│   ├── requirements.txt
│   └── static/               前端页面
├── .env.example              API Key 配置模板
├── data/
│   ├── modules.json          四模块二十一子类
│   ├── papers.json           100 篇文献元数据
│   ├── cases.json            44 个案例（已映射模块/子类，含正文段落）
│   └── cases_raw.json        案例拆分中间产物（按原文专题，未映射）
├── scripts/
│   ├── extract_site_data.py  从线上页面提取 DATA，拆成 modules/papers 与模板
│   ├── split_cases.py        案例库 docx → 44 条原始案例
│   ├── map_cases.py          案例映射模块子类、清模板字样、抽作者
│   └── build.py              合并数据并渲染 index.html
└── template/
    ├── _source.html          线上页面原件（备份，勿改）
    └── index.template.html   可维护模板，渲染时注入数据
```

全部脚本只用 Python 标准库，无需安装依赖。

## 重建页面

```bash
python scripts/build.py
```

改了 `data/*.json` 或 `template/index.template.html` 之后跑这一句即可。

## 从原始资料重跑

```bash
python scripts/split_cases.py   # 读 ../区域与城市经济政策案例库.docx
python scripts/map_cases.py
python scripts/build.py
```

`extract_site_data.py` 只在需要重新拉取线上页面时用，它会覆盖 `template/index.template.html`，
平时不要跑。

## 数据字段

文献（papers.json）

| 字段 | 说明 |
|---|---|
| n | 原始编号 |
| m | 模块 A/B/C/D |
| sub | 子类 |
| title / cn | 英文标题 / 中文标题 |
| authors / year / venue / type | 作者、年份、期刊、类型 |
| keywords | 关键词数组 |
| archive | 所属届别年份 |
| path | 原始文件相对路径 |
| cat | 编目号 A-001 |
| url / linkKind | 原文链接；doi 或 search |

案例（cases.json）

| 字段 | 说明 |
|---|---|
| id | CASE-001 起 |
| m / sub | 模块 / 子类（按四模块重新归类） |
| source_topic | 原案例库的十大专题，保留以便回溯 |
| title | 标题 |
| author / student_id | 作者与学号（原文有则填） |
| page | 原文页码 |
| tags | 跨主题副标签 |
| paragraphs | 正文段落数组 |
| char_count | 正文字数 |

## 归类原则

四模块是主分类，每个案例挂一个子类；`source_topic` 保留原专题，两个坐标并存。
案例库的十大专题与新框架不一一对应，映射结果见 `scripts/map_cases.py` 的 `MAPPING` 表，
改一行即改一个案例的归属。

各模块案例数：A 15、B 7、C 18、D 4。
C 与 A 偏多，是因为原案例库的财政与城市政策主题本就集中于此；B 只有 7 个，
原案例库对数字经济、遥测类主题覆盖很少，这一块目前全靠文献。

## 全栈应用：检索与带出处问答

`index.html` 只管离线浏览。需要按自然语言查资料、并让每条结论标出处时，用后端。

### 启动

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt      # Windows；macOS/Linux 用 .venv/bin/pip
copy ..\.env.example ..\.env                       # 填入 DEEPSEEK_API_KEY
.venv\Scripts\python -m uvicorn app:app --reload
```

打开 <http://127.0.0.1:8000>。首次启动自动从 `data/*.json` 建 `backend/knowledge.db` 并载入检索索引，约一秒。

服务起来后可以跑验收脚本，用四个真实问题检查检索、引用和拒答：

```bash
.venv\Scripts\python smoke_test.py
```

改了 `data/*.json` 后跑 `python db.py --rebuild`，再重启服务。

### 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/modules` | 四模块与各模块条目数 |
| GET | `/api/papers?m=&sub=&q=` | 文献筛选，`q` 匹配题录 |
| GET | `/api/cases?m=&sub=&q=` | 案例筛选，`q` 覆盖正文 |
| GET | `/api/papers/{cat}` | 单篇文献 |
| GET | `/api/cases/{id}` | 单条案例，含正文段落 |
| GET | `/api/recommend/{id}` | 相近条目 |
| POST | `/api/ask` | `{question}`，SSE 流式返回答案与来源 |

`/api/ask` 先推一条 `sources` 事件（结构化来源），再逐段推 `delta`，最后 `done`。前端据此渲染可点的来源编号。

### 检索怎么做

不引 SQLite FTS，也不引向量库。语料只有 44 篇案例正文加 100 条题录，启动时内存里建一张倒排索引就够，查询在毫秒级。

- 切词用拉丁词加汉字二元组，不依赖分词库。
- 打分按字段加权：标题 8、关键词 5、子类 3、题录信息 2.5、正文 1，再乘 IDF。
- 两道门槛挡掉凑数的来源：命中词加权覆盖率低于 0.25 的丢掉；得分低于最高分 25% 的丢掉。多词长句若最高分仍低于 40，直接判为库里没有。
- 送进模型的正文，第一条最多 3600 字，其余 1200 字。案例正文普遍三五千字，第一条给足，模型才能读到评估结论，不只看见开头。

推荐复用同一套打分：把目标条目的标题、关键词、子类，加上正文里跨文档出现的高频词拼成查询，再算相似度。

### 问答怎么防编造

模型只看见检索结果，看不见整个库。系统提示词要求逐条标注 `[n]` 来源编号、资料不足就直说、不得推测题录类文献的内容。来源列表由后端单独返回，模型写不出链接，也改不了出处。

### 部署

Cloudflare Pages 只能托管 `index.html` 这类静态页，跑不了 FastAPI。后端要一台常驻 Python 的机器。

**Render（仓库里已带 `render.yaml`）**

1. 代码推到 GitHub，仓库已有 `qingquentin/english-course-knowledge`。
2. Render 控制台 → New → Blueprint，选这个仓库；或 New → Web Service，Root Directory 填 `backend`，Build Command 填 `pip install -r requirements.txt`，Start Command 填 `uvicorn app:app --host 0.0.0.0 --port $PORT`。
3. 环境变量加 `DEEPSEEK_API_KEY`，值填自己的 key。仓库里不放 key。
4. 健康检查路径 `/healthz`。

免费实例 15 分钟无请求会休眠，下次访问冷启动约 30 秒，主要耗在拉起进程。数据库不需要持久盘，每次启动从 `data/*.json` 重建，不到一秒。

**Docker（Hugging Face Spaces、Fly.io 等）**

```bash
docker build -t english-kb .
docker run -p 8000:8000 -e DEEPSEEK_API_KEY=sk-... english-kb
```

**公网防护**

`/api/ask` 按 IP 限流，默认每小时 30 次，用 `ASK_LIMIT_PER_HOUR` 调。前后端同源时不需要 CORS；把前端单独部署出去时，设置 `ALLOWED_ORIGINS=https://前端域名`。

### 能力边界

- **案例**有全文（约 15 万字），问答能读正文答内容。
- **文献**只有题录，问答只能复述标题、作者、出处、DOI，答不了论文观点。页面上打开单篇文献时也会提示这一点。
- 词面检索挡不住语义离题。问库外话题时，偶有词面重合的材料被送入模型，由提示词规则拒答。
- 限流计数存在进程内存里，重启清零，多实例也不共享。单实例的小站够用，要更严得上 Redis。

## 已知限制

- 案例正文来自 docx 提取，Word 浮动文本框、图片内文字、公式未提取。原文共 5.6MB，
  含 36 张图片和 10 处墨迹批注，页面里不呈现。
- 44 个案例中有 23 个能识别出作者，其余原文未署名。
- 数据已脱敏，学号不写入 `cases.json`，也不出现在页面与 git 历史中。
- 页面自包含，含全部案例正文约 516KB；新增资料后体积会继续增长。
- 2026 课程材料（第13-14次文献、前沿文献导学大纲）未纳入。
