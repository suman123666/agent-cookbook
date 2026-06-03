"""达人投放分析 Agent 主程序。

架构：
  - 主流程：ReAct loop（最多 10 轮）
  - 子流程：Reflect 反思（每次 execute_sql 后单独叫一次 LLM 评判）
  - 安全：reflect 不通过 → 最多 retry 3 次 → 再不行就老实说

运行（跑示范问题）：uv run python chapter_10_capstone/agent.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from shared.client import get_client, MODEL  # noqa: E402
from tools import TOOLS, run_tool, TODAY  # noqa: E402

client = get_client()

# ═══════════════════════════════════════════════════════════
# Main agent 的 system prompt
# ═══════════════════════════════════════════════════════════
SYSTEM_PROMPT = f"""你是「DTC 美妆品牌 · 达人投放分析」助手。

【角色】
帮品牌运营（如小李）回答关于达人投放 / 平台表现 / SKU 销售的问题。

【数据库背景】
- 5 张表：influencers / campaigns / orders / skus / refunds
- 时间范围：2025-12-03 ~ {TODAY}（视为"今天"）
- 平台：抖音 / 小红书 / 快手
- 主播垂类：美妆 / 时尚 / 母婴 / 美食 / 数码
- SKU 品类：口红 / 精华 / 面膜 / 眼影 / 香水
- 主播等级：头部 / 腰部 / 尾部（按粉丝量）

【工作流程】
1. ★★ 业务术语必查 lookup_metric（不要自己猜定义）★★
   - 指标类：ROI / 性价比 / GMV / 销售量 / 退货率
   - 时间类（最关键！）：最近一周 / 上周 / 最近一个月 / 这个月 / 618 期间 / 平时
   - 分级类：头部主播 / 腰部主播 / 尾部主播 / 直播带货
   ★ 时间词哪怕看起来简单，也要查 —— "上周" 在公司有标准定义，不要自己拍脑袋
2. 表结构不熟 → lookup_schema
3. 写 SQL → execute_sql（写完会自动反思）
4. 拿到合理结果 → 用大白话答复
   ★ 3 个或以上数字对比时 → 调 plot_chart 画图，对话更直观

【常识基线（用于识别异常）】
- ROI 通常 1-5，超过 10 = 异常
- 退货率通常 3-15%，超过 30% = 异常
- 客单价通常 100-500 元

【反问规则】
- 时间含糊（"最近"/"前几天"，词典里也找不到）→ ask_user
- 指标含糊（"效果"/"表现"这种非标术语）→ 先 lookup_metric，找不到 ask_user
- 范围太大（"列出所有"）→ ask_user 确认是不是要 top N

【绝不做的事】
- 不做 INSERT/UPDATE/DELETE
- 不瞎编数字 —— 不确定就 ask_user
- 不强答 —— reflect 3 次都过不了就老实说"无法获取合理结果"
"""

# ═══════════════════════════════════════════════════════════
# Reflect agent 的 system prompt（独立模型调用，避免自圆其说）
# ═══════════════════════════════════════════════════════════
REFLECT_PROMPT = """你是独立的「SQL 结果评判员」，任务是检查 agent 跑的 SQL 结果是否合理。

【输入】
- 用户问的问题
- agent 写的 SQL
- SQL 执行结果

【判断标准（任一为是就 ok=false）】
1. 空结果：但问题应该有数据（例如查"抖音最近一周ROI"返回 0 行）→ 不合理
2. SQL 报错：执行失败 → 不合理
3. 严重数值异常（保守判定，宁可放过不要误杀）：
   - ROI > 20 或 < 0.05  → 不合理
   - 退货率 > 50% 或 < 0 → 不合理
   - 出现负的总额/数量    → 不合理
   ★ 但 ROI = 0.5、1.0、1.8 这种「平庸但真实」的数字都算合理
   ★ 不要因为"低于预期"就判定异常 —— 数据本身就可能不如预期
4. 数据爆炸：返回 > 100 行又没有 GROUP BY 汇总 → 不合理
5. 严重答非所问：列名/指标完全跟问题对不上（如问 ROI 但只返回主播名单）→ 不合理

【输出】严格 JSON 格式（不要 markdown 代码块）：
{"ok": true/false, "category": "OK"/"空结果"/"SQL报错"/"数值异常"/"数据爆炸"/"答非所问", "advice": "若 OK 写 N/A，否则给具体修正建议"}

【重要原则】
默认放行。只在明显错误时才判 false。
你的角色是"质量门卫"，不是"业务顾问"。
"""

MAX_ROUNDS = 10
MAX_RETRIES = 3


# ═══════════════════════════════════════════════════════════
# Reflect 子流程：单独叫一次 LLM 评判
# ═══════════════════════════════════════════════════════════
def reflect(question: str, sql: str, result: str) -> dict:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": REFLECT_PROMPT},
            {"role": "user", "content": (
                f"用户问：{question}\n\n"
                f"SQL：\n{sql}\n\n"
                f"结果（前 2000 字）：\n{result[:2000]}"
            )},
        ],
        temperature=0,
    )
    content = (resp.choices[0].message.content or "").strip()

    # 去掉常见的 markdown 代码块包裹
    if content.startswith("```"):
        content = content.split("\n", 1)[-1] if "\n" in content else content
        content = content.rstrip("`").rsplit("```", 1)[0].strip()
    if content.startswith("json"):
        content = content[4:].strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # 解析失败 → 安全默认通过（避免反思机制本身卡死）
        return {"ok": True, "category": "OK", "advice": "反思解析失败，默认放行"}


# ═══════════════════════════════════════════════════════════
# 主 Agent loop
# ═══════════════════════════════════════════════════════════
def run_agent(user_input: str, verbose: bool = True) -> dict:
    """跑 agent。返回 dict：{answer, trace, rounds, reflect_results}"""
    history = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]
    retry_count = 0
    trace = []           # 记录每个 tool 调用
    reflect_results = [] # 记录每次 reflect 的判定

    for round_idx in range(1, MAX_ROUNDS + 1):
        resp = client.chat.completions.create(
            model=MODEL, messages=history, tools=TOOLS, temperature=0,
        )
        choice = resp.choices[0]
        msg = choice.message
        history.append(msg)

        if choice.finish_reason != "tool_calls":
            answer = msg.content or "(空回复)"
            if verbose:
                print(f"\n🤖 最终回答：\n{answer}\n")
            return {
                "answer": answer,
                "trace": trace,
                "rounds": round_idx,
                "reflect_results": reflect_results,
            }

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args, _ = json.JSONDecoder().raw_decode(tc.function.arguments)

            tname = tc.function.name
            trace.append({"tool": tname, "args": args})  # 评估要用
            if verbose:
                if tname == "execute_sql":
                    print(f"\n[轮 {round_idx}] 🔧 execute_sql:\n{args.get('query', '')}\n")
                else:
                    args_preview = str(args)[:120].replace("\n", " ")
                    print(f"\n[轮 {round_idx}] 🔧 {tname}({args_preview})")

            result = run_tool(tname, args)

            # ── Reflect 子流程：仅对 execute_sql 触发 ──
            if tname == "execute_sql":
                sql = args.get("query", "")
                judgement = reflect(user_input, sql, result)
                ok = judgement.get("ok", True)
                cat = judgement.get("category", "OK")
                advice = judgement.get("advice", "")
                reflect_results.append({"ok": ok, "category": cat})  # 评估要用
                if verbose:
                    icon = "✅" if ok else "❌"
                    print(f"        🔍 反思：{icon} {cat}  建议: {advice[:80]}")

                if not ok:
                    if retry_count < MAX_RETRIES:
                        retry_count += 1
                        result = (
                            result + "\n\n⚠️ 反思发现问题：" + cat +
                            "\n建议：" + advice +
                            f"\n（这是第 {retry_count}/{MAX_RETRIES} 次重试，请修改 SQL 再试）"
                        )
                    else:
                        result = (
                            result + f"\n\n⚠️ 已 reflect {MAX_RETRIES} 次仍未通过。"
                            "请老实告诉用户「未获取合理结果」，或调 ask_user 让用户提供更多信息。"
                        )

            # 截断长 tool 输出，避免 history 爆炸
            if verbose and tname != "execute_sql":
                preview = str(result)[:200].replace("\n", " ")
                print(f"        ↪ {preview}...")

            history.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    if verbose:
        print(f"\n⚠️ 达到 {MAX_ROUNDS} 轮上限")
    return {
        "answer": "(达到最大轮数)",
        "trace": trace,
        "rounds": MAX_ROUNDS,
        "reflect_results": reflect_results,
    }


# ═══════════════════════════════════════════════════════════
# 入口：跑示范问题
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    demo_q = "最近一周的抖音投放ROI是多少？"
    if len(sys.argv) > 1:
        demo_q = " ".join(sys.argv[1:])
    print("═" * 70)
    print(f"问题：{demo_q}")
    print("═" * 70)
    run_agent(demo_q)
