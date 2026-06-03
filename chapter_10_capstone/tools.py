"""达人投放分析 Agent 的 5 个工具。

设计原则：
- execute_sql 强制只读 + 自动 LIMIT 1000
- lookup_metric 用关键词 + 同义词匹配（简易 RAG）
- ask_user 是结构化反问（不是 system prompt 里劝 LLM 追问，而是真有这工具）
"""
import json
import sqlite3
from pathlib import Path

# 路径
_HERE = Path(__file__).parent
DB = _HERE / "data" / "demo.db"
METRICS = json.loads((_HERE / "metrics_dict.json").read_text(encoding="utf-8"))

# 数据集的"今天" —— 让 demo 可复现
TODAY = "2026-06-03"


# ═══════════════════════════════════════════════════════════
# 工具 1：lookup_schema —— 查表结构
# ═══════════════════════════════════════════════════════════
def lookup_schema(table: str = "") -> str:
    """不传 → 列所有表；传 table → 列该表的字段。"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    if not table:
        rows = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        conn.close()
        return "数据库共 5 张表：\n" + "\n".join(f"  - {r[0]}" for r in rows)

    fields = c.execute(f"PRAGMA table_info({table})").fetchall()
    conn.close()
    if not fields:
        return f"找不到表「{table}」"
    return f"表「{table}」的字段：\n" + "\n".join(
        f"  - {f[1]}  ({f[2]})" for f in fields
    )


# ═══════════════════════════════════════════════════════════
# 工具 2：lookup_metric —— 查业务术语（语义层 RAG）
# ═══════════════════════════════════════════════════════════
def lookup_metric(term: str) -> str:
    """关键词 + 同义词匹配。找到 → 返回定义+公式；找不到 → 返回所有可用术语。"""
    term_l = term.lower().strip()
    matches = []
    for m in METRICS:
        candidates = [m["term"].lower()] + [a.lower() for a in m.get("aliases", [])]
        # 任一候选包含查询词，或反过来
        if any(term_l in c or c in term_l for c in candidates):
            matches.append(m)

    if not matches:
        terms = "、".join(m["term"] for m in METRICS)
        return f"⚠️ 词典里没找到「{term}」。\n可用术语：{terms}\n建议 ask_user 让用户澄清。"

    # 返回最匹配的（或多个）
    return json.dumps(matches[:3], ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════
# 工具 3：execute_sql —— 执行 SQL（只读 + 强制 LIMIT）
# ═══════════════════════════════════════════════════════════
def execute_sql(query: str) -> str:
    """安全保护：只允许 SELECT；没 LIMIT 自动加 LIMIT 1000；最多返回前 50 行。"""
    q = query.strip().rstrip(";")
    if not q.upper().lstrip("(").startswith(("SELECT", "WITH")):
        return "❌ 安全限制：只允许 SELECT / WITH 查询"

    if "LIMIT" not in q.upper():
        q += " LIMIT 1000"

    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        rows = c.execute(q).fetchall()
        cols = [d[0] for d in c.description] if c.description else []
        conn.close()
    except Exception as e:
        return f"❌ SQL 错误：{type(e).__name__}: {e}"

    if not rows:
        return "查询结果：0 行（空集）"

    result = {
        "columns": cols,
        "total_rows": len(rows),
        "rows": [dict(zip(cols, r)) for r in rows[:50]],
    }
    return json.dumps(result, ensure_ascii=False, default=str, indent=2)


# ═══════════════════════════════════════════════════════════
# 工具 4：plot_chart —— 生成图表（简化为 ASCII 条形图）
# ═══════════════════════════════════════════════════════════
def plot_chart(data: list, chart_type: str = "bar", title: str = "") -> str:
    """data 是 [{label, value}, ...]。简化为 ASCII 条形图（demo 用，生产可换 matplotlib）"""
    if not data:
        return "❌ 数据为空，无法画图"

    lines = [f"📊 {title or chart_type.upper()}"]
    try:
        values = [float(d.get("value", 0)) for d in data]
    except (ValueError, TypeError):
        return "❌ value 字段不是数字"

    max_val = max(values) if values else 1
    if max_val == 0:
        max_val = 1

    for d, v in zip(data, values):
        label = str(d.get("label", ""))[:15]
        bar = "█" * max(1, int(v / max_val * 30))
        lines.append(f"  {label:<16} {bar}  {v:.2f}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# 工具 5：ask_user —— 反问用户（结构化）
# ═══════════════════════════════════════════════════════════
def ask_user(question: str) -> str:
    """这个工具的特殊性：agent 调用它 = 显式选择"我要反问"
    交互模式下，外层 agent loop 看到这个 tool call 应当停下来等用户回复。
    """
    return f"⏸ 等待用户澄清：{question}"


# ═══════════════════════════════════════════════════════════
# Tool schemas（给 LLM 看的工具说明）
# ═══════════════════════════════════════════════════════════
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_schema",
            "description": "查数据库表结构。不传 table → 列所有表名；传 table → 列该表字段。第一次写 SQL 前建议先调这个。",
            "parameters": {
                "type": "object",
                "properties": {"table": {"type": "string", "description": "表名（可选）"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_metric",
            "description": "查业务术语标准定义和公式。遇到 ROI / 性价比 / 销售量 / 退货率 / 头部主播 / 最近一周 等业务概念必查。",
            "parameters": {
                "type": "object",
                "properties": {"term": {"type": "string", "description": "业务术语"}},
                "required": ["term"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": f"执行 SELECT SQL 查询。数据库截止日期是 {TODAY}（视为'今天'）。只读，自动加 LIMIT 1000。",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "SELECT 或 WITH 起头的 SQL"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plot_chart",
            "description": "生成对比可视化（条形图）。data 格式 [{label:'抖音', value:1.87}, ...]。适合 3+ 项对比时用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "value": {"type": "number"},
                            },
                        },
                    },
                    "chart_type": {"type": "string", "enum": ["bar", "pie", "line"]},
                    "title": {"type": "string"},
                },
                "required": ["data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "用户问题不清楚时反问澄清。如时间含糊（'最近'）、指标含糊（'性价比'查不到定义）、范围太大（'所有'）等。",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string", "description": "你要反问的具体问题"}},
                "required": ["question"],
            },
        },
    },
]


def run_tool(name: str, args: dict) -> str:
    funcs = {
        "lookup_schema": lookup_schema,
        "lookup_metric": lookup_metric,
        "execute_sql": execute_sql,
        "plot_chart": plot_chart,
        "ask_user": ask_user,
    }
    if name not in funcs:
        return f"❌ 未知工具：{name}"
    try:
        return funcs[name](**args)
    except TypeError as e:
        return f"❌ 工具参数错误：{e}"
