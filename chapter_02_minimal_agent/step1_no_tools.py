"""第 1 步：伪 agent（无工具）。

这就是第 1 章任务 A——一个只会说话、不会做事的 LLM。
我们故意让它去"读文件"，看它怎么回应。

重点体会：没有工具，LLM 只能在嘴上承认无能（或者瞎编一段内容）。
这就是"为什么需要给 LLM 装工具"的直观理由。

运行：uv run python chapter_02_minimal_agent/step1_no_tools.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.client import get_client, MODEL  # noqa: E402

client = get_client()

user_request = (
    "帮我读取 chapter_02_minimal_agent/sample_notes/python_basics.md 这个文件，"
    "总结成 3 个要点。"
)

resp = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": user_request}],
)

print("用户请求:", user_request)
print("=" * 56)
print("模型回复:")
print(resp.choices[0].message.content)
print("=" * 56)
print("👀 模型没有读文件的能力，它只能说'我做不到'，或者凭空编造内容。")
print("   下一步 step2，我们给它装上 read_file 工具。")
