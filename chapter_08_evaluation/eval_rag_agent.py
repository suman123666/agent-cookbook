"""第 8 章实战：给 chapter_05_rag 的 RAG agent 做评估。

落地评估三层 + 4 大指标，纯本地不依赖任何云服务。

评估对象：第 5 章的 search_knowledge agent
评估集：  6 个手工编写的 case（4 知识题 + 2 闲聊）
指标：
  - Unit 评估：工具使用准确率（调对工具了吗）
  - E2E 评估：答案质量（关键词命中 / 克制不瞎编）
  - 效率指标：平均轮数
  - 整体成功率：Unit + E2E 都过的比例

运行：uv run python chapter_08_evaluation/eval_rag_agent.py
"""
import json
import sys
from pathlib import Path

# 同时加 shared 和 chapter_05_rag 到路径（复用第 5 章的工具）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "chapter_05_rag"))

from shared.client import get_client, MODEL  # noqa: E402
from tools import TOOLS, run_tool  # noqa: E402  来自 chapter_05_rag/tools.py

client = get_client()

SYSTEM_PROMPT = """你是带私有知识库的学习助手。
- 知识题（agent 概念、ReAct、RAG 等）→ 优先调 search_knowledge 检索
- 闲聊/无关问题 → 直接回答，不调工具，不瞎编"""

# ═══════════════════════════════════════════════════════════
# ① 评估数据集（人工编写的"考题" + 标准答案）
# ═══════════════════════════════════════════════════════════
DATASET = [
    {
        "id": "knowledge_1",
        "input": "agent 的三大支柱是什么？",
        "should_search": True,                    # ← 期望调工具
        "expected_keywords": ["LLM", "工具", "循环"],  # ← 答案应含的关键词
    },
    {
        "id": "knowledge_2",
        "input": "ReAct 和 Plan-and-Execute 的区别？",
        "should_search": True,
        "expected_keywords": ["ReAct", "Plan", "规划"],
    },
    {
        "id": "knowledge_3",
        "input": "RAG 的 chunking 为什么需要 overlap？",
        "should_search": True,
        "expected_keywords": ["overlap", "重叠", "切"],
    },
    {
        "id": "knowledge_4",
        "input": "temperature=0 对 agent 决策有什么影响？",
        "should_search": True,
        "expected_keywords": ["稳定", "确定", "决策"],
    },
    {
        "id": "chitchat_1",
        "input": "你好，今天天气怎么样？",
        "should_search": False,                   # ← 期望不调工具
        "expected_keywords": [],
    },
    {
        "id": "chitchat_2",
        "input": "1+1 等于几？",
        "should_search": False,
        "expected_keywords": [],
    },
]


# ═══════════════════════════════════════════════════════════
# ② 跑 agent，记录关键指标
# ═══════════════════════════════════════════════════════════
def run_agent(user_input: str) -> dict:
    """跑一次 agent，返回 {answer, used_search, rounds}。"""
    history = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]
    used_search = False
    rounds = 0

    for _ in range(10):
        rounds += 1
        resp = client.chat.completions.create(
            model=MODEL, messages=history, tools=TOOLS, temperature=0,
        )
        choice = resp.choices[0]
        msg = choice.message
        history.append(msg)

        if choice.finish_reason != "tool_calls":
            return {
                "answer": msg.content or "",
                "used_search": used_search,
                "rounds": rounds,
            }

        for tc in msg.tool_calls:
            if tc.function.name == "search_knowledge":
                used_search = True
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args, _ = json.JSONDecoder().raw_decode(tc.function.arguments)
            result = run_tool(tc.function.name, args)
            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    return {"answer": "(达到最大轮数)", "used_search": used_search, "rounds": rounds}


# ═══════════════════════════════════════════════════════════
# ③ 评估单个 case（三层评估 + 规则评分）
# ═══════════════════════════════════════════════════════════
def evaluate_case(case: dict) -> dict:
    result = run_agent(case["input"])

    # ── Unit 评估：工具使用准确率 ──
    tool_correct = result["used_search"] == case["should_search"]

    # ── E2E 评估：答案质量 ──
    answer_lower = result["answer"].lower()
    if case["should_search"]:
        # 知识题：关键词命中至少一半
        hit = sum(1 for kw in case["expected_keywords"] if kw.lower() in answer_lower)
        answer_quality = hit >= max(1, len(case["expected_keywords"]) // 2)
    else:
        # 闲聊：判断是否"克制"（不瞎编天气、不瞎答数学）
        bad_signals = ["温度", "气温", "晴天", "雨天"]
        answer_quality = not any(b in result["answer"] for b in bad_signals)

    return {
        "id": case["id"],
        "input": case["input"],
        "tool_correct": tool_correct,
        "answer_quality": answer_quality,
        "rounds": result["rounds"],
        "used_search": result["used_search"],
        "should_search": case["should_search"],
        "answer_preview": result["answer"][:100].replace("\n", " "),
    }


# ═══════════════════════════════════════════════════════════
# ④ 主流程：跑全集 + 输出报告
# ═══════════════════════════════════════════════════════════
def main():
    print("═" * 64)
    print(f"📊 评估开始：{len(DATASET)} 个 case")
    print("═" * 64)

    results = []
    for i, case in enumerate(DATASET, 1):
        print(f"\n[{i}/{len(DATASET)}] {case['id']}: {case['input']}")
        r = evaluate_case(case)
        results.append(r)

        tool_mark = "✅" if r["tool_correct"] else "❌"
        ans_mark = "✅" if r["answer_quality"] else "❌"
        print(f"   工具决策 {tool_mark}  调了 search: {r['used_search']} | 期望: {r['should_search']}")
        print(f"   答案质量 {ans_mark}  ({r['rounds']} 轮)")
        print(f"   回答预览: {r['answer_preview']}...")

    # ─── 汇总报告 ─────────────────────────────────────────
    print("\n" + "═" * 64)
    print("📈 评估报告")
    print("═" * 64)

    n = len(results)
    tool_correct = sum(r["tool_correct"] for r in results)
    answer_correct = sum(r["answer_quality"] for r in results)
    both_correct = sum(r["tool_correct"] and r["answer_quality"] for r in results)
    avg_rounds = sum(r["rounds"] for r in results) / n

    print(f"\n  工具使用准确率: {tool_correct}/{n} = {tool_correct/n*100:5.1f}%")
    print(f"  答案质量通过率: {answer_correct}/{n} = {answer_correct/n*100:5.1f}%")
    print(f"  整体成功率:    {both_correct}/{n} = {both_correct/n*100:5.1f}%   ★ 综合指标")
    print(f"  平均轮数:      {avg_rounds:.1f}")

    failures = [r for r in results if not (r["tool_correct"] and r["answer_quality"])]
    if failures:
        print(f"\n  ⚠️  失败 case ({len(failures)}):")
        for f in failures:
            issues = []
            if not f["tool_correct"]:
                issues.append("工具决策错")
            if not f["answer_quality"]:
                issues.append("答案不达标")
            print(f"     • {f['id']}: {', '.join(issues)}")

    print("\n" + "═" * 64)
    print("💡 这就是评估的最小可用形态：")
    print("   评估集 → 跑 agent → 多维度打分 → 量化报告")
    print("   下次改 prompt / 工具 / 模型，跑这个脚本，对比数字就知道变好变坏")
    print("═" * 64)


if __name__ == "__main__":
    main()
