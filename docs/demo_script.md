# Code Assistant Agent 演示脚本

目标：录制 2-3 分钟视频，展示功能、数据隔离与工程边界。不要展示 `.env`、token、数据库密码或完整 JWT。

## 录制前准备

1. 启动 MySQL、Redis、后端和 Streamlit，并确认 `/health` 返回 200。
2. 在后端目录执行 `python -m app.rag.code_indexer`，确保系统代码与 BM25 索引已构建。
3. 准备两个测试账号：`demo_alice`、`demo_bob`，以及一个 20 行以内的 `private_demo.py` 文件。
4. 浏览器打开 `http://localhost:8501`，终端只保留必要的启动日志。

## 时间线

### 0:00 - 0:20 项目目标

展示首页并说明：这是一个以 TinyDB 为系统知识库的代码问答项目，系统检索与用户上传检索走不同 collection；当前重点是可解释的 RAG 与数据边界，而不是生产 SLA。

### 0:20 - 0:55 系统代码检索

1. 注册或登录 `demo_alice`。
2. 打开“检索”页，输入 `TinyDB storage JSON`。
3. 展示返回的 `source` 与代码片段，说明该接口只查询 `system_code`。
4. 可打开 `/docs` 中的 `/api/search` 响应，指出 `latency_ms` 是端到端耗时。

### 0:55 - 1:30 Agent 对话

1. 在“对话”页提问：`TinyDB 如何把数据写入磁盘？`。
2. 展示回答，并说明 Agent 只能使用静态注册的 `search` / `explain` / `testgen` 工具，循环有 `max_steps=6` 上限。
3. 简短说明同一用户、同一随机 session_id 的历史会在 MySQL 中恢复。

### 1:30 - 2:10 上传与隔离

1. 在“上传”页上传 `private_demo.py`，然后输入其中唯一的函数或变量名，点击“检索上传内容”。
2. 展示结果来源为 `upload/private_demo.py`。
3. 登出并登录 `demo_bob`，在“检索上传内容”页输入同一关键词，展示无结果。
4. 说明上传检索使用独立 `user_uploads` collection 与 `owner_id` filter，系统索引重建不会删除上传向量。

### 2:10 - 2:40 工程化与边界

展示 GitHub Actions 或本地 `pytest` 通过结果，说明测试覆盖鉴权、会话隔离、上传隔离与 429 限流。最后主动说明两个限制：20 条检索测试集只做回归；限流在高并发下仍需 Lua 原子化。

## 演示问题

- 系统检索：`TinyDB storage JSON`
- Agent：`TinyDB 如何把数据写入磁盘？`
- 上传文件：

```python
def calculate_private_total(items):
    return sum(item["price"] for item in items)
```

- 上传检索：`calculate_private_total`
