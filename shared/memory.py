"""长期记忆：用 JSON 文件持久化跨会话信息。

这是最简实现——一个键值对存储，放在项目根目录的 memory.json。
真实生产里会用向量库做语义检索（第 5 章会学），
但 K-V 已经够个人 agent 用了——而且简单到不会引入新 bug。

设计原则：
  - 写：每次更新都立即落盘（不缓存），简单可靠
  - 读：每次读取都从文件加载（不缓存），保证跨进程一致
"""
import json
from pathlib import Path
from typing import Any

# 长期记忆文件放在项目根目录，所有章节共用一份"用户档案"
_MEMORY_PATH = Path(__file__).resolve().parent.parent / "memory.json"


def load_memory() -> dict[str, Any]:
    """读取全部长期记忆。文件不存在或损坏时返回空字典。"""
    if not _MEMORY_PATH.exists():
        return {}
    try:
        return json.loads(_MEMORY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_memory(key: str, value: Any) -> None:
    """新增/更新一条长期记忆，立即写盘。"""
    data = load_memory()
    data[key] = value
    _MEMORY_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def format_for_prompt(memory: dict[str, Any]) -> str:
    """把长期记忆格式化成适合塞进 system prompt 的字符串。"""
    if not memory:
        return "（暂无长期记忆——这是首次对话）"
    return "\n".join(f"- {k}: {v}" for k, v in memory.items())
