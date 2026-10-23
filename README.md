# 专业英语课程 · 文献与案例库

把 2020—2025 届专业英语文献（100 篇）和《区域与城市经济政策案例库》（44 个案例）
合并成一个按四模块组织的静态知识库，文献与案例分栏浏览。

## 目录

```
知识库项目/
├── index.html                生成的页面，双击即可打开（也可直接部署到 Cloudflare Pages）
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

## 已知限制

- 案例正文来自 docx 提取，Word 浮动文本框、图片内文字、公式未提取。原文共 5.6MB，
  含 36 张图片和 10 处墨迹批注，页面里不呈现。
- 44 个案例中有 23 个能识别出作者，其余原文未署名。
- 数据已脱敏，学号不写入 `cases.json`，也不出现在页面与 git 历史中。
- 页面自包含，含全部案例正文约 516KB；新增资料后体积会继续增长。
- 2026 课程材料（第13-14次文献、前沿文献导学大纲）未纳入。
