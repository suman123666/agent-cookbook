"""项目 2：带长期记忆 + scratchpad 的文件助手 agent。

相比第 2 章的 step3_agent_loop.py，多了三件事：
  1. 启动时从 memory.json 加载长期记忆，注入 system prompt
  2. agent 能调 save_memory 主动存信息（跨会话保留）
  3. agent 能调 think 显式思考（不执行动作，但提升正确率）

体验流程（强烈建议跑两次！）：
  第一次启动 → 告诉它你是谁、有什么偏好 → exit
  第二次启动 → 什么都不说，直接问"我是谁？" → 看它还记不记得

运行：uv run python chapter_03_tools_memory/agent.py
退出：输入 exit / quit / 退出
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.client import get_client, MODEL  # noqa: E402
from shared.memory import load_memory, format_for_prompt  # noqa: E402
from tools import TOOLS, run_tool  # noqa: E402

client = get_client()

# ─── 启动：加载长期记忆 ─────────────────────────────────
memory = load_memory()
print("=" * 60)
print(f"📚 加载长期记忆: {len(memory)} 条")
for k, v in memory.items():
    print(f"   • {k}: {v}")
if not memory:
    print("   （这是首次对话，还没有任何记忆）")
print("=" * 60)

# ─── 把长期记忆注入 system prompt ────────────────────────
SYSTEM_PROMPT = f"""你是一个带长期记忆的文件助手 agent。

【你对当前用户的长期记忆】
{format_for_prompt(memory)}

【行为准则】
1. 面对复杂任务时，先用 think 工具梳理思路再行动
2. 当用户告诉你重要信息（姓名、偏好、技术栈、决策等），主动用 save_memory 存起来
3. 不要把临时计算或本次任务的中间状态存进长期记忆
4. 用中文回答，按用户在记忆中的偏好风格调整（如果有的话）
5. 如果用户问"我是谁"或类似问题，先查看长期记忆里有什么信息
"""

MAX_ITERATIONS = 15
history = [{"role": "system", "content": SYSTEM_PROMPT}]

print("💬 进入对话（输入 exit 退出）")

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
            model=MODEL,
            messages=history,
            tools=TOOLS,
            temperature=0,
        )
        choice = resp.choices[0]
        msg = choice.message
        history.append(msg)

        if choice.finish_reason != "tool_calls":
            print(f"\n🤖 {msg.content}")
            break

        # 打印 agent 的"思考-行动"轨迹，让你直观看到它在干什么
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            if tc.function.name == "think":
                print(f"\n💭 [思考] {args['thought']}")
            elif tc.function.name == "save_memory":
                print(f"\n📝 [记入长期记忆] {args['key']} = {args['value']}")
            else:
                preview = str(args)[:80]
                print(f"\n🔧 [{tc.function.name}] {preview}")

            result = run_tool(tc.function.name, args)
            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
    else:
        print("\n⚠️ 达到最大轮数，本轮强制结束。")
