"""跑评估集，输出多维度打分报告。

评估维度（参考第 8 章「评估三层」）：
  ① Unit  - 工具调用：期望的 metric 是否被查（部分匹配）
  ② E2E   - 答案内容：必中关键词 + 任中关键词
  ③ 效率  - 平均轮数
  ④ 综合  - Unit + E2E 都过的成功率（严格 AND）

运行：uv run python chapter_10_capstone/eval_runner.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from agent import run_agent  # noqa: E402
from eval_dataset import DATASET  # noqa: E402


# ═══════════════════════════════════════════════════════════
# 单题评估
# ═══════════════════════════════════════════════════════════
def evaluate_case(case: dict) -> dict:
    t0 = time.time()
    result = run_agent(case["question"], verbose=False)
    elapsed = time.time() - t0

    answer = result.get("answer", "")
    trace = result.get("trace", [])
    rounds = result.get("rounds", 0)
    reflect_results = result.get("reflect_results", [])

    # ── Unit：是否调了期望的 metric ──
    looked_up = [
        t["args"].get("term", "").lower()
        for t in trace
        if t["tool"] == "lookup_metric"
    ]
    expected = [m.lower() for m in case.get("expected_metric_lookups", [])]
    # 部分匹配：期望的术语在调用过的术语里有"子串"也算
    metric_hits = sum(
        1 for exp in expected
        if any(exp in lu or lu in exp for lu in looked_up)
    )
    metric_pass = (metric_hits >= max(1, len(expected) // 2))   # 至少一半命中

    # ── E2E：关键词命中 ──
    answer_lower = answer.lower()
    must_all = case.get("required_keywords_all", [])
    must_any = case.get("required_keywords_any", [])

    all_hit = all(k.lower() in answer_lower for k in must_all) if must_all else True
    any_hit = any(k.lower() in answer_lower for k in must_any) if must_any else True

    # 特殊：必须含 winner
    winner_ok = True
    if "must_contain_winner" in case:
        winner_ok = case["must_contain_winner"].lower() in answer_lower

    answer_pass = all_hit and any_hit and winner_ok

    # ── 效率指标 ──
    sql_count = sum(1 for t in trace if t["tool"] == "execute_sql")
    reflect_fails = sum(1 for r in reflect_results if not r.get("ok"))

    overall_pass = metric_pass and answer_pass

    return {
        "id": case["id"],
        "question": case["question"],
        "answer_preview": answer[:200].replace("\n", " "),
        "metric_pass": metric_pass,
        "metric_hits": f"{metric_hits}/{len(expected)}",
        "answer_pass": answer_pass,
        "all_hit": all_hit,
        "any_hit": any_hit,
        "winner_ok": winner_ok,
        "overall_pass": overall_pass,
        "rounds": rounds,
        "sql_count": sql_count,
        "reflect_fails": reflect_fails,
        "elapsed_sec": round(elapsed, 1),
    }


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════
def main():
    print("═" * 70)
    print(f"📊 评估开始：{len(DATASET)} 题")
    print("═" * 70)

    results = []
    for i, case in enumerate(DATASET, 1):
        print(f"\n[{i}/{len(DATASET)}] {case['id']}")
        print(f"   问题: {case['question'][:60]}")
        r = evaluate_case(case)
        results.append(r)

        m_mark = "✅" if r["metric_pass"] else "❌"
        a_mark = "✅" if r["answer_pass"] else "❌"
        o_mark = "★" if r["overall_pass"] else "✗"
        print(f"   工具调用 {m_mark} ({r['metric_hits']})  "
              f"答案 {a_mark}  综合 {o_mark}  "
              f"轮={r['rounds']} SQL={r['sql_count']} 反思失败={r['reflect_fails']} "
              f"耗时={r['elapsed_sec']}s")
        print(f"   答案: {r['answer_preview']}...")

    # ─── 总报告 ───────────────────────────────────────────
    print("\n" + "═" * 70)
    print("📈 评估总报告")
    print("═" * 70)

    n = len(results)
    metric_ok = sum(r["metric_pass"] for r in results)
    answer_ok = sum(r["answer_pass"] for r in results)
    overall_ok = sum(r["overall_pass"] for r in results)
    avg_rounds = sum(r["rounds"] for r in results) / n
    avg_sql = sum(r["sql_count"] for r in results) / n
    avg_reflect_fails = sum(r["reflect_fails"] for r in results) / n
    avg_time = sum(r["elapsed_sec"] for r in results) / n

    print(f"\n  工具调用准确率（Unit）:   {metric_ok}/{n} = {metric_ok/n*100:5.1f}%")
    print(f"  答案质量通过率（E2E）：   {answer_ok}/{n} = {answer_ok/n*100:5.1f}%")
    print(f"  整体成功率（综合）：     {overall_ok}/{n} = {overall_ok/n*100:5.1f}%   ★")
    print(f"")
    print(f"  平均轮数：               {avg_rounds:.1f}")
    print(f"  平均 SQL 查询次数：      {avg_sql:.1f}")
    print(f"  平均反思失败次数：       {avg_reflect_fails:.1f}")
    print(f"  平均耗时：               {avg_time:.1f}s")

    # 失败 case
    failures = [r for r in results if not r["overall_pass"]]
    if failures:
        print(f"\n  ⚠️  失败 case ({len(failures)}):")
        for f in failures:
            issues = []
            if not f["metric_pass"]:
                issues.append("工具调用差")
            if not f["all_hit"]:
                issues.append("关键词缺失")
            if not f["any_hit"]:
                issues.append("方向不对")
            if "winner_ok" in f and not f["winner_ok"]:
                issues.append("结论错")
            print(f"     • {f['id']}: {', '.join(issues)}")
            print(f"       答案: {f['answer_preview'][:120]}...")

    print("\n" + "═" * 70)


if __name__ == "__main__":
    main()
