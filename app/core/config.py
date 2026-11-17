from typing import Dict
import os

import logging

from dotenv import load_dotenv

# 不 override：容器 / CI / 命令行注入的同名环境变量优先
load_dotenv()


# 打印警告 —— 这样「没配 .env」也能先跑起来，换库时改 .env 或设 DB_URL 即可。
DEFAULT_DB_URL = "postgres://user:12345@127.0.0.1:5432/siftrepo"

DB_URL = os.getenv("DB_URL")

if not DB_URL:
    DB_URL = DEFAULT_DB_URL
    # 这只是「用的是默认库」的提示，不是错误：没配 .env / 没设 DB_URL 时就会走这里
    logging.getLogger(__name__).info(
        "未设置 DB_URL，使用默认库 %s（要换库：设 DB_URL 环境变量或写进 .env）",
        DEFAULT_DB_URL,
    )

TORTOISE_ORM: Dict = {
    "connections": {
        "default": DB_URL,
    },
    "apps": {
        "models": {
            "models": ["app.core.models"],
            "default_connection": "default",
        }
    },
    "use_tz": False,
    "timezone": "UTC",
    "db_pool": {
        "max_size": 10,
        "min_size": 1,
        "idle_timeout": 30,
    },
}
