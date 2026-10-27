# 接口契约

前后端以这份文件为准。改请求或返回结构，先改这里，再改代码，再通知对方。

所有路径以 `/api` 开头，返回 JSON，编码 UTF-8。出错时返回 `{"detail": "..."}`，HTTP 状态码表意。

## 浏览

### `GET /api/modules`

四个模块及条目数。

```json
[{"id":"A","name":"科技城市理论与方法","en":"...","color":"#2F5597",
  "descr":"...","subs":["城市与区域科学理论","..."],
  "paperCount":35,"caseCount":15}]
```

### `GET /api/papers?m=&sub=&q=`

参数都可选。`m` 为模块 ID，`sub` 为子类全称，`q` 在题录字段上做子串匹配（SQL LIKE，不是问答用的打分检索）。

返回文献数组，字段见 README「数据字段」。

### `GET /api/cases?m=&sub=&q=`

同上。`q` 覆盖案例正文。列表不含正文段落。

### `GET /api/papers/{cat}`

单篇文献，`cat` 形如 `A-001`。不存在返回 404。

### `GET /api/cases/{id}`

单条案例，含 `paragraphs` 全文段落。不存在返回 404。

### `GET /api/recommend/{id}`

按条目推荐相近条目，`id` 可以是文献编目号或案例编号。

```json
[{"id":"CASE-010","kind":"case","title":"...","sub":"科技创新空间","module":"A","score":305.2}]
```

## 问答

### `POST /api/ask`

请求：

```json
{"question": "宽带中国战略的实施效果如何？", "k": 6}
```

`question` 1—500 字，`k` 默认 6、范围 1—10。按 IP 限流，默认每小时 30 次，超出返回 429。

响应是 SSE（`text/event-stream`），事件顺序固定：

```
event: sources
data: {"sources":[{"id":"CASE-012","kind":"case","title":"...","module":"A","sub":"...","snippet":"..."}]}

event: delta
data: {"text":"库内材料显示，……"}

event: done
data: {}
```

- `sources` 只发一次，含 `excerpt` 之外的公开字段，用于渲染来源卡片。
- `delta` 可多次，拼接即完整答案，正文中的 `[n]` 对应来源序号。
- `done` 若无来源，会带 `{"answer": "库中没有……", "empty": true}`。
- 出错发 `event: error`，`data` 为 `{"message": "..."}`，之后结束。

## 其他

### `GET /api/stats`

```json
{"modules":4,"papers":100,"cases":44,"aiConfigured":true,"model":"deepseek-chat"}
```

前端据此判断是否禁用问答入口。

### `GET /healthz`

部署健康检查，返回 `{"ok":true,...}`。
