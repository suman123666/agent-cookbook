"""Checkpoint + Human-in-the-loop 实战。

演示 LangGraph 两个杀手级能力（手写循环很难做到的）：
  1. Checkpoint    —— 每个 super-step 边界自动保存 state
  2. interrupt_before —— 在指定节点前暂停，等人工审批，再从断点恢复

场景：agent 要操作文件，但每次调工具前都暂停让你审批（批准/拒绝）。
这就是 Claude Code 里"危险命令需要确认"的底层机制。

运行：uv run python chapter_06_langchain/checkpoint_demo.py
"""
import os
import sys
from pathlib import Path
from typing import Annotated, Literal
from typing_extensions import TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.client import MODEL  # noqa: E402

from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402
from langgraph.graph import StateGraph, START, END  # noqa: E402
from langgraph.graph.message import add_messages  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402


# ─── 工具：在独立工作目录里操作 ────────────────────────────
BASE_DIR = Path(__file__).resolve().parent / "checkpoint_workspace"
BASE_DIR.mkdir(exist_ok=True)


@tool
def write_file(path: str, content: str) -> str:
    """在工作目录创建/覆盖一个文件。

    Args:
        path: 文件名
        content: 文件内容
    """
    (BASE_DIR / path).write_text(content, encoding="utf-8")
    return f"已写入 {path}（{len(content)} 字符）"


@tool
def list_dir() -> str:
    """列出工作目录下的所有文件。"""
    items = [p.name for p in sorted(BASE_DIR.iterdir())]
    return "\n".join(items) if items else "(空目录)"


TOOLS = [write_file, list_dir]
TOOL_MAP = {t.name: t for t in TOOLS}


# ─── State + 图 ───────────────────────────────────────────
class State(TypedDict):
    messages: Annotated[list, add_messages]


llm = ChatOpenAI(
    model=MODEL,
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["OPENAI_BASE_URL"],
    temperature=0,
).bind_tools(TOOLS)


def call_llm(state: State) -> dict:
    return {"messages": [llm.invoke(state["messages"])]}


def call_tools(state: State) -> dict:
    last = state["messages"][-1]
    results = []
    for tc in last.tool_calls:
        result = TOOL_MAP[tc["name"]].invoke(tc["args"])
        results.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
    return {"messages": results}


def should_continue(state: State) -> Literal["tools", "__end__"]:
    last = state["messages"][-1]
    return "tools" if (hasattr(last, "tool_calls") and last.tool_calls) else END


graph = StateGraph(State)
graph.add_node("llm", call_llm)
graph.add_node("tools", call_tools)
graph.add_edge(START, "llm")
graph.add_conditional_edges("llm", should_continue, {"tools": "tools", END: END})
graph.add_edge("tools", "llm")

# ★★★ 关键：编译时加 checkpointer + interrupt_before ★★★
checkpointer = InMemorySaver()           # 状态保存器（生产用 SqliteSaver/PostgresSaver）
agent = graph.compile(
    checkpointer=checkpointer,
    interrupt_before=["tools"],           # 在 tools 节点执行【前】暂停
)


# ─── 执行：带人工审批的循环 ───────────────────────────────
# thread_id 标识一个"会话"——同一个 thread_id 的 state 会被持续保存/恢复
config = {"configurable": {"thread_id": "demo-1"}}

initial = {
    "messages": [
        SystemMessage("你是文件助手，能创建文件、列目录。"),
        HumanMessage(
            "请在工作目录创建一个 note.md，内容是'这是 checkpoint 测试'，"
            "然后列出目录确认文件在不在。"
        ),
    ]
}

print("═" * 60)
print("🚀 启动 agent（每次调工具前会暂停审批）")
print("═" * 60)

# 第一次 invoke：agent 会跑到第一个 tools 节点【前】自动暂停
agent.invoke(initial, config)

# 审批循环：只要还有待执行的节点，就暂停问你
while True:
    snapshot = agent.get_state(config)

    # snapshot.next 是「即将执行的节点」的元组；为空 = 跑完了
    if not snapshot.next:
        print("\n✅ agent 已完成所有任务")
        break

    # 被 interrupt 拦在 tools 节点前了——看看它想调什么工具
    print(f"\n⏸  agent 暂停！即将执行节点: {snapshot.next}")
    last_msg = snapshot.values["messages"][-1]
    for tc in last_msg.tool_calls:
        print(f"   🔧 它想调用: {tc['name']}({tc['args']})")

    approve = input("   批准执行吗？[y/n]: ").strip().lower()
    if approve == "y":
        # ★ invoke(None) = 从 checkpoint 断点恢复，继续往下跑
        agent.invoke(None, config)
    else:
        print("   ❌ 已拒绝，终止。")
        break

# ─── 打印最终对话 + 验证文件 ───────────────────────────────
print("\n" + "═" * 60)
print("📜 完整对话历史:")
final = agent.get_state(config)
for msg in final.values["messages"]:
    role = type(msg).__name__
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        calls = ", ".join(tc["name"] for tc in msg.tool_calls)
        print(f"  [{role}] 调用工具: {calls}")
    else:
        print(f"  [{role}] {str(msg.content)[:80]}")

note = BASE_DIR / "note.md"
print(f"\n📄 note.md 是否创建: {'✅ 是' if note.exists() else '❌ 否'}")
if note.exists():
    print(f"   内容: {note.read_text(encoding='utf-8')}")
