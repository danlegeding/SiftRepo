"""回答质量评测：引用真实性 + 边界拒答率。

用法（在项目根目录）：
    python scripts/run_answer_eval.py                # 6 条引用 + 5 条拒答
    python scripts/run_answer_eval.py --limit 10 --top 10
    python scripts/run_answer_eval.py --skip-refusal

指标口径：
- 引用真实性 = 回答里提到的文件路径，能在「检索到的上下文」里找到的比例。
  回答里编一个不存在的文件 → 分母加一、分子不加，指标下降。
- 边界拒答率 = 问「库里根本没有的东西」时，回答明确说没找到/不包含的比例。
  答得像模像样（幻觉）→ 不算拒答，指标下降。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.graph.build import graph  # noqa: E402
from app.services.vector_store import retrieve  # noqa: E402

EVAL_DIR = ROOT / "data" / "eval"
QUESTIONS_FILE = EVAL_DIR / "retrieval_questions.yaml"
REPORT_FILE = EVAL_DIR / "answer_report.json"

# 回答里可能出现的「文件路径」，可带行号：app/services/vector_store.py:44
CITATION_PATTERN = re.compile(r"([\w][\w./\-]*\.(?:py|md|txt|ya?ml|toml|json|ini|cfg))(?![\w.])")

# 「库里没有」的问题：正确答案是明确说找不到，而不是编一个位置
OUT_OF_SCOPE_QUESTIONS = [
    "Kubernetes 的部署清单（deployment.yaml）在哪个目录？",
    "前端用的是哪个 Vue 组件库？",
    "数据库迁移脚本（alembic 的 versions）放在哪里？",
    "用户登录用的 JWT 鉴权中间件在哪个文件？",
    "GitLab CI 的 .gitlab-ci.yml 里定义了哪几个 stage？",
]

STRONG_REFUSAL_HINTS = (
    "未找到",
    "没有找到",
    "找不到",
    "无法找到",
    "无法定位",
    "不存在",
    "不包含",
    "未包含",
    "没有相关",
    "没有提到",
    "未提供",
    "缺少",
    "上下文不足以",
    "无法回答",
    "无法确定",
    "本次检索",
    "检索到的代码里没有",
    "检索到的所有代码片段中",
    "没有任何内容涉及",
)

# 弱拒答信号：需要同时出现「上下文」字样才算（例如「前端用的是 Streamlit，不是 Vue」）
WEAK_REFUSAL_HINTS = ("不是", "并非", "未使用", "没有使用", "不涉及")


def normalize_path(raw: str) -> str:
    """把引用规范成仓库内相对路径，便于和上下文里的路径比对。"""
    path = raw.strip().strip("`'\"()（）:：,，、")
    return path.removeprefix("./").replace("\\", "/")


def extract_citations(answer: str) -> list[str]:
    """从回答里抽出文件路径引用（去重保序）。"""
    seen: list[str] = []
    for match in CITATION_PATTERN.finditer(answer or ""):
        path = normalize_path(match.group(1))
        if path and path not in seen:
            seen.append(path)
    return seen


def is_refusal(answer: str) -> bool:
    text = answer or ""
    if any(hint in text for hint in STRONG_REFUSAL_HINTS):
        return True
    return "上下文" in text and any(hint in text for hint in WEAK_REFUSAL_HINTS)


def context_paths(context: str) -> set[str]:
    """上下文里出现过的文件路径集合。"""
    paths = {normalize_path(match.group(1)) for match in CITATION_PATTERN.finditer(context or "")}
    return {path for path in paths if path}


async def resolve_projects() -> dict[str, int]:
    from app.core.models import Project

    projects = await Project.all().values("id", "name")
    return {row["name"].removesuffix(".zip"): row["id"] for row in projects}


def pick_case_project(case: dict, projects: dict[str, int]) -> int | None:
    wanted = str(case.get("project") or "")
    if wanted in projects:
        return projects[wanted]
    for name, project_id in projects.items():
        if wanted and wanted.lower() in name.lower():
            return project_id
    return next(iter(projects.values()), None)


def basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def match_citation(citation: str, available: set[str]) -> str:
    """把一条引用分成四类。

    - strict：完整路径能在检索上下文里找到（最严格，等同于“可核对”）
    - shorthand：只写了文件名，但该文件确实在检索结果里（写法不完整，不算错）
    - exists_not_retrieved：文件在项目里存在，但这次没被检索到（引用来源不明，最可疑）
    - hallucinated：项目里根本没有这个文件（编造）
    """
    if citation in available:
        return "strict"
    if basename(citation) in {basename(path) for path in available}:
        return "shorthand"
    return "unknown"


async def project_paths_of(project_id: int, cache: dict[int, set[str]]) -> set[str]:
    """项目的全部文件路径（用于区分「没检索到」和「根本不存在」）。"""
    if project_id in cache:
        return cache[project_id]
    from app.core.models import CodeFile

    rows = await CodeFile.filter(project_id=project_id).values_list("path", flat=True)
    cache[project_id] = {normalize_path(path) for path in rows}
    return cache[project_id]


async def eval_citations(cases: list[dict], projects: dict[str, int], top: int) -> dict:
    rows = []
    totals = {"strict": 0, "shorthand": 0, "exists_not_retrieved": 0, "hallucinated": 0}
    path_cache: dict[int, set[str]] = {}

    for case in cases:
        project_id = pick_case_project(case, projects)
        if project_id is None:
            rows.append({"id": case["id"], "error": "项目不存在"})
            continue
        project_name = next(
            (name for name, pid in projects.items() if pid == project_id), str(project_id)
        )
        state = await graph.ainvoke(
            {"question": case["question"], "project_id": project_id, "history": []}
        )
        answer = state.get("answer", "")
        available = context_paths(state.get("mid_context", ""))
        existing = await project_paths_of(project_id, path_cache)

        verdicts: dict[str, list[str]] = {
            "strict": [],
            "shorthand": [],
            "exists_not_retrieved": [],
            "hallucinated": [],
        }
        for citation in extract_citations(answer):
            verdict = match_citation(citation, available)
            if verdict == "unknown":
                known = basename(citation) in {basename(path) for path in existing}
                verdict = "exists_not_retrieved" if known else "hallucinated"
            verdicts[verdict].append(citation)
            totals[verdict] += 1

        rows.append(
            {
                "id": case["id"],
                "project": project_name,
                "question": case["question"],
                "verdicts": verdicts,
                "answer_chars": len(answer),
            }
        )

    total = sum(totals.values())
    return {
        "total": total,
        "counts": totals,
        # 严格口径：完整路径命中检索结果
        "strict_rate": (totals["strict"] / total) if total else None,
        # 宽松口径：完整路径 + 只写文件名（都算“文件确实来自检索”）
        "lenient_rate": ((totals["strict"] + totals["shorthand"]) / total) if total else None,
        # 幻觉率：引用了项目里根本不存在的文件
        "hallucination_rate": (totals["hallucinated"] / total) if total else None,
        "rows": rows,
    }


async def eval_refusal(projects: dict[str, int]) -> dict:
    project_id = next(iter(projects.values()), None)
    if project_id is None:
        return {"error": "没有项目可评测", "rows": []}
    rows = []
    refused = 0
    for question in OUT_OF_SCOPE_QUESTIONS:
        state = await graph.ainvoke(
            {"question": question, "project_id": project_id, "history": []}
        )
        answer = state.get("answer", "")
        ok = is_refusal(answer)
        refused += 1 if ok else 0
        rows.append(
            {
                "question": question,
                "refused": ok,
                "answer_head": (answer or "")[:120],
            }
        )
    return {
        "total": len(OUT_OF_SCOPE_QUESTIONS),
        "refused": refused,
        "rate": refused / len(OUT_OF_SCOPE_QUESTIONS),
        "rows": rows,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description="回答质量评测：引用真实性 + 边界拒答率")
    parser.add_argument("--limit", type=int, default=6, help="引用类用例数量")
    parser.add_argument("--top", type=int, default=10, help="检索块数（传给 retrieve 的 limit 无关，仅记录）")
    parser.add_argument("--skip-refusal", action="store_true", help="跳过边界拒答评测")
    parser.add_argument("--skip-citation", action="store_true", help="跳过引用真实性评测")
    parser.add_argument("--out", default=str(REPORT_FILE), help="结果写到哪里")
    args = parser.parse_args()

    payload = yaml.safe_load(QUESTIONS_FILE.read_text(encoding="utf-8")) or {}
    cases = payload.get("cases") or []
    if args.limit:
        cases = cases[: args.limit]

    from tortoise import Tortoise

    from app.core.config import TORTOISE_ORM

    await Tortoise.init(config=TORTOISE_ORM)
    try:
        projects = await resolve_projects()
        if not projects:
            print("库里没有项目：先上传一个 ZIP 再评测")
            return 1
        print(f"已解析项目：{projects}")
        result: dict = {}

        if not args.skip_citation:
            print(f"\n== 引用真实性（{len(cases)} 条）==")
            citation = await eval_citations(cases, projects, args.top)
            result["citation"] = citation
            for row in citation["rows"]:
                if "error" in row:
                    print(f"  {row['id']}: {row['error']}")
                    continue
                verdicts = row["verdicts"]
                total = sum(len(items) for items in verdicts.values())
                bad = len(verdicts["hallucinated"]) + len(verdicts["exists_not_retrieved"])
                mark = "OK " if not bad else "WARN"
                print(f"  {mark} {row['id']}: 引用 {total} 个")
                for verdict, items in verdicts.items():
                    if items and verdict in ("exists_not_retrieved", "hallucinated"):
                        print(f"       [{verdict}] {items}")

            counts = citation["counts"]
            strict = citation["strict_rate"]
            lenient = citation["lenient_rate"]
            halluc = citation["hallucination_rate"]
            print(
                f"引用 {citation['total']} 条：完整路径命中 {counts['strict']}、"
                f"只写文件名 {counts['shorthand']}、库里存在但未检索到 "
                f"{counts['exists_not_retrieved']}、编造 {counts['hallucinated']}"
            )
            print(
                "引用真实性（严格，完整路径） = "
                f"{'n/a' if strict is None else f'{strict:.2f}'}"
                "；宽松（含只写文件名） = "
                f"{'n/a' if lenient is None else f'{lenient:.2f}'}"
                "；编造率 = "
                f"{'n/a' if halluc is None else f'{halluc:.2f}'}"
            )

        if not args.skip_refusal:
            print("\n== 边界拒答率（5 条库外问题）==")
            refusal = await eval_refusal(projects)
            result["refusal"] = refusal
            for row in refusal["rows"]:
                print(f"  {'REFUSED' if row['refused'] else 'ANSWERED'} {row['question']}")
            print(f"边界拒答率 = {refusal['refused']}/{refusal['total']} = {refusal['rate']:.2f}")

        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n结果已写入 {out_path}")
        return 0
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
