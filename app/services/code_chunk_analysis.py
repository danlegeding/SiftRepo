"""按代码块做质量分析，并把多块结果汇总成一份报告。

两个模型客户端都延迟到调用期构造：import 阶段不要求 API Key。
"""

from langchain.chat_models import init_chat_model
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv
import os

from app.model.analysis import AnalysisResult

load_dotenv()

# 单块分析用的模型（走 OpenAI 兼容代理）；可用 ANALYSIS_MODEL 覆盖
DEFAULT_ANALYSIS_MODEL = "gpt-5.4-mini"

# 单次分析的最大字符数：超过就切片后并行分析再汇总
MAX_ANALYSIS_CHARS = 3000

_structured_llm = None


def get_structured_llm():
    """返回「输出 AnalysisResult」的结构化模型（首次调用时创建）。"""
    global _structured_llm
    if _structured_llm is not None:
        return _structured_llm

    api_key = os.getenv("CLOSEAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "未找到 CLOSEAI_API_KEY，请在项目根目录的 .env 中配置后再做代码分析"
        )

    model_name = os.getenv("ANALYSIS_MODEL", DEFAULT_ANALYSIS_MODEL)
    base_llm = init_chat_model(
        model=model_name,
        model_provider="openai",
        api_key=api_key,
        base_url=os.getenv("CLOSEAI_BASE_URL"),
    )
    _structured_llm = base_llm.with_structured_output(AnalysisResult)
    return _structured_llm


def split_code_for_analyses(content: str) -> list[str]:
    """把长文件切成若干块（优先在类/函数边界切）。"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=MAX_ANALYSIS_CHARS,
        chunk_overlap=300,
        separators=[
            "\nclass ",
            "\nasync def ",
            "\ndef ",
            "\n\n",
            "\n",
            " ",
            "",
        ],
    )
    return splitter.split_text(content)


def _failed_result(reason: str) -> AnalysisResult:
    """模型没返回结构化结果时的占位，保证汇总环节不会因为 None 崩掉。"""
    return AnalysisResult(
        summary=f"该代码块分析失败：{reason}",
        issues=[],
        strengths=[],
        optimization=["可重试一次，或检查模型服务是否可用。"],
    )


async def analyses_code_chunk(content: str) -> AnalysisResult:
    """分析单个代码块，返回结构化结果（失败时返回占位结果而不是 None）。"""
    prompt = f"""
你是一名经验丰富的代码审查工程师。

请分析下面的代码。注意：这段代码是从一个更大文件里切出来的片段，行号以片段第一行为第 1 行。

分析要求：
1. 总结代码的主要功能：一句话说清它做什么、被谁调用。
2. 找出潜在的问题，包括逻辑错误、异常处理、代码质量、安全性等。每条问题都必须写清位置：
   - 用「函数名/类名」定位，例如 `save_embeddings`、`retrieve`；
   - **不要写行号**（片段行号与真实文件不一致，会误导），位置信息一律靠下面第 3 条的逐字引用承担；
   - 实在无法定位时写「位置不明确」。
3. 每条问题必须逐字引用出问题的原代码（不超过一行，标成 `原代码：...`），这段引用要能在给定代码里原样搜索到。
4. 不要写「异常处理不足」「缺少校验」这类没有位置的泛泛结论，必须指出是哪一个调用、哪一个分支。
5. 给出具体的优化建议：改哪里、改成什么，要能直接落地。
6. 指出代码中做得比较好的地方，同样要带位置。
7. 不要凭空猜测代码不存在的问题；如果没发现明显问题，明确写「本片段未发现明显问题」。

代码：
{content}
"""
    result = await get_structured_llm().ainvoke(prompt)
    if result is None:
        return _failed_result("模型没有返回结构化结果")
    return result


async def summarize_analyses(
    analyses: list[AnalysisResult],
    file_path: str,
) -> AnalysisResult:
    """把多个块的分析结果合并成一份文件级报告。"""
    valid = [item for item in analyses if item is not None]
    if not valid:
        return _failed_result("没有可汇总的分析结果")

    analyses_text = "\n\n".join(item.model_dump_json() for item in valid)

    prompt = f"""
你是一名高级代码审查工程师。

文件：{file_path}

以下是同一文件不同代码片段的分析结果：
{analyses_text}

请综合生成最终代码审查报告。
1. 合并重复问题，但保留位置信息（哪个函数、片段内第几行），不要因为合并把位置丢掉。
2. 总结整份文件的主要功能。
3. 整合代码优点和优化建议，每条建议要能直接落地。
4. 不要凭空增加问题；不同片段位置不同但问题相同的，合并成一条并列出多处位置。
"""
    result = await get_structured_llm().ainvoke(prompt)
    if result is None:
        return _failed_result("汇总时模型没有返回结构化结果")
    return result
