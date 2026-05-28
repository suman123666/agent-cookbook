"""项目 6：研究 agent（多 agent 协作 / Orchestrator-Worker 模式）。

架构：
  Planner（分解主题）→ Researcher × N（并行调研）→ Writer（汇总报告）

这是 7.1「场景 B」的答案，也是 Orchestrator-Worker 的典型实现。
用 LangGraph 的 Send API 实现「动态并行」——多个 researcher 在同一个
super-step 里 fan-out（兑现第 6 章 super-step 并行的伏笔）。

运行：uv run python chapter_07_multi_agent/research_agent.py
"""
import operator
import os
import sys
from pathlib import Path
from typing import Annotated
from typing_extensions import TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.client import MODEL  # noqa: E402

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402
from langgraph.graph import StateGraph, START, END  # noqa: E402
from langgraph.constants import Send  # noqa: E402

llm = ChatOpenAI(
    model=MODEL,
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["OPENAI_BASE_URL"],
    temperature=0,
)


# ─── State：多 agent 共享的"黑板" ──────────────────────────
class ResearchState(TypedDict):
    topic: str                                       # 总主题（用户输入）
    subtopics: list[str]                             # Planner 分解出的子主题
    research_results: Annotated[list, operator.add]  # ★ 各 researcher 结果，reducer 合并
    final_report: str                                # Writer 的产出


# ─── Researcher 的"专属输入"（Send 单独传给它的）──────────
class ResearcherInput(TypedDict):
    subtopic: str


# ═══ Node 1: Planner（协调者）—— 把大主题拆成子主题 ═════════
def planner_node(state: ResearchState) -> dict:
    print(f"\n🧭 [Planner] 分解主题: {state['topic']}")
    resp = llm.invoke([
        SystemMessage("你是研究规划者。把主题拆成正好 3 个具体、不重叠的子主题。"
                      "每行一个，不要编号，不要多余的话。"),
        HumanMessage(f"主题：{state['topic']}"),
    ])
    subtopics = [ln.strip() for ln in resp.content.strip().split("\n") if ln.strip()][:3]
    for st in subtopics:
        print(f"   → 子主题: {st}")
    return {"subtopics": subtopics}


# ═══ 路由：Planner 完 → fan-out 派发给多个 Researcher（并行）═
def assign_researchers(state: ResearchState):
    """为每个子主题派发一个 researcher 任务——动态并行的关键。

    返回 Send 列表，LangGraph 让 researcher 节点并行执行 N 次，
    每次输入一个不同的 subtopic。这就是 super-step 并行。
    """
    print(f"\n📤 [派发] {len(state['subtopics'])} 个子主题 → researcher（同一 super-step 并行）")
    return [Send("researcher", {"subtopic": st}) for st in state["subtopics"]]


# ═══ Node 2: Researcher（工人）—— 调研一个子主题 ═══════════
def researcher_node(state: ResearcherInput) -> dict:
    subtopic = state["subtopic"]
    print(f"   🔬 [Researcher] 调研: {subtopic}")
    resp = llm.invoke([
        SystemMessage("你是领域研究员。针对给定子主题，写 150 字以内的要点总结。"),
        HumanMessage(f"子主题：{subtopic}"),
    ])
    # ★ 返回的结果通过 operator.add reducer 合并到全局 research_results
    return {"research_results": [{"subtopic": subtopic, "content": resp.content}]}


# ═══ Node 3: Writer（汇总者）—— 综合成报告 ════════════════
def writer_node(state: ResearchState) -> dict:
    print(f"\n✍️  [Writer] 汇总 {len(state['research_results'])} 份调研，生成报告")
    material = "\n\n".join(
        f"## {r['subtopic']}\n{r['content']}" for r in state["research_results"]
    )
    resp = llm.invoke([
        SystemMessage("你是报告撰写者。把多份子主题调研整合成结构清晰的报告，"
                      "包含引言、分主题正文、结语。"),
        HumanMessage(f"主题：{state['topic']}\n\n调研材料：\n{material}"),
    ])
    return {"final_report": resp.content}


# ═══ 画图 ═══════════════════════════════════════════════════
graph = StateGraph(ResearchState)
graph.add_node("planner", planner_node)
graph.add_node("researcher", researcher_node)
graph.add_node("writer", writer_node)

graph.add_edge(START, "planner")
# planner 完 → assign_researchers fan-out 到多个并行 researcher
graph.add_conditional_edges("planner", assign_researchers, ["researcher"])
# 所有 researcher 完 → writer（LangGraph 自动等全部并行 researcher 跑完，super-step 屏障）
graph.add_edge("researcher", "writer")
graph.add_edge("writer", END)

research_agent = graph.compile()


# ═══ 执行 ═══════════════════════════════════════════════════
if __name__ == "__main__":
    TOPIC = "如何系统地学习构建 AI Agent"

    print("═" * 60)
    print(f"🎯 研究主题: {TOPIC}")
    print("═" * 60)

    result = research_agent.invoke({"topic": TOPIC})

    print("\n" + "═" * 60)
    print("📄 最终报告:")
    print("═" * 60)
    print(result["final_report"])
