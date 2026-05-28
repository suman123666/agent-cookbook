"""第 3 步：把手动往返变成自动循环——这就是一个真正的 agent。

step2 是手动走完 1 次工具调用。这一步我们把它泛化成 while 循环，
让 agent 自己决定：调几次工具、调哪些工具、什么时候停。

任务：读取 sample_notes/ 下所有 .md 文件，
     总结成 summary.md，每个文件 3 个要点。

预期：agent 会自主依次调用 list_dir → 多次 read_file → write_file，
     循环数轮后以 finish_reason="stop" 结束。

运行：uv run python chapter_02_minimal_agent/step3_agent_loop.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.client import get_client, MODEL  # noqa: E402
from tools import TOOLS, run_tool  # 同目录的 tools.py  # noqa: E402

client = get_client()

# system prompt：约束 agent 的行为风格。好的 system prompt 是 agent 稳定的关键之一。
SYSTEM_PROMPT = """你是一个文件助手 agent，能调用工具读写文件。

工作原则：
1. 先用 list_dir 看清目录结构，再决定读哪些文件
2. 一次任务里只调必要的工具，不要重复读已读过的文件
3. 完成任务后用一句话告诉用户结果，不要继续调工具
"""

USER_TASK = (
    "请读取 sample_notes/ 目录下所有 .md 文件，"
    "把每个文件总结成 3 个要点，"
    "整理写入 sample_notes/summary.md。"
)

MAX_ITERATIONS = 10  # 防无限循环的兜底——agent 万一卡住，不至于无限消耗 API
history = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": USER_TASK},
]

print(f"任务: {USER_TASK}")
print("=" * 60)

round_idx = 0
for round_idx in range(1, MAX_ITERATIONS + 1):
    print(f"\n──── 第 {round_idx} 轮 ────")
    resp = client.chat.completions.create(
        model=MODEL,
        messages=history,
        tools=TOOLS,
        temperature=0,  # agent 决策要稳定，不要创造性
    )
    choice = resp.choices[0]
    msg = choice.message
    history.append(msg)  # 先把模型本轮的回复塞进历史

    # 模型说完话了（没有要求调工具），结束
    if choice.finish_reason != "tool_calls":
        print(f"finish_reason = {choice.finish_reason}")
        print(f"agent 说: {msg.content}")
        break

    # 模型要调工具——可能一次调多个（并行工具调用）
    print(f"agent 决定调 {len(msg.tool_calls)} 个工具:")
    for tc in msg.tool_calls:
        args = json.loads(tc.function.arguments)
        # 参数和结果太长时截断显示，避免刷屏
        args_preview = str(args)[:80] + ("…" if len(str(args)) > 80 else "")
        print(f"  → {tc.function.name}({args_preview})")
        result = run_tool(tc.function.name, args)
        result_preview = result[:80].replace("\n", " ") + ("…" if len(result) > 80 else "")
        print(f"    结果: {result_preview}")
        history.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": result,
        })
else:
    # Python for/else 语法：for 正常跑完没 break 才进 else。
    # 这里意味着循环 MAX_ITERATIONS 轮还没结束 = agent 卡住了。
    print(f"\n⚠️ 达到最大轮数 {MAX_ITERATIONS}，强制停止。")

print("\n" + "=" * 60)
print(f"总共跑了 {round_idx} 轮")

# 看看 agent 写出来的 summary 长啥样
summary_path = Path(__file__).parent / "sample_notes" / "summary.md"
if summary_path.exists():
    print(f"\n📄 生成的 summary.md ({summary_path}):")
    print("─" * 60)
    print(summary_path.read_text(encoding="utf-8"))
else:
    print("\n⚠️ 没找到 summary.md——agent 可能没完成任务。")
