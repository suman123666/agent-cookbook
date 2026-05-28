"""第 2 步：给 agent 装上 1 个工具，手动走完一次"工具调用往返"。

★ 这是整章最重要的代码。★
理解了下面这 5 步，你就理解了所有 agent 的本质：

  1. 把【用户问题 + 工具清单】发给模型
  2. 模型说"我要调 read_file"（finish_reason == "tool_calls"）
  3. 我们在【本地】真正执行 read_file，拿到文件内容
  4. 把执行结果作为 role:"tool" 消息追加回对话（用 tool_call_id 配对）
  5. 再发一次，模型基于文件内容给出最终答案

注意：模型自己不会执行任何代码。它只会"请求"调用工具，真正干活的是我们的 Python。
这就是为什么 agent 既强大又安全可控——执行权始终在你手里。

运行：uv run python chapter_02_minimal_agent/step2_single_tool.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.client import get_client, MODEL  # noqa: E402

client = get_client()
BASE_DIR = Path(__file__).resolve().parent


# ── ① 工具的"真身"：一个普通 Python 函数 ───────────────────
def read_file(path: str) -> str:
    target = (BASE_DIR / path).resolve()
    return target.read_text(encoding="utf-8")


# ── ② 工具的"说明书"：给模型看的 schema（OpenAI function calling 格式）──
tools = [{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "读取指定文本文件的全部内容",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对本章目录的文件路径，例如 sample_notes/python_basics.md",
                }
            },
            "required": ["path"],
        },
    },
}]

user_request = "帮我读取 sample_notes/python_basics.md，总结成 3 个要点。"
history = [{"role": "user", "content": user_request}]

# ── 第 1 次请求：模型决定要不要用工具 ──────────────────────
print("【第 1 次请求】把问题 + 工具清单发给模型 ...")
resp = client.chat.completions.create(model=MODEL, messages=history, tools=tools)
choice = resp.choices[0]
print("  finish_reason =", choice.finish_reason)

# 把模型这条回复（assistant 消息，可能含 tool_calls）追加进历史
history.append(choice.message)

if choice.finish_reason == "tool_calls":
    for tc in choice.message.tool_calls:
        print(f"  → 模型请求调用: {tc.function.name}({tc.function.arguments})")
        print(f"    这次调用的 id = {tc.id}（待会儿用它配对结果）")

        # ── ③ 本地真正执行工具 ──
        args = json.loads(tc.function.arguments)  # arguments 是 JSON 字符串，要先解析
        result = read_file(**args)
        print(f"    本地执行完毕，读到 {len(result)} 个字符")

        # ── ④ 把结果作为 role:"tool" 消息喂回，用 tool_call_id 配对 ──
        history.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": result,
        })

    # ── 第 2 次请求：⑤ 模型基于文件内容给最终答案 ──
    print("\n【第 2 次请求】把工具结果喂回，让模型给最终答案 ...")
    resp2 = client.chat.completions.create(model=MODEL, messages=history, tools=tools)
    print("  finish_reason =", resp2.choices[0].finish_reason)
    print("=" * 56)
    print("最终答案:")
    print(resp2.choices[0].message.content)
else:
    print("模型没调用工具，直接回复:")
    print(choice.message.content)
