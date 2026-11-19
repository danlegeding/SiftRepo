# 常用命令速查（本地 ↔ CI）

> 目标：CI 里跑的每一步，本地都有对应命令；本地绿了，基本就能确定 CI 会绿。
> 两条硬规则先说：**用 `python -m pytest`**（不要直接敲 `pytest`），**命令都在项目根目录跑**。

## 1. 一条命令验完 CI 的核心两步

```bash
python -m compileall -q app frontend tests scripts   # 语法/导入检查
python -m pytest -q                                   # 34 个用例
```

看到 `34 passed` 就等于本地过了 CI 的 test job（数据库相关的那个用例在没库时会 `skip`，CI 里才真跑）。

## 2. CI 每一步 ↔ 本地命令

| CI 步骤 | CI 里的写法 | 本地怎么做 |
|---|---|---|
| 装依赖 | `pip install -r requirements.txt -r requirements-dev.txt` | 同左（conda 环境 `D:\conda\envs\siftrepo`） |
| 起数据库 | `services.postgres`（镜像 `pgvector/pgvector:pg16`） | `docker start siftrepo-postgres` |
| 建向量扩展 | `psql -c "CREATE EXTENSION IF NOT EXISTS vector"` | 同上，或第一次跑 `POST /projects/upload` 时由 `db_init` 自动建 |
| 语法检查 | `python -m compileall -q app frontend tests scripts` | 同左 |
| 单测 | `python -m pytest -q` | 同左 |
| 看 CI 结果 | GitHub Actions 页面 | `gh run list --limit 5` / `gh run watch`（装了 gh 才可用） |

## 3. 评测（要真实模型 key，不走 CI）

```bash
python scripts/run_retrieval_eval.py          # hit@1/3/5、MRR、耗时
python scripts/run_answer_eval.py             # 引用真实性（严格/宽松）、边界拒答
python scripts/check_files.py                 # 本地体检：结构、命名、明显的脏东西
```

两个评测都会真调 embedding + LLM，**跑一次要几分钟、要花钱**，所以它们只手动跑、不进 CI。

## 4. 起服务

```powershell
powershell -File scripts/run_backend.ps1      # http://127.0.0.1:8000
powershell -File scripts/run_frontend.ps1     # http://127.0.0.1:8501
```

## 5. 常见报错对照表

| 报错 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: No module named 'app'` | 没把项目根加进 `sys.path`；直接调 `pytest` 脚本就会这样 | `pytest.ini` 里 `pythonpath = .`，或改用 `python -m pytest` |
| `pytest.ini:1: unexpected line: '\ufeff[pytest]'` | 文件存成了 UTF-8 **带 BOM** | 用无 BOM 的 UTF-8 重存 |
| `UnicodeDecodeError: 'gbk' codec can't decode byte 0x94` | Windows 默认 GBK 读 UTF-8 文件 | `$env:PYTHONUTF8='1'` |
| `ConfigurationError: Module "app.models" not found` | 目录重构后 `TORTOISE_ORM` 里的模块路径没跟着改 | 改 `app/core/config.py` 的 `"models"` 列表 |
| 本机接口返回 `502 Bad Gateway` | httpx 默认读系统代理，把 127.0.0.1 也走代理 | `httpx.Client(trust_env=False)` |
| `pytest.exe` 无报错但 `exit 1` | Windows 下 console script 走管道的老问题 | 用 `python -m pytest` |

## 6. git 常用

```bash
git status --short --branch      # 看当前分支领先/落后远端几个提交
git log --oneline -5             # 最近 5 个提交
git diff --stat                  # 本次改动的文件与行数
git push origin main             # 网络不通时：git -c http.proxy=http://127.0.0.1:7897 push origin main
git stash push -u -m "备份"      # 临时收起未提交改动
```

## 7. 提交前自检清单

1. `python -m compileall -q app frontend tests scripts` 无输出
2. `python -m pytest -q` → `34 passed`
3. `git diff --stat` 里没有 `.env`、`data/eval/*_report.json`、`_backup_*` 这类不该进仓库的东西
4. 改了接口/模型：同步 README 的 API 表
