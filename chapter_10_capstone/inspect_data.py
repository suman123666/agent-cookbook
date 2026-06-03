"""数据合理性检查：跑 6 个 SQL，看数据是否"看起来真实"

运行：uv run python chapter_10_capstone/inspect_data.py
"""
import sqlite3
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

DB_PATH = Path(__file__).parent / "data" / "demo.db"
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()


def print_table(title: str, headers: list, rows: list):
    print("\n" + "─" * 70)
    print(f"【{title}】")
    print("─" * 70)
    # 列宽
    widths = [max(len(str(h)), max((len(str(r[i])) for r in rows), default=0)) + 2
              for i, h in enumerate(headers)]
    print("".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    print("".join("─" * (w - 1) + " " for w in widths))
    for r in rows:
        print("".join(str(v).ljust(widths[i]) for i, v in enumerate(r)))


# ═══════════════════════════════════════════════════════════
# 检查 1：主播分布（平台 × 等级）—— 应符合金字塔
# ═══════════════════════════════════════════════════════════
rows = c.execute("""
    SELECT platform, tier, COUNT(*) AS n
    FROM influencers
    GROUP BY platform, tier
    ORDER BY platform, CASE tier WHEN '头部' THEN 1 WHEN '腰部' THEN 2 ELSE 3 END
""").fetchall()
print_table("检查 1：主播 × 平台 × 等级（看金字塔分布）",
            ["平台", "等级", "数量"], rows)


# ═══════════════════════════════════════════════════════════
# 检查 2：主播垂类分布（美妆该是大头）
# ═══════════════════════════════════════════════════════════
rows = c.execute("""
    SELECT category, COUNT(*) AS n
    FROM influencers
    GROUP BY category
    ORDER BY n DESC
""").fetchall()
print_table("检查 2：主播垂类分布（美妆应占大头）",
            ["垂类", "数量"], rows)


# ═══════════════════════════════════════════════════════════
# 检查 3：618 期间订单密度 vs 日常
# ═══════════════════════════════════════════════════════════
rows = c.execute("""
    SELECT
      CASE WHEN order_date BETWEEN '2026-05-20' AND '2026-06-03'
           THEN '618 期间' ELSE '日常' END AS 期间,
      COUNT(*) AS 订单数,
      ROUND(AVG(amount), 0) AS 平均金额,
      ROUND(SUM(amount), 0) AS GMV
    FROM orders
    GROUP BY 期间
""").fetchall()
print_table("检查 3：618 期间 vs 日常（618 应明显高于日常人均/天）",
            ["期间", "订单数", "客单价", "GMV"], rows)
# 提示日均
total_days = c.execute("""
    SELECT COUNT(DISTINCT order_date) FROM orders
    WHERE order_date NOT BETWEEN '2026-05-20' AND '2026-06-03'
""").fetchone()[0]
n_618 = c.execute("SELECT COUNT(*) FROM orders WHERE order_date BETWEEN '2026-05-20' AND '2026-06-03'").fetchone()[0]
n_normal = c.execute("SELECT COUNT(*) FROM orders WHERE order_date NOT BETWEEN '2026-05-20' AND '2026-06-03'").fetchone()[0]
print(f"   日均：日常 {n_normal // max(total_days,1):>5}/天 | 618 期间 {n_618 // 15:>5}/天")


# ═══════════════════════════════════════════════════════════
# 检查 4：分品类退货率（香水/精华 > 口红/眼影）
# ═══════════════════════════════════════════════════════════
rows = c.execute("""
    SELECT s.category AS 品类,
           COUNT(o.id) AS 订单总数,
           SUM(CASE WHEN o.status = '已退款' THEN 1 ELSE 0 END) AS 退款数,
           ROUND(SUM(CASE WHEN o.status = '已退款' THEN 1.0 ELSE 0 END) / COUNT(o.id) * 100, 2) AS 退货率_pct
    FROM orders o JOIN skus s ON o.sku_id = s.id
    GROUP BY s.category
    ORDER BY 退货率_pct DESC
""").fetchall()
print_table("检查 4：分品类退货率（香水/精华应较高，口红/眼影较低）",
            ["品类", "订单数", "退款数", "退货率%"], rows)


# ═══════════════════════════════════════════════════════════
# 检查 5：主播带单二八分布（头部主播应贡献多数）
# ═══════════════════════════════════════════════════════════
rows = c.execute("""
    SELECT i.tier AS 等级,
           COUNT(DISTINCT i.id) AS 主播数,
           COUNT(o.id) AS 带单数,
           ROUND(SUM(o.amount), 0) AS GMV,
           ROUND(SUM(o.amount) * 100.0 / (SELECT SUM(amount) FROM orders WHERE source_type='达人'), 1) AS GMV占比_pct
    FROM influencers i
    LEFT JOIN orders o ON o.source_influencer_id = i.id
    WHERE o.source_type = '达人'
    GROUP BY i.tier
    ORDER BY GMV DESC
""").fetchall()
print_table("检查 5：达人 GMV 分等级分布（头部应占大头，符合二八）",
            ["等级", "主播数", "带单数", "GMV", "GMV占比%"], rows)


# ═══════════════════════════════════════════════════════════
# 检查 6：跑你 8 句话里的「平台 ROI」(句 4)
# ═══════════════════════════════════════════════════════════
rows = c.execute("""
    WITH spend AS (
      SELECT platform, SUM(cost) AS 投放费
      FROM campaigns
      WHERE start_date >= '2026-05-27'  -- 最近一周
      GROUP BY platform
    ),
    revenue AS (
      SELECT c.platform, SUM(o.amount) AS GMV
      FROM orders o JOIN campaigns c ON o.source_campaign_id = c.id
      WHERE o.order_date >= '2026-05-27'
        AND o.source_type = '达人'
      GROUP BY c.platform
    )
    SELECT s.platform, ROUND(s.投放费, 0) AS 投放费,
           ROUND(COALESCE(r.GMV, 0), 0) AS GMV,
           ROUND(COALESCE(r.GMV, 0) / s.投放费, 2) AS ROI
    FROM spend s LEFT JOIN revenue r ON s.platform = r.platform
    ORDER BY ROI DESC
""").fetchall()
print_table("检查 6：最近一周三平台 ROI（你 8 句话的句 4 真实数据）",
            ["平台", "投放费", "GMV", "ROI"], rows)


# ═══════════════════════════════════════════════════════════
# 整体合理性总结
# ═══════════════════════════════════════════════════════════
total_gmv = c.execute("SELECT ROUND(SUM(amount), 0) FROM orders").fetchone()[0]
total_spend = c.execute("SELECT ROUND(SUM(cost), 0) FROM campaigns").fetchone()[0]
overall_roi = round(total_gmv / total_spend, 2)
overall_refund = c.execute("""
    SELECT ROUND(SUM(CASE WHEN status='已退款' THEN 1.0 ELSE 0 END) / COUNT(*) * 100, 2)
    FROM orders
""").fetchone()[0]

print("\n" + "═" * 70)
print("📈 全局摘要")
print("═" * 70)
print(f"   6 个月总 GMV:        ¥{total_gmv:>12,.0f}")
print(f"   6 个月总投放费:      ¥{total_spend:>12,.0f}")
print(f"   整体 ROI:            {overall_roi}")
print(f"   整体退货率:          {overall_refund}%")

conn.close()
