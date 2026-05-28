"""第 2 章 agent 能调用的工具集。

每个工具由三部分组成：
  ① 一个普通 Python 函数（真正干活）
  ② 一份 OpenAI function schema（告诉模型：这工具叫啥、干啥、要什么参数）
  ③ 在 TOOL_FUNCTIONS 派发表里登记"名字 → 函数"映射

所有文件操作都被限制在本章目录内（BASE_DIR），防止 agent 越权乱碰你的硬盘。
这是 agent 安全的第一课——给工具划边界。第 9 章会系统讲。
"""
from pathlib import Path

# 所有文件操作的根目录：本章目录。agent 不能跳出这里。
BASE_DIR = Path(__file__).resolve().parent


def _safe_path(path: str) -> Path:
    """把模型给的相对路径解析成绝对路径，并确保它落在 BASE_DIR 内。"""
    target = (BASE_DIR / path).resolve()
    if not target.is_relative_to(BASE_DIR):
        raise ValueError(f"路径越界：{path} 不在允许的目录内")
    return target


# ─── ① 工具的"真身"：3 个普通 Python 函数 ───────────────────

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


# ─── ③ 名字 → 函数 派发表（run_tool 用） ────────────────────
TOOL_FUNCTIONS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir,
}

# ─── ② 给模型看的工具说明（OpenAI function calling 格式）───
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取指定文本文件的全部内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "相对本章目录的文件路径，如 sample_notes/python_basics.md",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "把内容写入指定文件（覆盖式），文件不存在会自动创建",
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
                    "path": {
                        "type": "string",
                        "description": "相对本章目录的目录路径，默认为本章根目录",
                    }
                },
                "required": [],
            },
        },
    },
]


def run_tool(name: str, args: dict) -> str:
    """按名字派发到对应函数；出错时把错误信息当结果返回，让 agent 有机会自愈。"""
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return f"错误：未知工具 {name}"
    try:
        return func(**args)
    except Exception as e:
        return f"工具执行出错：{type(e).__name__}: {e}"
