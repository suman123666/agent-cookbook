"""第 10 章评估集：小李 8 句话原话 + 期望工具调用 + 关键词。

每条 case 包含 3 类评估线索：
  - expected_metric_lookups：应该调 lookup_metric 查的术语（Unit 评估）
  - required_keywords:        最终答案里必须出现的关键词（E2E 评估）
  - golden_numbers:           可选——关键数字 ± 容差（数字精度评估）

★ 关键词允许"任一命中"（or 逻辑）和"必须全中"（and 逻辑）两种。
"""

DATASET = [
    {
        "id": "q1_platform_sales_refund",
        "question": "最近一个月不同平台的主播的销售量、退货率是多少？",
        "expected_metric_lookups": ["最近一个月", "销售量", "退货率"],
        "required_keywords_any": ["抖音", "小红书", "快手"],   # 至少命中 1 个就算 ✓
        "required_keywords_all": ["销售", "退货"],              # 必须全中
    },
    {
        "id": "q2_tier_category_sales_refund",
        "question": "最近一个月不同类型的主播的销售量、退货率是多少？类型按粉丝量和内容垂类区分",
        "expected_metric_lookups": ["最近一个月", "头部", "腰部"],
        "required_keywords_any": ["头部", "腰部", "尾部"],
        "required_keywords_all": ["销售", "退货"],
    },
    {
        "id": "q3_douyin_roi",
        "question": "最近一周的抖音投放ROI是多少？",
        "expected_metric_lookups": ["最近一周", "ROI"],
        "required_keywords_any": ["1.87", "1.8"],   # 容许 1.87 / 1.8 / 1.87左右
        "required_keywords_all": ["抖音"],
    },
    {
        "id": "q4_three_platform_roi",
        "question": "上周抖音 vs 小红书 vs 快手的 ROI，哪个最高？",
        "expected_metric_lookups": ["上周", "ROI"],
        "required_keywords_any": ["抖音"],   # 三平台对比结论：抖音应是最高
        "required_keywords_all": ["抖音", "小红书", "快手"],
        "must_contain_winner": "抖音",   # 结论必须指明抖音最高
    },
    {
        "id": "q5_618_vs_normal_roi",
        "question": "618 期间投放 ROI 比平时高还是低？",
        "expected_metric_lookups": ["618", "平时", "ROI"],
        "required_keywords_any": ["高", "低"],   # 至少给出结论方向
        "required_keywords_all": ["618"],
    },
    {
        "id": "q6_livestream_top_sku",
        "question": "哪些 SKU 在直播带货里最好卖？",
        "expected_metric_lookups": ["直播带货", "销售量"],
        "required_keywords_any": ["SKU", "口红", "精华", "面膜", "眼影", "香水"],
        "required_keywords_all": [],
    },
    {
        "id": "q7_refund_diagnosis",
        "question": "这个月退货率突然涨了,是哪个主播/SKU 的问题?",
        "expected_metric_lookups": ["这个月", "退货率"],
        "required_keywords_any": ["主播", "SKU"],
        "required_keywords_all": ["退货"],
    },
    {
        "id": "q8_tier_value",
        "question": "头部主播 vs 腰部主播,哪个性价比更高?",
        "expected_metric_lookups": ["性价比", "头部", "腰部"],
        "required_keywords_any": ["头部", "腰部"],
        "required_keywords_all": ["性价比"],
    },
]
