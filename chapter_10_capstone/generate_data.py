"""生成「DTC 美妆品牌 · 达人投放分析」demo 数据库（SQLite）

数据规模：150 主播 / 80 SKU / ~900 投放 / 30000 订单 / ~3000 退货
时间范围：2025-12-03 ~ 2026-06-03 （6 个月，含 618 期间）
平台：抖音 / 小红书 / 快手
主播垂类：美妆 / 时尚 / 母婴 / 美食 / 数码
SKU 品类：口红 / 精华 / 面膜 / 眼影 / 香水

运行：uv run python chapter_10_capstone/generate_data.py
"""
import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

# Windows GBK 控制台 → 强制 UTF-8 输出
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# ═══════════════════════════════════════════════════════════
# 配置区
# ═══════════════════════════════════════════════════════════
DB_PATH = Path(__file__).parent / "data" / "demo.db"
random.seed(42)  # 固定随机种子，每次跑数据完全一致

START_DATE = date(2025, 12, 3)
END_DATE = date(2026, 6, 3)
TOTAL_DAYS = (END_DATE - START_DATE).days

PROMO_618_START = date(2026, 5, 20)
PROMO_618_END = date(2026, 6, 20)

N_INFLUENCERS = 150
N_SKUS = 80
N_ORDERS = 30000

PLATFORMS = ["抖音", "小红书", "快手"]
PLATFORM_WEIGHTS = [0.35, 0.40, 0.25]  # 小红书最多（种草）、快手最少

INFLUENCER_CATEGORIES = ["美妆", "时尚", "母婴", "美食", "数码"]
CATEGORY_WEIGHTS = [0.40, 0.20, 0.15, 0.15, 0.10]  # 美妆为主（DTC 美妆品牌）

SKU_CATEGORIES = ["口红", "精华", "面膜", "眼影", "香水"]
SKU_BASE_REFUND_RATE = {
    "口红": 0.05, "精华": 0.12, "面膜": 0.08, "眼影": 0.06, "香水": 0.15,
}

CAMPAIGN_FORMS = ["直播", "短视频", "种草帖"]
FORM_WEIGHTS = [0.30, 0.40, 0.30]

REFUND_REASONS = ["质量", "不喜欢", "物流", "其他"]
REASON_WEIGHTS = [0.30, 0.40, 0.20, 0.10]

# ═══════════════════════════════════════════════════════════
# 名字生成（不用 Faker，自带常见中文姓名+后缀）
# ═══════════════════════════════════════════════════════════
SURNAMES = list("李王张刘陈杨黄赵周吴徐孙朱马胡林郭何高罗郑梁谢宋唐许韩")
GIVEN_NAMES = ["小琳", "阿婷", "佳佳", "美美", "悦悦", "甜甜", "可可", "莉莉",
               "诗诗", "雨欣", "梓涵", "若曦", "依依", "薇薇", "妙妙", "兮兮",
               "婉儿", "茉莉", "豆豆", "果果", "宝宝", "糖糖", "牛牛", "嘟嘟"]
SUFFIXES = ["种草日记", "美妆笔记", "好物分享", "生活小记", "测评团",
            "推荐官", "选品师", "实验室", "研究所", "在带货"]

def gen_name():
    style = random.choice(["姓名", "姓名后缀", "纯昵称"])
    if style == "姓名":
        return random.choice(SURNAMES) + random.choice(GIVEN_NAMES)
    if style == "姓名后缀":
        return random.choice(SURNAMES) + random.choice(GIVEN_NAMES) + "的" + random.choice(SUFFIXES)
    return random.choice(GIVEN_NAMES) + random.choice(["", "酱", "鸭"]) + random.choice(SUFFIXES[:5])


# ═══════════════════════════════════════════════════════════
# Schema (DDL)
# ═══════════════════════════════════════════════════════════
SCHEMA = """
DROP TABLE IF EXISTS refunds;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS campaigns;
DROP TABLE IF EXISTS skus;
DROP TABLE IF EXISTS influencers;

CREATE TABLE influencers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    platform TEXT NOT NULL,         -- 抖音 / 小红书 / 快手
    follower_count INTEGER NOT NULL,
    category TEXT NOT NULL,         -- 美妆/时尚/母婴/美食/数码
    tier TEXT NOT NULL,             -- 头部/腰部/尾部
    join_date TEXT NOT NULL
);

CREATE TABLE skus (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,         -- 口红/精华/面膜/眼影/香水
    price REAL NOT NULL,
    cost REAL NOT NULL,
    launch_date TEXT NOT NULL
);

CREATE TABLE campaigns (
    id INTEGER PRIMARY KEY,
    influencer_id INTEGER NOT NULL REFERENCES influencers(id),
    platform TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    cost REAL NOT NULL,
    form TEXT NOT NULL,             -- 直播/短视频/种草帖
    period TEXT NOT NULL            -- 日常/618/双11/年货节
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    sku_id INTEGER NOT NULL REFERENCES skus(id),
    order_date TEXT NOT NULL,
    amount REAL NOT NULL,
    status TEXT NOT NULL,           -- 已付款/已完成/已退款
    source_type TEXT NOT NULL,      -- 达人/自然/广告
    source_influencer_id INTEGER REFERENCES influencers(id),
    source_campaign_id INTEGER REFERENCES campaigns(id)
);

CREATE TABLE refunds (
    order_id INTEGER PRIMARY KEY REFERENCES orders(id),
    refund_date TEXT NOT NULL,
    refund_amount REAL NOT NULL,
    reason TEXT NOT NULL            -- 质量/不喜欢/物流/其他
);

CREATE INDEX idx_orders_date ON orders(order_date);
CREATE INDEX idx_orders_influencer ON orders(source_influencer_id);
CREATE INDEX idx_orders_sku ON orders(sku_id);
CREATE INDEX idx_campaigns_influencer ON campaigns(influencer_id);
"""


# ═══════════════════════════════════════════════════════════
# 数据生成
# ═══════════════════════════════════════════════════════════
def gen_influencers():
    """生成 150 个主播，符合金字塔分布"""
    influencers = []
    used_names = set()
    for i in range(1, N_INFLUENCERS + 1):
        # 名字去重
        while True:
            name = gen_name()
            if name not in used_names:
                used_names.add(name)
                break

        platform = random.choices(PLATFORMS, weights=PLATFORM_WEIGHTS)[0]
        category = random.choices(INFLUENCER_CATEGORIES, weights=CATEGORY_WEIGHTS)[0]

        # 等级金字塔：头部 10%、腰部 33%、尾部 57%
        r = random.random()
        if r < 0.10:
            tier = "头部"
            follower = random.randint(1_000_000, 10_000_000)
        elif r < 0.43:
            tier = "腰部"
            follower = random.randint(100_000, 1_000_000)
        else:
            tier = "尾部"
            follower = random.randint(10_000, 100_000)

        # 合作时间：过去 24 个月里随机
        days_ago = random.randint(30, 730)
        join_date = (END_DATE - timedelta(days=days_ago)).isoformat()

        influencers.append((i, name, platform, follower, category, tier, join_date))
    return influencers


def gen_skus():
    """生成 80 个 SKU"""
    skus = []
    for i in range(1, N_SKUS + 1):
        category = random.choice(SKU_CATEGORIES)
        # 不同品类价格区间不同
        price_range = {
            "口红": (80, 350), "精华": (200, 800), "面膜": (50, 250),
            "眼影": (100, 450), "香水": (300, 1200),
        }[category]
        price = round(random.uniform(*price_range), 0)
        cost = round(price * random.uniform(0.30, 0.50), 2)
        name = f"{category}#{i:03d}"

        days_ago = random.randint(60, 730)
        launch_date = (END_DATE - timedelta(days=days_ago)).isoformat()

        skus.append((i, name, category, price, cost, launch_date))
    return skus


def is_618(d: date) -> bool:
    return PROMO_618_START <= d <= PROMO_618_END


def gen_campaigns(influencers):
    """为每个主播生成 5-15 次投放"""
    campaigns = []
    cid = 1
    for inf in influencers:
        inf_id, _, platform, _, _, tier, join_date_str = inf
        join_d = date.fromisoformat(join_date_str)
        # 投放只在合作期内 + 我们关心的时间窗里
        window_start = max(join_d, START_DATE)
        if window_start >= END_DATE:
            continue

        n_camp = random.randint(5, 15)
        for _ in range(n_camp):
            # 在窗口内随机起始
            offset = random.randint(0, (END_DATE - window_start).days)
            start_d = window_start + timedelta(days=offset)
            duration = random.randint(1, 7)
            end_d = min(start_d + timedelta(days=duration), END_DATE)

            # 费用按等级（调整后：贴近真实 DTC 美妆达人投放报价）
            base_cost = {
                "头部": random.uniform(15000, 60000),
                "腰部": random.uniform(1500, 9000),
                "尾部": random.uniform(300, 1000),
            }[tier]

            form = random.choices(CAMPAIGN_FORMS, weights=FORM_WEIGHTS)[0]
            # 直播费用更高
            if form == "直播":
                base_cost *= 1.5
            # 618 期间涨价
            if is_618(start_d):
                base_cost *= 1.3
                period = "618"
            else:
                period = "日常"

            campaigns.append((cid, inf_id, platform, start_d.isoformat(),
                              end_d.isoformat(), round(base_cost, 2), form, period))
            cid += 1
    return campaigns


def gen_orders_and_refunds(influencers, skus, campaigns):
    """生成订单 + 退货。618 期间订单密度更高，主播等级影响销量。"""
    orders = []
    refunds = []

    # 索引方便查
    inf_by_id = {x[0]: x for x in influencers}
    sku_by_id = {x[0]: x for x in skus}
    camp_by_id = {x[0]: x for x in campaigns}

    # 按主播分组投放，方便采样
    camps_by_inf = {}
    for c in campaigns:
        camps_by_inf.setdefault(c[1], []).append(c)

    # 主播销量权重（头部高、腰部中、尾部低，符合二八）
    inf_weights = []
    for inf in influencers:
        tier = inf[5]
        w = {"头部": 30, "腰部": 8, "尾部": 1}[tier]
        inf_weights.append(w)

    next_oid = 1
    for _ in range(N_ORDERS):
        # 来源类型：达人 50% / 自然 30% / 广告 20%
        src_type = random.choices(["达人", "自然", "广告"], weights=[0.50, 0.30, 0.20])[0]

        sku = random.choice(skus)
        amount = round(sku[3] * random.uniform(0.8, 1.0), 2)  # 偶尔有折扣

        # 订单日期
        if random.random() < 0.30:  # 30% 订单集中在 618 期间
            d = PROMO_618_START + timedelta(days=random.randint(0, (PROMO_618_END - PROMO_618_START).days))
            d = min(d, END_DATE)
        else:
            d = START_DATE + timedelta(days=random.randint(0, TOTAL_DAYS))
        order_date = d.isoformat()

        # 归因
        source_inf_id = None
        source_camp_id = None
        if src_type == "达人":
            # 按权重选主播
            inf = random.choices(influencers, weights=inf_weights)[0]
            source_inf_id = inf[0]
            # 找该主播的投放，订单日期在投放后 30 天内的优先
            camps = camps_by_inf.get(source_inf_id, [])
            valid = [c for c in camps if date.fromisoformat(c[3]) <= d <= date.fromisoformat(c[4]) + timedelta(days=30)]
            if valid:
                source_camp_id = random.choice(valid)[0]
            elif camps:
                source_camp_id = random.choice(camps)[0]

        # 状态：85% 已完成 / 5% 已付款 / 10% 已退款
        status = random.choices(["已完成", "已付款", "已退款"], weights=[0.85, 0.05, 0.10])[0]

        # 退货率受品类影响（已退款则按品类概率重新判定）
        if status == "已退款":
            base_refund = SKU_BASE_REFUND_RATE[sku[2]]
            # 尾部主播退货更高
            if source_inf_id:
                tier = inf_by_id[source_inf_id][5]
                if tier == "尾部":
                    base_refund *= 1.4
            # 用 base_refund 判定是否真退（让退货率更接近品类的真实分布）
            if random.random() > base_refund * 6:  # 整体退货 ~10%
                status = "已完成"

        orders.append((next_oid, random.randint(1, 50000), sku[0], order_date,
                       amount, status, src_type, source_inf_id, source_camp_id))

        if status == "已退款":
            # 退货发生在订单后 1-15 天
            refund_d = (d + timedelta(days=random.randint(1, 15))).isoformat()
            reason = random.choices(REFUND_REASONS, weights=REASON_WEIGHTS)[0]
            refunds.append((next_oid, refund_d, amount, reason))

        next_oid += 1

    return orders, refunds


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════
def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript(SCHEMA)

    print("🎲 生成主播 ...")
    influencers = gen_influencers()
    c.executemany("INSERT INTO influencers VALUES (?,?,?,?,?,?,?)", influencers)

    print("🎲 生成 SKU ...")
    skus = gen_skus()
    c.executemany("INSERT INTO skus VALUES (?,?,?,?,?,?)", skus)

    print("🎲 生成投放 ...")
    campaigns = gen_campaigns(influencers)
    c.executemany("INSERT INTO campaigns VALUES (?,?,?,?,?,?,?,?)", campaigns)

    print("🎲 生成订单 + 退货 ...")
    orders, refunds = gen_orders_and_refunds(influencers, skus, campaigns)
    c.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)", orders)
    c.executemany("INSERT INTO refunds VALUES (?,?,?,?)", refunds)

    conn.commit()

    # ─── 摘要 ───────────────────────────────────────────────
    print("\n" + "═" * 60)
    print("📊 生成完成！数据摘要：")
    print("═" * 60)

    for table, count_query in [
        ("influencers", "SELECT COUNT(*) FROM influencers"),
        ("skus", "SELECT COUNT(*) FROM skus"),
        ("campaigns", "SELECT COUNT(*) FROM campaigns"),
        ("orders", "SELECT COUNT(*) FROM orders"),
        ("refunds", "SELECT COUNT(*) FROM refunds"),
    ]:
        n = c.execute(count_query).fetchone()[0]
        print(f"   {table:<15} {n:>8} 行")

    print("\n📂 数据库：", DB_PATH)
    conn.close()


if __name__ == "__main__":
    main()
