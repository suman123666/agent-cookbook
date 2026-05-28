"""用 LangGraph 重写第 2 章的 step3_agent_loop.py。

任务完全一样：读取 sample_notes/ 下所有 .md，整理成 summary。
但实现从「for + if + break + append」变成「画图」。

强烈建议：跑通后打开 chapter_02_minimal_agent/step3_agent_loop.py 对照看。

运行：uv run python chapter_06_langchain/react_agent.py
"""
import os
import sys
from pathlib import Path
from typing import Annotated, Literal
from typing_extensions import TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.client import MODEL  # 复用我们的模型配置  # noqa: E402

from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402
from langgraph.graph import StateGraph, START, END  # noqa: E402
from langgraph.graph.message import add_messages  # noqa: E402


# ═══════════════════════════════════════════════════════════
# ① 工具：用 @tool 装饰器（对照手写版 tools.py 的一大坨 schema）
# ═══════════════════════════════════════════════════════════
# 复用第 2 章的 sample_notes 目录作为操作范围
BASE_DIR = Path(__file__).resolve().parent.parent / "chapter_02_minimal_agent"


def _safe_path(path: str) -> Path:
    target = (BASE_DIR / path).resolve()
    if not target.is_relative_to(BASE_DIR):
        raise ValueError(f"路径越界：{path}")
    return target


@tool
def read_file(path: str) -> str:
    """读取指定文本文件的全部内容。

    Args:
        path: 相对 chapter_02_minimal_agent 目录的文件路径
    """
    return _safe_path(path).read_text(encoding="utf-8")


@tool
def write_file(path: str, content: str) -> str:
    """把内容写入指定文件（覆盖式），文件不存在会自动创建。

    Args:
        path: 相对 chapter_02_minimal_agent 目录的文件路径
        content: 要写入的完整文本
    """
    target = _safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"已写入 {len(content)} 个字符到 {path}"


@tool
def list_dir(path: str = ".") -> str:
    """列出指定目录下的文件和子目录。

    Args:
        path: 相对本章目录的目录路径，默认为根
    """
    target = _safe_path(path)
    if not target.is_dir():
        return f"错误：{path} 不是目录"
    items = [p.name + ("/" if p.is_dir() else "") for p in sorted(target.iterdir())]
    return "\n".join(items) if items else "(空目录)"


TOOLS = [read_file, write_file, list_dir]
TOOL_MAP = {t.name: t for t in TOOLS}
# ★ 对比手写版：你之前要手写 schema 的 "name/description/parameters" 一大坨，
# 这里 @tool 装饰器自动从 docstring + 类型注解 生成 schema。


# ═══════════════════════════════════════════════════════════
# ② 定义 State —— 只有 messages 字段
# ═══════════════════════════════════════════════════════════
class AgentState(TypedDict):
    """state 在节点间流动。

    Annotated[list, add_messages] 是 reducer：
    节点返回 {"messages": [new_msg]} 时，会自动「追加」到列表里，
    而不是「覆盖」。这就是为什么 node 只需要返回新增的部分。
    """
    messages: Annotated[list, add_messages]


# ═══════════════════════════════════════════════════════════
# ③ 准备模型 —— bind_tools 把工具绑给模型
# ═══════════════════════════════════════════════════════════
llm = ChatOpenAI(
    model=MODEL,
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["OPENAI_BASE_URL"],
    temperature=0,
).bind_tools(TOOLS)


# ═══════════════════════════════════════════════════════════
# ④ 定义两个 Node 函数 —— 一个调 LLM、一个执行工具
# ═══════════════════════════════════════════════════════════
def call_llm(state: AgentState) -> dict:
    """调 LLM，把回复追加到 messages。"""
    print("    🟦 [框架调用了 call_llm 节点] 当前 messages 数:", len(state["messages"]))
    response = llm.invoke(state["messages"])
    return {"messages": [response]}   # 只返回新增部分，add_messages 会合并


def call_tools(state: AgentState) -> dict:
    """执行最后一条 AIMessage 里的所有 tool_calls。"""
    print("    🟩 [框架调用了 call_tools 节点]")
    last_msg = state["messages"][-1]
    results = []
    for tc in last_msg.tool_calls:
        tool_fn = TOOL_MAP[tc["name"]]
        try:
            result = tool_fn.invoke(tc["args"])
        except Exception as e:
            result = f"工具执行出错：{type(e).__name__}: {e}"
        # ToolMessage 自动带上 tool_call_id 配对（手写版要自己处理这个）
        results.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
    return {"messages": results}


# ═══════════════════════════════════════════════════════════
# ⑤ Conditional Edge：决定走 tools 还是 END
# ═══════════════════════════════════════════════════════════
def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """对照手写版的 `if resp.finish_reason != "tool_calls": break`。"""
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        print("    🔶 [框架调用了 should_continue 边] → 有 tool_calls，去 tools 节点")
        return "tools"
    print("    🔶 [框架调用了 should_continue 边] → 无 tool_calls，结束(END)")
    return END   # END 是个常量，等于 "__end__"


# ═══════════════════════════════════════════════════════════
# ⑥ 画图！声明节点 + 边 + 条件路由
# ═══════════════════════════════════════════════════════════
graph = StateGraph(AgentState)
graph.add_node("llm", call_llm)
graph.add_node("tools", call_tools)

graph.add_edge(START, "llm")                  # 入口指向 llm
graph.add_conditional_edges(                  # llm 完了根据 should_continue 分流
    "llm",
    should_continue,
    {"tools": "tools", END: END},
)
graph.add_edge("tools", "llm")                # tools 执行完一定回 llm

agent = graph.compile()
# ★ 这 6 行图定义 = 手写版的 for + if + break + append 整段循环


# ═══════════════════════════════════════════════════════════
# ⑦ 执行 + 流式打印（看到每个 node 的执行）
# ═══════════════════════════════════════════════════════════
SYSTEM_PROMPT = """你是文件助手 agent，能调用工具读写文件。

工作原则：
1. 先用 list_dir 看清目录结构，再决定读哪些文件
2. 一次任务里只调必要的工具，不要重复读
3. 完成任务后用一句话告诉用户，不要继续调工具"""

USER_TASK = (
    "请读取 sample_notes/ 目录下所有 .md 文件，"
    "把每个文件总结成 3 个要点，"
    "整理写入 sample_notes/summary_langgraph.md。"
)

print(f"【任务】{USER_TASK}\n" + "═" * 60)

initial_state = {
    "messages": [
        SystemMessage(SYSTEM_PROMPT),
        HumanMessage(USER_TASK),
    ]
}

# ★ agent.stream() —— 不仅是 token 流，还是「node 级别的执行流」
event_idx = 0
for event in agent.stream(initial_state, {"recursion_limit": 20}):
    event_idx += 1
    # ★ 调试：打印框架吐出的原始 event（截断防刷屏）。看清它就是 {节点名: 更新}
    raw = repr(event)
    print(f"\n【原始 event #{event_idx}】 keys={list(event.keys())}")
    print(f"   {raw[:300]}{'  ...(截断)' if len(raw) > 300 else ''}")
    # event 是 dict: {node_name: state_update}
    for node_name, state_update in event.items():
        print(f"\n──── 事件 {event_idx}: node={node_name} ────")
        for msg in state_update["messages"]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    args_preview = str(tc["args"])[:60]
                    print(f"  🔧 调工具 {tc['name']}({args_preview}{'...' if len(str(tc['args'])) > 60 else ''})")
            elif isinstance(msg, ToolMessage):
                preview = str(msg.content)[:80].replace("\n", " ")
                print(f"  ✓ 工具结果: {preview}{'...' if len(str(msg.content)) > 80 else ''}")
            elif hasattr(msg, "content") and msg.content:
                print(f"  🤖 {msg.content[:200]}{'...' if len(msg.content) > 200 else ''}")

print("\n" + "═" * 60)
print(f"✅ Agent 执行完成（共 {event_idx} 个 node 事件）")

# 看产出
summary_path = BASE_DIR / "sample_notes" / "summary_langgraph.md"
if summary_path.exists():
    print(f"\n📄 生成文件: {summary_path}")
    print("─" * 60)
    print(summary_path.read_text(encoding="utf-8"))
