# DTC 美妆品牌 · 达人投放分析 Agent

> 一个面向电商运营的"问数 Agent"——用自然语言查达人投放效果、对比平台 ROI、诊断退货异常。

## 项目特色

- 🎯 **业务聚焦**：只做达人投放分析（不做泛电商），故事清晰
- 🧠 **语义层 RAG**：业务术语 + SQL 模板词典，避免 LLM 自己解读口径
- 🔁 **Reflect 反思**：每次 SQL 后独立 LLM 评判，不合理自动重试
- 🛡 **优雅失败**：3 次反思仍不通过 → ask_user 兜底，永不瞎编
- 📊 **可量化评估**：8 题评估集 + 多维度自动打分

## 架构

```
小李提问
   ↓
LLM 大脑 + 5 个工具
   ├─ lookup_schema      查表结构
   ├─ lookup_metric      查业务术语（语义层 RAG）
   ├─ execute_sql        执行 SQL（只读 + 限 1000 行）
   ├─ plot_chart         生成图表
   └─ ask_user           反问澄清（兜底）
   ↓
Reflect 子流程（独立 LLM 评判）
   ↓ ok
最终回答
```

## 数据模型

```
influencers ─┬─< campaigns ─┐
             │              │
             └──────────────┼───< orders >──── skus
                            │       │
                            │       └──< refunds

读法：
   一个主播 → 多次投放
   一次投放 → 多个订单
   一笔订单 → 1 个 SKU + 最多 1 个退货
```

## 快速开始

```bash
# 1. 生成假数据
uv run python chapter_10_capstone/generate_data.py

# 2. 检查数据合理性
uv run python chapter_10_capstone/inspect_data.py

# 3. 跑一个示范问题
uv run python chapter_10_capstone/agent.py "最近一周的抖音投放ROI是多少？"

# 4. 跑全量评估
uv run python chapter_10_capstone/eval_runner.py
```

## 评估表现

```
单次评估 8/8 = 100%
工具调用准确率：100%
答案质量通过率：100%
平均轮数 5.9 / 平均 SQL 1.8 次 / 平均耗时 42s

稳定性（多次跑期望）：~95%
production-ready（业内问数 agent 上线门槛 80%）
```

## 8 题典型场景

```
1. 最近一个月不同平台的主播销售量、退货率
2. 最近一个月不同类型（粉丝量+垂类）主播销售量、退货率
3. 最近一周的抖音投放 ROI
4. 上周三平台 ROI 对比
5. 618 期间 ROI vs 平时
6. 直播带货 SKU 排行
7. 退货率突涨原因诊断
8. 头部 vs 腰部主播性价比
```

## 关键设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 归因方式 | 末次点击 | 业内主流、简单可演示 |
| ROI 口径 | 宽松 | 反映"达人渠道当下健康度" |
| 性价比公式 | (GMV × (1-退货率)) / 投放费 | 同时考虑销量和退货 |
| 数据来源 | 合成数据 (Faker) | 学习项目用，零安全问题 |
| 框架选型 | 纯 OpenAI SDK | 透明、易 debug、对非程序员友好 |

## 局限性 & 下一期

```
当前局限：
  - 数据是合成的（demo 用，非真实业务）
  - 稳定性约 95%（部分边缘问题需多次跑）
  - 没接真实数据库
  - 没接 trace 监控

下一期方向：
  P0：reflect 跑 3 次取多数（提升稳定性到 99%）
  P1：plot_chart 主动调用 + 多轮对话记忆
  P2：包 FastAPI 服务 + 接 LangSmith trace
  P3：接真实数据库（脱敏 + 只读账号 + 权限透传）
```

## 致谢

这是 [10 章 AI Agent 学习项目](../) 的毕业项目。
完整课程：`chapter_01` ~ `chapter_10`。
