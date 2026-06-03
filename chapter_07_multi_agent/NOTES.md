# 第 7 章 · 多 Agent 系统 · 知识要点

## 本章定位

前 6 章：1 个 agent + 多个工具。
本章：多个 agent 协作 —— 各管一摊，组队干活。

兑现第 6 章的伏笔：**super-step 并行**在多 agent 场景才见威力。

---

# 🎯 何时需要多 Agent（最重要）

```
铁律：能用「单 agent + 多工具」解决的，别上多 agent。
```

需要的 4 个信号：
```
① 任务能清晰"分工"  —— 研究/写作/审查是不同技能
② 单 agent 工具太多  —— >10-15 个，它会选择困难、调错
③ 需要不同"人格"    —— 严苛批评者 vs 热情创作者，prompt 冲突
④ 需要并行加速      —— 同时调研多个子主题
```

不需要的信号：
```
✗ 工具少（< 10）
✗ 任务线性、单一技能
✗ 一个 system prompt 能说清楚
```

---

# 🧠 核心价值：上下文隔离 + 并行（不是更聪明）

```
❌ 误解：多 agent = 多个大脑 = 更智能
✅ 真相：核心价值是「上下文隔离」和「并行扩展」
```

**上下文隔离**：每个 agent 有自己干净的上下文窗口，不被无关信息干扰。

```
单 agent 做"研究 5 个主题"：
  1 个 200K 上下文塞 5 主题材料 → 互相干扰、可能爆窗

多 agent：
  5 个 researcher 各有独立 200K → 有效上下文 = 5 × 200K（并行扩展）
```

Anthropic 多 agent 研究系统就靠这个突破单一上下文限制。

---

# 🏗 4 种多 Agent 模式

## ① Orchestrator-Worker（最常用 ★）

```
        Orchestrator（项目经理）
       /        |         \
   Worker_1  Worker_2  Worker_3
```
- Orchestrator 分解 + 分派 + 汇总
- Worker 专精，干完上报
- 适合：任务可拆成独立子任务
- 例：研究 agent（项目 6）

## ② Hierarchical（层级）

```
            CEO agent
          /          \
    Manager_A      Manager_B
     /     \        /     \
   W1      W2      W3      W4
```
- 多层管理，比 OW 多了中间层
- 适合：任务极复杂，单层管不过来
- 代价：层级越多越慢越贵

## ③ Swarm / Handoff（交接）

```
Agent_A ──交接──> Agent_B ──交接──> Agent_C
（前台）          （技术支持）       （退款专员）
```
- 没中央协调者，agent 间直接交接控制权
- 适合：流程式任务，按阶段转交（OpenAI Swarm 模式）

## ④ Debate / Critique（辩论）

```
Agent_A 提方案 ←→ Agent_B 批评 ←→ Agent_C 仲裁
```
- 多 agent 互相批评，提升质量
- 类似第 4 章 Reflection 但多视角（多个独立 agent）
- 适合：质量敏感（方案设计、代码审查）

---

# 📡 通信机制：共享 State（黑板模式）

LangGraph 用「共享 state」方式 —— 所有 agent 读写同一个 StateGraph 的 state：

```
   ┌─── 共享 State ───┐
   │ task / results   │
   └──────────────────┘
      ↑↓    ↑↓    ↑↓
   Agent1 Agent2 Agent3
```

设计原则：
- 子 agent **通常不给完整历史**（隔离原则），只给它需要的部分
- 子 agent 输出**通过 reducer 合并**到全局 state

---

# 💰 成本与延迟代价

```
单 agent：1 LLM × N 轮 = N 次调用
多 agent：M agent × 各 N 轮 = M×N 次调用
```

Anthropic 实测：多 agent 比单 agent **贵约 15 倍 token**。

但**并行能降延迟**（墙钟时间）：
```
3 个 researcher 串行：3 × 30 秒 = 90 秒
3 个 researcher 并行：≈ 30 秒
```

**权衡公式**：
> 多 agent = 用「更多 token」换「上下文隔离 + 质量 + 并行降延迟」

---

# 🔧 LangGraph 实现：3 个关键技术

## ① `Send` API —— 动态 fan-out

```python
from langgraph.constants import Send

def assign_researchers(state):
    return [Send("researcher", {"subtopic": st}) for st in state["subtopics"]]

graph.add_conditional_edges("planner", assign_researchers, ["researcher"])
```

`Send("node", input)` = 派一个该节点执行，给它专属输入。
返回 Send 列表 → 多次并行执行（**同一 super-step**）。

## ② Reducer 合并并行结果

```python
class ResearchState(TypedDict):
    research_results: Annotated[list, operator.add]  # ★
```

多个并行 researcher 各返回 `{"research_results": [我的结果]}`，
`operator.add` 把它们**拼成一个列表**——否则会互相覆盖。

**并行节点的输出必须靠 reducer 合并**，这是铁律。

## ③ 同步屏障自动等齐

```python
graph.add_edge("researcher", "writer")
```

一行边定义 → LangGraph **自动等所有并行 researcher 都跑完**，才进 writer。
**你不用写任何 wait/join 逻辑**——声明式编程的威力。

执行结构：
```
super-step 1: [planner]
super-step 2: [researcher × 3 并行]   ← 全跑完才跨屏障
              ↓ 同步屏障
super-step 3: [writer]
```

---

# 📦 项目 6：研究 Agent（Orchestrator-Worker）

```
Planner（分解 3 个子主题）
   ↓ Send fan-out
Researcher × 3（并行调研，结果用 operator.add 合并）
   ↓ 同步屏障（自动等齐）
Writer（汇总成报告）
```

文件：`chapter_07_multi_agent/research_agent.py`

执行顺序铁律：`🧭 → 📤 → 🔬🔬🔬 → ✍️ → 📄`
（writer 必出现在所有 researcher 之后，永不交错）

---

# ⚠️ 诚实说明：图并行 ≠ IO 并发

```
图结构上：3 个 researcher 在同一 super-step（并行）
本地同步 invoke 时：LLM 调用其实是依次发出的（不是同时）
真正 IO 并发（同时发 N 个 API）：需要 async（ainvoke）
```

第 9 章生产化会提性能优化。本章重点是**编排结构**，不是并发加速。

---

# ✅ 自检清单

- [ ] 多 agent 的核心价值是什么？（不是更聪明）
- [ ] 4 种模式各适合什么场景？
- [ ] Send API 和 operator.add reducer 怎么配合实现并行？
- [ ] super-step 同步屏障是什么？为什么 writer 不会和 researcher 交错？
- [ ] 多 agent 比单 agent 贵几倍？什么时候这个代价值得？

---

# 🎓 本章产出

- `chapter_07_multi_agent/research_agent.py` —— Orchestrator-Worker 研究 agent
  - Planner / Researcher × N / Writer 三类节点
  - Send 动态 fan-out + operator.add reducer
  - LangGraph 自动同步屏障

# 📌 关键心智沉淀

```
多 agent 不是"高级 agent"，是「用成本换隔离/并行/质量」
80% 场景 Orchestrator-Worker 够用
先单 agent，遇瓶颈再拆
```


---

◀ 上一章：[第 6 章 · 框架进阶 LangChain + LangGraph](../chapter_06_langchain/NOTES.md)
▶ 下一章：[第 8 章 · 评估与可观测](../chapter_08_evaluation/NOTES.md)

🏠 [回到课程首页](../README.md)
