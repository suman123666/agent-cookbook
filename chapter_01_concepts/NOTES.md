# 第 1 章 · 认知地基 · 知识要点

## 核心一句话

> **Workflow 的路径由「程序员」决定；Agent 的路径由「LLM 自己」决定。**

---

## 1. 能力梯子（看清 agent 的位置）

| Level | 形态 | 特征 |
|-------|------|------|
| 0 | 单次问答（completion） | 无状态、无工具、无循环 |
| 1 | Chatbot | 有历史，但只会说不会做 |
| 2 | Workflow | 路径**程序员**写死，LLM 是流水线一环 |
| 3 | **Agent** ★ | 路径**LLM**临场决定，会循环调工具 |

---

## 2. Agent 三大支柱（缺一不可）

```
        ┌─────────────────────────┐
        │      Agent              │
        │                         │
        │   ① LLM 决策核心        │  ← "大脑"
        │         ↕               │
        │   ② 工具集（Tools）     │  ← "手脚"
        │         ↕               │
        │   ③ 反馈循环（Loop）    │  ← "心跳"
        │                         │
        └─────────────────────────┘
```

少了任何一个就不是 agent：
- 没工具 = chatbot（只会说话）
- 没循环 = 单次 function call（一锤子买卖）
- 没 LLM 决策 = 传统程序（写死的脚本）

---

## 3. 三问决策树（选型时直接套用）

```
Q1：完成这个任务的步骤数和顺序，能事先写出来吗？
    ├─ 能   → workflow
    └─ 不能 → Q2

Q2：执行过程中，是否需要根据"上一步的结果"决定"下一步做什么"？
    ├─ 不需要 → workflow
    └─ 需要   → Q3

Q3：失败和重试是可以接受的吗？
    ├─ 不可 → workflow + 兜底规则
    └─ 可以 → ✅ Agent
```

---

## 4. 三种主流 Agent 架构

| 架构 | 模式 | 在哪学 |
|------|------|--------|
| **ReAct** | Think → Act → Observe → 循环 | 第 2 章亲手实现 |
| **Plan-and-Execute** | 先一次性出全部计划 → 再执行 | 第 4 章 |
| **Reflection** | Generate → Critique → Refine → 循环 | 第 4 章 |

---

## 5. 两条实践铁律

### 铁律 1：能不上 agent 就不上 agent

Agent 的三大代价：
- **不可预测**——你不知道它会走几轮
- **贵**——每轮都是一次完整 API 调用
- **慢**——循环天然延迟高

> 大多数生产场景，workflow 才是对的。Agent 只在任务步骤无法预测、必须 LLM 动态决策、且失败可容忍时才值得用。
> ——Anthropic《Building Effective Agents》

### 铁律 2：颗粒度决定架构

同一件事，按不同颗粒度切，可以是 workflow 也可以是 agent：

| 颗粒度 | 例：学习总结 | 类型 |
|--------|----------------|------|
| 粗：「收集→总结→写入」 | 固定三步 | workflow |
| 细：「针对每条内容，LLM 决定要不要展开、要不要查资料」 | 循环+决策 | agent |

**实践指南**：先用 workflow 实现 MVP，再按需把局部环节升级为 agent。

---

## 6. 自检清单

- [ ] 能用一句话说清 workflow 和 agent 的本质区别
- [ ] 能说出 agent 的三大支柱
- [ ] 拿到新需求能用三问决策树判断该用什么架构
- [ ] 理解"能不上 agent 就不上"的工程哲学

---

## 7. 推荐扩展阅读

- Anthropic 《Building Effective Agents》（必读）
- Anthropic 《Effective context engineering for AI agents》
- Lilian Weng 《LLM Powered Autonomous Agents》


---

▶ 下一章：[第 2 章 · 最小 Agent](../chapter_02_minimal_agent/NOTES.md)

🏠 [回到课程首页](../README.md)
