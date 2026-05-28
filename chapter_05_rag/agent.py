"""项目 4：带 RAG 工具的个人知识库 agent。

相比项目 3（chapter_03 的带记忆 agent），多了一个 search_knowledge 工具——
让 agent 自主决定"这个问题该不该查我的笔记"。

重点观察：
- 知识相关问题  → agent 主动调 search_knowledge
- 无关问题（闲聊）→ agent 直接回答，不调
- 综合问题       → 可能多次 search 不同 query

运行：uv run python chapter_05_rag/agent.py
退出：exit / quit / 退出
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.client import get_client, MODEL  # noqa: E402
from tools import TOOLS, run_tool  # noqa: E402

client = get_client()


SYSTEM_PROMPT = """你是一个带私有知识库的学习助手。

【你的知识库】
用户已经学过的 agent 课程笔记（chapter_01~04 的 NOTES.md），存在向量库里。
通过 search_knowledge 工具检索。

【行为准则】
1. 用户问 agent 概念、设计、原理等学习相关问题 → 优先调 search_knowledge
2. 引用知识库内容时标注来源（如 [来源: chapter_02_minimal_agent/NOTES.md]）
3. 闲聊、问候、跟知识库无关的问题 → 直接回答，不要查
4. 知识库里没找到时直接说"知识库里没有"，不要瞎编
5. 复杂问题可以多次 search_knowledge（用不同关键词检索）
"""

MAX_ITERATIONS = 10
history = [{"role": "system", "content": SYSTEM_PROMPT}]

print("═" * 60)
print("🤖 个人知识库 agent（输入 exit 退出）")
print("═" * 60)
print("\n建议试试这些问题，观察 agent 决策：")
print("  1. 知识题：「agent 的三大支柱是什么？」")
print("  2. 知识题：「对比 Plan-and-Execute 和 ReAct 的适用场景」")
print("  3. 闲聊：「你好，今天天气怎么样？」(应不调工具)")
print("  4. 综合：「我学了哪些章节？每章核心讲什么？」(可能多次 search)")

while True:
    try:
        user_input = input("\n你: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n再见。")
        break

    if user_input.lower() in {"exit", "quit", "退出"}:
        print("再见。")
        break
    if not user_input:
        continue

    history.append({"role": "user", "content": user_input})

    for _ in range(MAX_ITERATIONS):
        resp = client.chat.completions.create(
            model=MODEL, messages=history, tools=TOOLS, temperature=0,
        )
        choice = resp.choices[0]
        msg = choice.message
        history.append(msg)

        if choice.finish_reason != "tool_calls":
            print(f"\n🤖 {msg.content}")
            break

        # 打印工具调用，让你看到 agent 的决策轨迹
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            if tc.function.name == "search_knowledge":
                print(f"\n🔍 [检索] query={args.get('query', '')!r} top_k={args.get('top_k', 3)}")
            else:
                print(f"\n🔧 [{tc.function.name}] {str(args)[:80]}")

            result = run_tool(tc.function.name, args)

            # 摘要打印检索结果（前 200 字 + 换行替成 | 避免刷屏）
            if tc.function.name == "search_knowledge":
                preview = result[:200].replace("\n", " | ")
                print(f"   返回摘要: {preview}...")

            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
    else:
        print("\n⚠️ 达到最大轮数，本轮强制结束")
