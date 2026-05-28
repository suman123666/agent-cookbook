"""第 3 章工具集。

相比第 2 章，新增两个工具：
  ★ save_memory(key, value)  —— 把信息存进长期记忆（跨会话保留）
  ★ think(thought)           —— 让 agent 显式思考再行动（什么都不做，但有奇效）

文件工具（read_file / write_file / list_dir）保留第 2 章设计，
但 BASE_DIR 限定到本章目录，互不越界。
"""
import sys
from pathlib import Path

# 让我们能 import shared.memory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.memory import save_memory as _persist_memory  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent


def _safe_path(path: str) -> Path:
    target = (BASE_DIR / path).resolve()
    if not target.is_relative_to(BASE_DIR):
        raise ValueError(f"路径越界：{path} 不在允许的目录内")
    return target


# ─── 文件工具（沿用第 2 章设计）──────────────────────────
def read_file(path: str) -> str:
    return _safe_path(path).read_text(encoding="utf-8")


def write_file(path: str, content: str) -> str:
    target = _safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"已写入 {len(content)} 个字符到 {path}"


def list_dir(path: str = ".") -> str:
    target = _safe_path(path)
    if not target.is_dir():
        return f"错误：{path} 不是目录"
    items = [p.name + ("/" if p.is_dir() else "") for p in sorted(target.iterdir())]
    return "\n".join(items) if items else "(空目录)"


# ─── ★ 新工具 1：长期记忆 ────────────────────────────────
def save_memory(key: str, value: str) -> str:
    _persist_memory(key, value)
    return f"已存入长期记忆: {key} = {value}"


# ─── ★ 新工具 2：思考（什么都不做，但能提升正确率）────────
def think(thought: str) -> str:
    """这个工具看似无用——它什么都不执行，只是让 agent 必须显式写下推理。
    神奇的是：写下推理的过程会进入对话历史，影响后续决策。
    Anthropic 论文显示复杂任务正确率能提升 15-40%。
    """
    return "已记录思考。继续。"


TOOL_FUNCTIONS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir,
    "save_memory": save_memory,
    "think": think,
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取指定文本文件的全部内容。如果文件不存在会返回错误，可用 list_dir 先查看可用文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "相对本章目录的文件路径"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "把内容写入指定文件（覆盖式）。文件不存在会自动创建。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "相对本章目录的文件路径"},
                    "content": {"type": "string", "description": "要写入的完整文本内容"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "列出指定目录下的文件和子目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "相对本章目录的目录路径，默认为本章根目录"}
                },
                "required": [],
            },
        },
    },
    # ★ 新工具 1：save_memory ───────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": (
                "把一条值得跨会话记忆的信息存进长期记忆。"
                "适合存：用户档案（叫什么、是什么角色）、明确表达的偏好（喜欢简洁/详细）、"
                "技术栈、重要决策。"
                "不要存：本次任务的中间状态、临时计算结果、闲聊内容。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "记忆的键名，用英文简洁描述，例：user_name / preferred_style / tech_stack",
                    },
                    "value": {
                        "type": "string",
                        "description": "要记住的具体内容，中文或英文均可",
                    },
                },
                "required": ["key", "value"],
            },
        },
    },
    # ★ 新工具 2：think ────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "think",
            "description": (
                "写下你的思考过程。这个工具不会执行任何动作——只是让你在采取行动前"
                "显式推理一遍。复杂任务、需要规划、面对模糊需求时使用，能显著提升正确率。"
                "简单的问候、单步任务不必使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "thought": {
                        "type": "string",
                        "description": "你的推理、规划或对当前局面的分析",
                    },
                },
                "required": ["thought"],
            },
        },
    },
]


def run_tool(name: str, args: dict) -> str:
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return f"错误：未知工具 {name}"
    try:
        return func(**args)
    except Exception as e:
        return f"工具执行出错：{type(e).__name__}: {e}"
