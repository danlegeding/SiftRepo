import asyncio
import sys
from pathlib import Path

# region 改动 2026-11-17（整理）：文件从 app/ 挪到 scripts/，跑脚本时要先把项目根加进 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# endregion

from tortoise import Tortoise
from app.core.models import CodeFile
from app.core.config import TORTOISE_ORM  # 按实际路径修改


async def main():
    await Tortoise.init(config=TORTOISE_ORM)

    try:
        files = await CodeFile.all().order_by("-id").limit(100)

        for file in files:
            print(
                f"id={file.id}, "
                f"path={file.path}, "
                f"project_id={file.project_id}"
            )
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())