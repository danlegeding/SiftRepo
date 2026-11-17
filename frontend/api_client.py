"""SiftRepo 前端的 HTTP 层：发请求、拼 URL、把错误翻译成人话。

页面（frontend/app.py）只负责渲染与交互；要换后端地址，改这里的 API_BASE_URL 或设环境变量。
"""

import html
import os
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)

API_BASE_URL = os.getenv(
    "SIFTREPO_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

def api_error_message(response):
    """尽量从后端错误响应中提取可读信息。"""
    try:
        data = response.json()
        if isinstance(data, dict):
            return data.get(
                "message",
                data.get("detail", response.text[:500]),
            )
        return str(data)[:500]
    except (ValueError, requests.exceptions.JSONDecodeError):
        return response.text[:500] or "服务器返回了无法解析的响应。"

def fetch_projects():
    """从后端拿项目列表（前端不再直连数据库）。"""
    url = f"{API_BASE_URL}/projects"

    try:
        response = requests.get(url, timeout=(10, 60))
    except requests.ConnectionError as exc:
        raise RuntimeError(
            f"无法连接后端：{API_BASE_URL}。请确认 FastAPI 已启动。"
        ) from exc
    except requests.Timeout as exc:
        raise RuntimeError("获取项目列表超时，请检查后端日志。") from exc

    if not response.ok:
        raise RuntimeError(
            f"获取项目列表失败（HTTP {response.status_code}）："
            f"{api_error_message(response)}"
        )

    data = response.json()
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise RuntimeError("项目列表接口返回格式不符合预期。")

    projects = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        project_id = item.get("project_id")
        if project_id is None:
            continue
        projects[str(project_id)] = {
            "name": item.get("name") or f"project-{project_id}"
        }
    return projects


def fetch_project_files(project_id):
    """从后端拿项目下的文件清单与代码块起止行。"""
    url = f"{API_BASE_URL}/projects/{int(project_id)}/files"

    try:
        response = requests.get(url, timeout=(10, 120))
    except requests.ConnectionError as exc:
        raise RuntimeError(
            f"无法连接后端：{API_BASE_URL}。请确认 FastAPI 已启动。"
        ) from exc
    except requests.Timeout as exc:
        raise RuntimeError("获取项目文件超时，请检查后端日志。") from exc

    if not response.ok:
        raise RuntimeError(
            f"获取项目文件失败（HTTP {response.status_code}）："
            f"{api_error_message(response)}"
        )

    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("项目文件接口返回格式不符合预期。")

    files = [
        {
            "file_id": item.get("file_id"),
            "path": item.get("path") or "",
            "language": item.get("language") or "",
            "start_line": item.get("start_line"),
            "end_line": item.get("end_line"),
        }
        for item in (data.get("files") or [])
        if isinstance(item, dict)
    ]

    chunk_rows = [
        {
            "file_id": item.get("file_id"),
            "path": item.get("path") or "",
            "chunk_index": item.get("chunk_index"),
            "start_line": item.get("start_line"),
            "end_line": item.get("end_line"),
        }
        for item in (data.get("chunks") or [])
        if isinstance(item, dict)
    ]

    if data.get("chunks_truncated"):
        st.caption(
            f"代码块过多，仅展示前 {len(chunk_rows)} 条"
            f"（共 {data.get('chunks_total')} 条）。"
        )

    return files, chunk_rows
# endregion


def extract_project_info(data, fallback_name):
    """
    兼容上传接口返回：
    {"project_id": 1, "filename": "..."}
    """
    if not isinstance(data, dict):
        raise ValueError("上传接口返回的 JSON 格式不符合预期。")

    project_data = data.get("project", data)

    if not isinstance(project_data, dict):
        raise ValueError("没有从上传响应中读取到项目信息。")

    project_id = project_data.get(
        "project_id",
        project_data.get("id"),
    )

    if project_id is None:
        raise ValueError(
            "上传接口没有返回 project_id 或 id。"
            "请检查后端上传接口的返回结构。"
        )

    project_name = project_data.get(
        "filename",
        project_data.get(
            "name",
            project_data.get("project_name", fallback_name),
        ),
    )

    return str(project_id), str(project_name)


def upload_project(uploaded_file):
    """将 ZIP 文件交给现有 FastAPI 后端。"""
    url = f"{API_BASE_URL}/projects/upload"

    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            "application/zip",
        )
    }

    try:
        response = requests.post(
            url,
            files=files,
            timeout=(10, 600),
        )

        if not response.ok:
            raise RuntimeError(
                f"上传失败（HTTP {response.status_code}）："
                f"{api_error_message(response)}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(
                "上传接口没有返回有效的 JSON，请检查后端响应。"
            ) from exc

        project_id, project_name = extract_project_info(
            data,
            uploaded_file.name,
        )

        return project_id, project_name

    except requests.Timeout as exc:
        raise RuntimeError(
            "上传等待超时。项目可能仍在处理中，请先检查后端日志，"
            "确认是否已经创建项目，避免重复上传。"
        ) from exc

    except requests.ConnectionError as exc:
        raise RuntimeError(
            f"无法连接后端：{API_BASE_URL}。"
            "请确认 FastAPI 已启动。"
        ) from exc


#把 session_state 里的聊天记录压成「最近几轮问答」传给后端
#           所以追问“那它的超时呢”后端完全不知道“它”指什么。
HISTORY_TURNS_TO_SEND = 3


def build_history(messages, max_turns=HISTORY_TURNS_TO_SEND):
    """从聊天记录里取最近 N 轮「问 + 答」，转成后端要的 history 结构。"""
    turns = []
    pending_question = None

    for message in messages:
        role = message.get("role")
        content = str(message.get("content") or "").strip()
        if role == "user":
            pending_question = content
        elif role == "assistant" and pending_question:
            turns.append({"question": pending_question, "answer": content})
            pending_question = None

    return turns[-max_turns:]


def ask_code_question(question, project_id, history=None):
    """调用已有的 LangGraph 问答接口（带最近几轮对话，支持追问）。"""
    url = f"{API_BASE_URL}/chat/"

    try:
        response = requests.post(
            url,
            json={
                "question": question,
                "project_id": int(project_id),
                "history": history or [],   # 改动：带上历史，供后端做指代补全
            },
            timeout=(10, 180),
        )

        if not response.ok:
            raise RuntimeError(
                f"问答失败（HTTP {response.status_code}）："
                f"{api_error_message(response)}"
            )

        data = response.json()
        answer = data.get("answer")

        if not isinstance(answer, str):
            raise RuntimeError("后端响应中没有有效的 answer 字段。")

        return answer

    except requests.Timeout as exc:
        raise RuntimeError(
            "AI 回答等待超时，请检查后端模型服务及日志。"
        ) from exc

    except requests.ConnectionError as exc:
        raise RuntimeError(
            f"无法连接后端：{API_BASE_URL}。"
            "请确认 FastAPI 已启动。"
        ) from exc


def analyze_code_file(file_id):
    """调用已有的代码分析接口 POST /analysis/。"""
    url = f"{API_BASE_URL}/analysis/"

    try:
        response = requests.post(
            url,
            json={"file_id": int(file_id)},
            timeout=(10, 180),
        )

        if not response.ok:
            raise RuntimeError(
                f"代码分析失败（HTTP {response.status_code}）："
                f"{api_error_message(response)}"
            )

        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("代码分析接口没有返回有效的结果对象。")

        return data

    except requests.Timeout as exc:
        raise RuntimeError(
            "代码分析等待超时，请检查后端模型服务及日志。"
        ) from exc

    except requests.ConnectionError as exc:
        raise RuntimeError(
            f"无法连接后端：{API_BASE_URL}。"
            "请确认 FastAPI 已启动。"
        ) from exc
