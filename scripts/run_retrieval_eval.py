"""检索质量评测：hit@k / MRR + 「指代补全」的 A/B 对照。

用法：
    python scripts/run_retrieval_eval.py
    python scripts/run_retrieval_eval.py --limit 5 --top 10
    python scripts/run_retrieval_eval.py --skip-followups

指标口径：
- 每题检索 top-k，若返回的 file_path 里出现 expected_files 任一（子串匹配）即算命中；
- hit@1 / hit@3 / hit@5 = 前 k 名内命中的比例；MRR = 命中名次取 1/rank 再平均；
- 多轮对照：同一句追问，直接检索 vs 用 build_retrieval_query 拼上一轮问题后再检索。
"""

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
from dotenv import load_dotenv
from tortoise import Tortoise, connections

from app.core.config import TORTOISE_ORM
from app.graph.nodes.query_builder import build_retrieval_query
from app.services.vector_store import retrieve

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "eval" / "retrieval_questions.yaml"
BLOCK_SEPARATOR = "\n\n--- 相关代码片段 ---\n\n"
FILE_PREFIX = "文件："


def load_cases() -> tuple[list[dict], list[dict]]:
    data = yaml.safe_load(DATA_FILE.read_text(encoding="utf-8")) or {}
    return data.get("cases") or [], data.get("followups") or []


async def resolve_project_ids() -> dict[str, int]:
    """项目名 → project_id（按 LIKE 匹配，取第一条）。"""
    conn = connections.get("default")
    _, rows = await conn.execute_query("SELECT id, name FROM project")
    mapping: dict[str, int] = {}
    for row in rows:
        mapping[row["name"]] = row["id"]
    return mapping


def pick_project_id(mapping: dict[str, int], name: str) -> int | None:
    for real_name, pid in mapping.items():
        if name.lower() in real_name.lower():
            return pid
    return None


def parse_file_paths(context: str) -> list[str]:
    """从 retrieve() 拼好的文本里取出每个片段的文件路径。

    只认每个片段的第一行（`文件：xxx`），不能全文正则 —— 代码内容里也可能出现
    「文件：{file_path}」这种模板行（CodeInsight 的 prompt 里就有），会被误当成路径。
    """
    if not context or context.startswith("没有检索到"):
        return []

    paths: list[str] = []
    for block in context.split(BLOCK_SEPARATOR):
        lines = block.strip().splitlines()
        if lines and lines[0].startswith(FILE_PREFIX):
            paths.append(lines[0][len(FILE_PREFIX):].strip())
    return paths


def rank_of_hit(paths: list[str], expected: list[str]) -> int:
    """命中名次（1 开始）；未命中返回 0。"""
    for index, path in enumerate(paths, start=1):
        if any(item in path for item in expected):
            return index
    return 0


async def eval_cases(cases: list[dict], projects: dict[str, int], top: int) -> list[dict]:
    results = []
    for case in cases:
        project_id = pick_project_id(projects, case["project"])
        if project_id is None:
            print(f"[跳过] {case['id']}：库里找不到项目 {case['project']}")
            continue

        start = time.perf_counter()
        context = await retrieve(case["question"], project_id, top)
        elapsed_ms = (time.perf_counter() - start) * 1000

        paths = parse_file_paths(context)
        rank = rank_of_hit(paths, case["expected_files"])
        results.append(
            {
                "id": case["id"],
                "rank": rank,
                "paths": paths,
                "expected": case["expected_files"],
                "elapsed_ms": elapsed_ms,
            }
        )

        mark = "✓" if rank else "✗"
        head = paths[0] if paths else "（无结果）"
        print(f"{mark} {case['id']} rank={rank or '-'}  {elapsed_ms:6.0f}ms  top1={head}")

    return results


def summarize(results: list[dict], top: int) -> None:
    total = len(results)
    if not total:
        print("没有可评测的用例。")
        return

    def hit(k: int) -> float:
        return sum(1 for item in results if 0 < item["rank"] <= k) / total

    mrr = sum(1 / item["rank"] for item in results if item["rank"]) / total
    latency = sorted(item["elapsed_ms"] for item in results)
    p50 = latency[len(latency) // 2]

    print("\n" + "=" * 60)
    print(f"用例数 {total} | top-{top}")
    print(f"hit@1 = {hit(1):.2f}   hit@3 = {hit(3):.2f}   hit@5 = {hit(5):.2f}   MRR = {mrr:.2f}")
    print(f"检索耗时 P50 = {p50:.0f}ms")
    print("=" * 60)

    misses = [item for item in results if not item["rank"]]
    if misses:
        print("\n未命中明细（看 expected 与你实际返回的文件差在哪）：")
        for item in misses:
            print(f"- {item['id']}  期望 {item['expected']}")
            for path in item["paths"][:3]:
                print(f"    got: {path}")


async def eval_followups(followups: list[dict], projects: dict[str, int], top: int) -> None:
    if not followups:
        return

    print("\n" + "-" * 60)
    print("多轮对照：直接检索 vs 指代补全后检索（只看 hit@5）")
    alone_hits = 0
    aided_hits = 0
    for case in followups:
        project_id = pick_project_id(projects, case["project"])
        if project_id is None:
            continue

        alone_paths = parse_file_paths(await retrieve(case["followup_question"], project_id, top))
        merged_query = build_retrieval_query(
            case["followup_question"],
            [{"question": case["previous_question"], "answer": ""}],
        )
        aided_paths = parse_file_paths(await retrieve(merged_query, project_id, top))

        alone_rank = rank_of_hit(alone_paths, case["expected_files"])
        aided_rank = rank_of_hit(aided_paths, case["expected_files"])
        alone_hits += 1 if 0 < alone_rank <= 5 else 0
        aided_hits += 1 if 0 < aided_rank <= 5 else 0

        print(
            f"{case['id']}  裸问 rank={alone_rank or '-'}  "
            f"补全后 rank={aided_rank or '-'}   query={merged_query[:40]}"
        )

    total = len(followups)
    print(
        f"\nhit@5（裸问）= {alone_hits}/{total} = {alone_hits / total:.2f}   "
        f"hit@5（指代补全）= {aided_hits}/{total} = {aided_hits / total:.2f}"
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="检索评测：hit@k / MRR / 指代补全 A/B")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 条用例")
    parser.add_argument("--top", type=int, default=10, help="检索 top-k（默认 10，便于算 hit@1/3/5）")
    parser.add_argument("--skip-followups", action="store_true", help="不跑多轮对照")
    args = parser.parse_args()

    load_dotenv()
    cases, followups = load_cases()
    if args.limit:
        cases = cases[: args.limit]

    await Tortoise.init(config=TORTOISE_ORM)
    try:
        projects = await resolve_project_ids()
        print(f"库里的项目：{projects}\n")
        results = await eval_cases(cases, projects, args.top)
        summarize(results, args.top)
        if not args.skip_followups:
            await eval_followups(followups, projects, args.top)
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
