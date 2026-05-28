"""第 5 章工具集：核心是 search_knowledge 工具。

设计哲学：
- 不强制 agent 每次都查（agent 应判断"这个问题需要查私有知识吗"）
- 检索结果格式化得含来源 + 相似度（agent 可引用、判断质量）
- 只暴露一个工具，让 agent 专注做"何时用 RAG"的决策
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from retriever import search  # 复用 5.2 的检索函数（同目录）


def search_knowledge(query: str, top_k: int = 3) -> str:
    """在私有知识库（向量库）里检索相关内容。

    返回格式化字符串：top-K 个 chunk + 来源 + 相似度。
    """
    chunks = search(query, top_k=top_k)
    if not chunks:
        return "（知识库里没找到相关内容）"

    lines = [f"检索到 {len(chunks)} 个相关片段："]
    for i, c in enumerate(chunks, 1):
        lines.append(f"\n[{i}] 来源: {c['source']} | 相似度: {c['similarity']:.2f}")
        lines.append(c["content"])
    return "\n".join(lines)


TOOL_FUNCTIONS = {
    "search_knowledge": search_knowledge,
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": (
                "在用户的私有知识库（学过的 agent 课程笔记）里搜索相关内容。"
                "返回 top-K 个相关片段，每片段含来源文件和相似度分数。\n\n"
                "**何时使用**：\n"
                "- 用户问关于 agent 设计、ReAct、RAG、记忆、规划等学习过的概念\n"
                "- 用户让你回顾、总结、对比之前学过的内容\n"
                "- 你不确定某个细节，去查笔记验证\n\n"
                "**何时不要使用**：\n"
                "- 用户问天气、时间、闲聊等无关话题\n"
                "- 用户只是打招呼\n"
                "- 答案已经在当前对话历史里出现过"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询，越具体越好。例：'agent 三大支柱'、'chunking 策略 overlap'",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回 top-K 个最相关片段，默认 3，复杂问题可设 5",
                        "default": 3,
                    },
                },
                "required": ["query"],
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
