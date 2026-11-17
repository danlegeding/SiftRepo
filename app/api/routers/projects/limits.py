"""上传与解析相关的硬限制与白名单。

把常量单独放一个文件，是为了让 upload / query 两个端点文件只管流程、
不用在各自的头部堆一屏魔法数字。
"""

# 跳过不需要分析的目录
EXCLUDED_DIRS = {
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    "node_modules",
    "site-packages",
    ".idea",
}

# 上传硬上限：防止大仓库把内存打满（ZIP 会整个读进内存，所以先限大小）
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_FILES = 2000
MAX_CHUNKS = 20000

# 单个文件一次最多返回多少条代码块（前端展示用）
MAX_CHUNK_ROWS = 2000

# 向量写入时每批多少条（避免一次请求过大）
EMBED_BATCH_SIZE = 32
