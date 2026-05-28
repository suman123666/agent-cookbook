"""第 4 章工具集：沿用第 3 章的文件工具（read/write/list）。

这一章我们不需要 save_memory（不涉及长期记忆）。
也不需要 think 工具——因为 plan/reflect 已经把"显式思考"做成了独立阶段。
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _safe_path(path: str) -> Path:
    target = (BASE_DIR / path).resolve()
    if not target.is_relative_to(BASE_DIR):
        raise ValueError(f"路径越界：{path}")
    return target


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


TOOL_FUNCTIONS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir,
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取指定文本文件的全部内容",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "相对本章目录的文件路径"}},
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
                "properties": {"path": {"type": "string", "description": "相对本章目录的目录路径"}},
                "required": [],
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
