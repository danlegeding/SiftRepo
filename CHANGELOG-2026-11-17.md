# 改动说明（2026-11-17，P0 修复）

本次改动的代码里都有 `# region 改动 2026-11-17：...` / `# endregion` 包裹，
被删掉的旧写法以 `# [原代码] 改动前：...` 的注释形式留在同一位置（因为仓库没有 git，
逐字原文无法自动恢复，注释里保留的是原逻辑的写法与关键行）。

在 PyCharm 里可以用 `Ctrl + Alt + .`（折叠 region）/ 或左侧折叠箭头，把每个改动块收起来对比。

## 1. `app/services/embedding.py`（3 处 region）
- **原来**：模块级 `embedding_model = init_embeddings(...)`，`load_dotenv(override=True)`，`retrieve` 的 SQL 多选了一列距离。
- **现在**：`get_embedding_model()` 懒加载（没 key 只在真正用时才报错）；`EMBEDDING_DIM` / `EMBEDDING_MODEL` 走环境变量；`save_embeddings` 写前先 `ensure_pgvector_schema(EMBEDDING_DIM)`；`retrieve` 只取 top-k，参数化 `project_id` + `limit`。

## 2. `app/db_init.py`（1 处 region）
- **原来**：`EMBEDDING_DIM = 1536` 写死 + 布尔缓存。
- **现在**：`ensure_pgvector_schema(dim=DEFAULT_EMBEDDING_DIM)`，按维度缓存（换 embedding 模型不用改代码）。

## 3. `app/services/code_chunk_analysis.py`（2 处 region）
- **原来**：模块级 `gdp_model = init_chat_model(model="gpt-5.4-mini", ...)` + `structured_llm = ...with_structured_output(...)`；两个函数直接 `return await structured_llm.ainvoke(...)`，返回 None 时上层 `model_dump_json()` 会崩。
- **现在**：`get_structured_llm()` 懒加载，模型名读 `ANALYSIS_MODEL`；`_failed_result()` 占位，None / 空列表都有兜底。

## 4. `app/config.py`（1 处 region）
- `load_dotenv(override=True)` → `load_dotenv()`（容器 / CI 注入的变量优先）。
- `DB_URL` 缺失时报错改成「copy .env.example .env 或注入环境变量 DB_URL」。

## 5. `app/services/deepseek_llm.py`（1 处 region）
- `extra_body={"thinking": {"type": "disabled"}}` 从「无条件带」改为「`DEEPSEEK_DISABLE_THINKING=1` 才带」。
- 模型名/地址走 `DEEPSEEK_MODEL` / `DEEPSEEK_BASE_URL`。

## 6. `app/routers/chat.py`（1 处 region）
- `question` 加 `Field(min_length=1, max_length=2000)`。
- 先 `Project.get_or_none` → 项目不存在返回 **404**（原来返回 200 + 「没有检索到相关代码」）。

## 7. `app/routers/project.py`（5 处 region）
- 新增 `GET /projects`、`GET /projects/{project_id}/files`（前端改为走 HTTP，不再直连库）。
- 上传加三道闸：`MAX_ZIP_BYTES`(50MB) / `MAX_FILES`(2000) / `MAX_CHUNKS`(20000)，超了返回 **413**；非法 ZIP 返回 **400**。
- `CodeChunk` 由「循环单条 create」改成 `bulk_create` + 回查 id。
- 后缀比较 `path.suffix` → `path.suffix.lower()`（`.PY` 也能进来）。

## 8. `app/graph/code_graph.py`（2 处 region）
- 新增 `_to_text()`：模型 `content` 是 `list[dict]` 时不再把 list 塞进 `answer: str`（否则 Pydantic 校验 500）。
- `retrieve_node` / `generate_node` 返回注解 `-> OverAllState` → `-> dict`（实际返回的就是 state 增量）。

## 9. `frontend/app.py`（1 处 region）
- 删除 `import psycopg`、`to_psycopg_url()`、`fetch_database_projects()`、`fetch_project_files_with_lines()`；
- 新增 `fetch_projects()` / `fetch_project_files()`，改为请求 `GET /projects`、`GET /projects/{id}/files`。
- 前端从此不需要 `DB_URL`。

## 10. `README.md`
- API 表补 `GET /projects`、`GET /projects/{project_id}/files`；目录树里 `project.py` 的描述同步。

## 11. 启动问题修复（追加）
- `app/config.py`：没有 `DB_URL` 不再 `raise`，改为回退到 docker-compose 默认库
  `postgres://user:12345@127.0.0.1:5432/siftrepo` 并打印警告 —— 没配 `.env` 也能先起来。
- `.env.example`：**原来里面写着两个真实 key**（DeepSeek 与 CloseAI），已换成占位符；
  `DB_URL` 端口由 5433 改为 5432（与 `docker-compose.yml` 一致）；补上
  `DEEPSEEK_MODEL` / `EMBEDDING_MODEL` / `EMBEDDING_DIM` / `ANALYSIS_MODEL` 说明。

## 验证
- `compileall app frontend tests` → 0
- 无任何 API Key、无 `.env` 也能 `import app.main` 并启动 uvicorn
- `pytest -q` → 12 passed
- 起服务后：`GET /projects` 200、`GET /projects/999/files` 404、`POST /chat/`（不存在项目）404、`/docs` 200
- 接口冒烟 6/6、上传链路 9/9（假的 embedding，不花钱）
