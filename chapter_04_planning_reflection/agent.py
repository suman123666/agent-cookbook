"""项目 3：Plan + Execute + Reflect 完整组合的 agent。

任务：实现一个高质量的 Python 函数 merge_dicts(a, b)，
要求处理嵌套字典/列表合并/类型冲突，支持 strategy 参数。

三阶段架构（生产级 agent 的常见模式）：
  1. Plan    → Planner 一次性出步骤计划，全局视野
  2. Execute → 按计划逐步执行，每步是一个 mini ReAct
  3. Reflect → Critic 审查产出，最多迭代 2 轮修订

实现细节：
  - Plan / Reflect 都用 function calling 让模型输出结构化结果（最稳定）
  - Plan 用 tool_choice 强制模型调用 submit_plan，不会跑偏
  - Critic 用 submit_critique 工具返回 {pass, issues}

运行：uv run python chapter_04_planning_reflection/agent.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.client import get_client, MODEL  # noqa: E402
from tools import TOOLS, run_tool  # noqa: E402

client = get_client()
BASE_DIR = Path(__file__).resolve().parent


def _parse_args(s: str) -> dict:
    """解析模型返回的工具参数 JSON。

    某些 OpenAI 兼容中转渠道会把多个 tool_call 的 arguments 错误地拼接到
    同一个字符串里，导致 json.loads 报 'Extra data'。
    用 raw_decode 只取开头第一个完整 JSON 对象，兼容这种 bug。
    """
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(s)
        return obj

USER_TASK = """实现一个 Python 函数 merge_dicts(a, b, strategy="override")，深度合并两个字典：
1. 嵌套字典递归合并
2. 同 key 的列表合并（保持顺序、去重）
3. 类型冲突时按 strategy 决定：
   - "override"（默认）：用 b 的值覆盖
   - "ignore"：保留 a 的值
   - "raise"：抛 TypeError
4. 不修改原字典（返回新字典）

写到 output/merge_dicts.py，包含：
- 完整的中文 docstring（说明参数、返回、异常）
- 类型注解
- 4 个 if __name__ == "__main__" 下的使用示例（覆盖所有 strategy）"""


# ═══════════════════════════════════════════════════════════
# Phase 1: Plan
# ═══════════════════════════════════════════════════════════
PLAN_TOOL = [{
    "type": "function",
    "function": {
        "name": "submit_plan",
        "description": "提交规划好的步骤列表",
        "parameters": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "description": "步骤序号，从 1 开始"},
                            "action": {"type": "string", "description": "这一步要做的具体动作，越具体越好"},
                            "verify": {"type": "string", "description": "如何验证这一步完成"},
                        },
                        "required": ["id", "action", "verify"],
                    },
                    "description": "按依赖顺序排列的 3-7 个步骤",
                }
            },
            "required": ["steps"],
        },
    },
}]


def plan(task: str) -> list[dict]:
    """让 Planner 输出 JSON 格式的步骤计划（用 function calling 保证结构化）。"""
    print("═" * 60)
    print("📋 Phase 1: Plan")
    print("═" * 60)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": (
                "你是 agent 规划者。把用户任务拆成 3-7 个可独立执行的具体步骤，"
                "按依赖顺序排列。每步都要可验证。完成后调用 submit_plan 提交。"
            )},
            {"role": "user", "content": task},
        ],
        tools=PLAN_TOOL,
        tool_choice={"type": "function", "function": {"name": "submit_plan"}},
        temperature=0,
    )
    args_json = resp.choices[0].message.tool_calls[0].function.arguments
    steps = _parse_args(args_json)["steps"]
    for s in steps:
        print(f"  {s['id']}. {s['action']}")
        print(f"     ✓ 验证：{s['verify']}")
    return steps


# ═══════════════════════════════════════════════════════════
# Phase 2: Execute
# ═══════════════════════════════════════════════════════════
def execute_step(step: dict, prior_results: list[str]) -> str:
    """执行单个步骤——本质是一个小型 ReAct loop。"""
    context = "\n".join(prior_results[-3:]) if prior_results else "（无前置步骤）"
    history = [
        {"role": "system", "content": (
            "你是执行者，专注完成当前一步。可以调用 read_file / write_file / list_dir。"
            "完成后用一句话简短回报结果，不要继续调工具。"
        )},
        {"role": "user", "content": (
            f"【当前步骤】{step['action']}\n"
            f"【验证标准】{step['verify']}\n"
            f"【前几步的结果】\n{context}"
        )},
    ]
    for _ in range(5):  # 每步最多 5 轮工具调用
        resp = client.chat.completions.create(
            model=MODEL, messages=history, tools=TOOLS, temperature=0,
        )
        choice = resp.choices[0]
        msg = choice.message
        history.append(msg)
        if choice.finish_reason != "tool_calls":
            return msg.content or "（无回报）"
        for tc in msg.tool_calls:
            args = _parse_args(tc.function.arguments)
            print(f"    🔧 {tc.function.name}({str(args)[:60]}{'...' if len(str(args)) > 60 else ''})")
            result = run_tool(tc.function.name, args)
            history.append({"role": "tool", "tool_call_id": tc.id, "content": result})
    return "（达到单步最大轮数）"


def execute(steps: list[dict]) -> list[str]:
    """按计划顺序执行所有步骤。"""
    print("\n" + "═" * 60)
    print("⚙️  Phase 2: Execute")
    print("═" * 60)
    results = []
    for step in steps:
        print(f"\n  ▶ 步骤 {step['id']}: {step['action']}")
        result = execute_step(step, results)
        preview = result[:80] + ('...' if len(result) > 80 else '')
        print(f"    ✓ {preview}")
        results.append(f"Step {step['id']}: {result}")
    return results


# ═══════════════════════════════════════════════════════════
# Phase 3: Reflect
# ═══════════════════════════════════════════════════════════
CRITIC_TOOL = [{
    "type": "function",
    "function": {
        "name": "submit_critique",
        "description": "提交代码审查结果",
        "parameters": {
            "type": "object",
            "properties": {
                "passed": {
                    "type": "boolean",
                    "description": "代码是否完全满足任务要求且质量高",
                },
                "issues": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "如未通过，列出具体问题（每条指出位置和修改建议）",
                },
            },
            "required": ["passed", "issues"],
        },
    },
}]


def reflect(task: str, output_path: str, max_iters: int = 2) -> bool:
    """读取产出 → critic 审查 → 必要时让 generator 修订。"""
    print("\n" + "═" * 60)
    print("🔍 Phase 3: Reflect")
    print("═" * 60)

    for round_idx in range(1, max_iters + 1):
        print(f"\n  Round {round_idx}/{max_iters}")
        content = run_tool("read_file", {"path": output_path})

        # ── Critic 审查（用 function calling 保证结构化） ──
        critic_resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": (
                    "你是严苛的 Python 代码审查者。审查代码是否满足任务要求。"
                    "不要客气、不要找借口。如果有问题，越具体越好。"
                    "审查完毕后调用 submit_critique。"
                )},
                {"role": "user", "content": f"【任务】\n{task}\n\n【代码】\n{content}"},
            ],
            tools=CRITIC_TOOL,
            tool_choice={"type": "function", "function": {"name": "submit_critique"}},
            temperature=0,
        )
        critique = _parse_args(critic_resp.choices[0].message.tool_calls[0].function.arguments)

        if critique["passed"]:
            print(f"    ✅ Critic: PASS（第 {round_idx} 轮通过）")
            return True

        print(f"    ⚠️  Critic 发现 {len(critique['issues'])} 个问题：")
        for issue in critique["issues"]:
            print(f"      • {issue}")

        # ── Generator 根据 critique 修订 ──
        print(f"\n    ✏️  正在修订...")
        revise_history = [
            {"role": "system", "content": "你是 Python 工程师，根据审查意见修订代码并用 write_file 保存。"},
            {"role": "user", "content": (
                f"【原任务】\n{task}\n\n"
                f"【当前代码】（{output_path}）\n{content}\n\n"
                f"【审查意见】\n" + "\n".join(f"- {i}" for i in critique["issues"]) + "\n\n"
                f"请逐条修订所有问题，然后调用 write_file 覆盖保存到 {output_path}。"
            )},
        ]
        for _ in range(5):
            resp = client.chat.completions.create(
                model=MODEL, messages=revise_history, tools=TOOLS, temperature=0,
            )
            choice = resp.choices[0]
            msg = choice.message
            revise_history.append(msg)
            if choice.finish_reason != "tool_calls":
                break
            for tc in msg.tool_calls:
                args = _parse_args(tc.function.arguments)
                print(f"    🔧 {tc.function.name}({str(args)[:60]}{'...' if len(str(args)) > 60 else ''})")
                result = run_tool(tc.function.name, args)
                revise_history.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    print(f"\n  ⏹  达到最大反思轮数 {max_iters}（仍未 PASS）")
    return False


# ═══════════════════════════════════════════════════════════
# Main：串联三个阶段
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"【任务】\n{USER_TASK}\n")

    # Phase 1
    steps = plan(USER_TASK)

    # Phase 2
    results = execute(steps)

    # Phase 3
    output_path = "output/merge_dicts.py"
    passed = reflect(USER_TASK, output_path, max_iters=2)

    # ── 总结 ──────────────────────────────────────────
    print("\n" + "═" * 60)
    print("📊 总结")
    print("═" * 60)
    print(f"  计划步骤数: {len(steps)}")
    print(f"  执行步骤数: {len(results)}")
    print(f"  反思结果: {'PASS ✅' if passed else '达到迭代上限（仍可看产出）'}")
    output_full = BASE_DIR / output_path
    if output_full.exists():
        print(f"\n  📄 查看产出: {output_full}")
        print(f"  📏 文件大小: {len(output_full.read_text(encoding='utf-8'))} 字符")
    else:
        print(f"\n  ⚠️  产出文件不存在: {output_full}")
