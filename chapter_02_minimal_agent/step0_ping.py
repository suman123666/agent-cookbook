"""第 0 步：连通性 + function calling 能力预检。

为什么要先跑这个？
- 你用的是中转渠道，得先确认能调通、模型名填对了。
- 更关键：要确认渠道支不支持 function calling（工具调用）。
  这决定了我们 step1-3 怎么写——支持就走"原生工具调用"，
  不支持就降级成"让模型输出 JSON、我们自己解析"。

运行：  uv run python chapter_02_minimal_agent/step0_ping.py
"""
import sys
from pathlib import Path

# 把项目根目录加入模块搜索路径，这样能 import shared 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.client import get_client, MODEL  # noqa: E402

client = get_client()

print(f"使用模型: {MODEL}")
print("=" * 56)

# ── 测试 1：普通对话，确认连通 + 模型名正确 ───────────────
print("【测试 1】普通对话连通性 ...")
try:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "请只回复两个字：你好"}],
    )
    print("  ✅ 连通成功，模型回复:", resp.choices[0].message.content)
except Exception as e:
    print("  ❌ 连不通。检查 OPENAI_BASE_URL / OPENAI_API_KEY / MODEL 是否正确。")
    print("     报错:", e)
    sys.exit(1)

print()

# ── 测试 2：function calling 能力 ─────────────────────────
print("【测试 2】function calling（工具调用）支持情况 ...")
test_tool = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询某个城市当前的天气",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"}
            },
            "required": ["city"],
        },
    },
}]

try:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "北京今天天气怎么样？"}],
        tools=test_tool,
    )
    choice = resp.choices[0]
    if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
        tc = choice.message.tool_calls[0]
        print(f"  ✅ 支持 function calling！")
        print(f"     模型主动请求调用工具: {tc.function.name}({tc.function.arguments})")
        print("     → 我们走主路径（原生工具调用）。")
    else:
        print("  ⚠️ 渠道接受了 tools 参数，但模型这次没触发工具调用。")
        print(f"     finish_reason={choice.finish_reason}")
        print(f"     content={choice.message.content!r}")
        print("     → 大概率仍支持，可以先按主路径试 step2。")
except Exception as e:
    print("  ❌ tools 参数报错，渠道可能不支持 function calling。")
    print("     报错:", e)
    print("     → 我们改走降级方案：prompt-based ReAct。")
