# 第 4 章 · 规划与反思 · 知识要点

## 本章解决什么问题

第 2、3 章的 ReAct agent 在**简单任务**上够用，但两类任务它做不好：

```
1. 复杂多步任务  → ReAct 缺乏全局视野，"边走边返工"
2. 质量敏感任务  → ReAct 一遍生成完就交差，不打磨
```

本章给 agent 工具箱增加两种思维模式：
- **Plan-and-Execute**（4.1）：先规划再执行，避免局部最优
- **Reflection**（4.2）：自审迭代，提升输出质量

---

# 📋 4.1 Planning 模式

## ReAct vs Plan-and-Execute

| 维度 | ReAct | Plan-and-Execute |
|------|-------|------------------|
| 架构 | 单循环 | 两阶段：先 Plan，再 Execute |
| 全局视野 | ❌ 边走边看 | ✅ 一开始就有全局图 |
| 返工成本 | 高 | 低（计划阶段就发现）|
| 灵活性 | ✅ 高 | ⚠️ 计划错了后果严重 |
| 可解释性 | ⚠️ 看历史才知道 | ✅ 计划本身就是文档 |
| 成本 | 每轮都用大模型 | Planner 大模型 + Executor 便宜模型 |
| 适合任务 | 步骤少（<5）、动态强 | 步骤多（5+）、阶段清晰 |

## 反直觉成本优化

```
ReAct        全程用 Claude Opus 4.7         成本: N × 贵
P-and-E      Planner(Opus 1次) + Executor(Haiku N次)  成本: 1 × 贵 + N × 便宜
                                                          ↓
                                            P-and-E 整体更便宜
```

## Re-plan：计划错了怎么办

```python
for i, step in enumerate(plan):
    result = execute(step)
    if failed(result):
        plan = re_plan(task, completed=plan[:i], failure=result)
```

## 任务分解黄金原则

```
✅ 每个子任务可独立验证
✅ 依赖关系明确
✅ 颗粒度均匀（不能一步是"实现项目"，下步是"加分号"）
✅ 数量适中（5-15 步最佳；>20 粒度太细，<3 该用 ReAct）

❌ 不要把"思考"写进步骤——那是 plan 阶段做的，execute 只该有"具体行动"
```

## Tree-of-Thoughts（进阶）

不只生成一条计划，而是多条 → 评估 → 选最优。适合**真正高难度的推理**（数学题、架构设计）。**90% 的 agent 不需要**。

---

# 🔁 4.2 Reflection 模式

## 三种模式对比

| 模式 | 做法 | 推荐度 |
|------|------|--------|
| Self-Critique | 同一 LLM 自审自改 | ⚠️ 易"光环效应"，效果差 |
| **Critic-Generator** | 两个 system prompt 分裂出两个角色 | ⭐ 推荐 |
| **Reflexion** | 失败 → 反思 → 反思塞进 prompt 重试 | ⭐⭐ 高级 |

### Reflexion 的精髓

> **不修改模型权重，只把失败反思写进 prompt，就能让 agent"学会"。**

论文实证：HumanEval 代码任务上提升 11%。这是"verbal reinforcement learning"——用自然语言实现 RL 的"试错-改进"机制。

## Critic 设计的两个反模式 ★

### 反模式 A：太通用、太宽泛
```
❌ "请评价这个回答有什么问题"
→ Critic 只会输出客套话："整体不错，但可以更详细"
```

**修复**：角色 + 维度 + 具体格式
```
✅ "你是 10 年经验的安全工程师，按 4 维度找具体问题：
   - 安全 / 边界 / 命名 / 性能
   每个问题指出行号 + 修改建议"
```

### 反模式 B：没有"PASS"终止信号
```
❌ 只会"列出问题"，永远不说"行了"
→ agent 卡在循环里烧 token
```

**修复**：给明确通过线
```
✅ "如果所有维度 ≥ 4 分且无安全问题，输出 PASS。"
```

**或最稳**：用外部 verifier 优先（测试通过 = PASS）。

## Reflection 的 ROI 曲线 ★

```
质量 ↑
    │       ╱──── 第 3+ 轮几乎平了
    │    ╱──
    │ ╱──        ← 第 1-2 轮提升最大
    └──────────────→ 反思轮数
       1   2   3   4

成本 ↑                          ROI ↑
    │        ╱                    │ ╲ ← 第 1 轮 ROI 最高
    │      ╱                      │  ╲
    │    ╱   (线性)                │   ╲___ ← 第 3+ 轮断崖
    └──────────→                   └──────────→
```

**经验数**：`max_iters=2` 或 `3` 是 ROI 拐点，再多就是烧钱不涨质量。

## 何时该 Reflect

```
✅ 适合
- 质量敏感（代码、文案、设计稿）
- 有客观验收标准（测试通过、metric 达标）
- 失败成本高（线上代码、医疗）

❌ 不适合
- 简单 Q&A
- 工具调用主导（工具结果已是反馈）
- 流式实时输出（反思打破流畅度）
- 成本/延迟敏感
- 任务无"好坏"标准（创意头脑风暴）
```

---

# 🎯 选型四步法（综合 1-4 章）

```
Step 1. 能不能用 workflow？             ← 第 1 章铁律
        能 → 走 workflow，结束
        
Step 2. 估算总步骤数 N
        N < 5 且独立 → ReAct
        N ≥ 5 或强依赖 → Plan-and-Execute
        
Step 3. 任务有质量要求要打磨吗？
        要 → 加 Reflection
        
Step 4. 任务有多个独立子目标吗？
        是 → 多 Agent（第 7 章）
```

---

# 🏗 三种模式的生产组合

```
═════════════════════════════════════════════════════
   Plan ──→ Execute（with ReAct）──→ Reflect
═════════════════════════════════════════════════════

1. Plan: Planner 出 N 步计划
2. Execute: 每步用 ReAct 执行（plan 外层 + ReAct 内层嵌套）
3. Reflect: Critic 审查整体输出，必要时 re-plan
```

**注意**：Plan 和 ReAct 不矛盾，是**嵌套关系**——外层 Plan 给"做什么"，内层 ReAct 决定"具体怎么做"。

---

# 📦 实战项目 3：Plan + Execute + Reflect 完整组合

## 核心架构

```python
def main():
    steps = plan(task)              # Planner LLM + submit_plan 工具
    results = execute(steps)        # 循环 execute_step（mini ReAct）
    passed = reflect(task, output)  # Critic + Generator 双角色
```

## 4 个关键设计决策

1. **Plan / Critic 用 function calling 输出结构化** —— 比 prompt 引导 JSON 稳定得多
2. **`tool_choice` 强制调用 submit_plan** —— 模型不能跑偏
3. **Execute 阶段每步是 mini ReAct** —— Plan 和 ReAct 嵌套
4. **Generator 和 Critic 用不同 system prompt** —— 同模型分裂出两个角色，避免 self-critique 偏差

## 兼容性陷阱：OpenAI 兼容渠道的 3 个坑

```
1. tool_calls.arguments 可能拼接多个 JSON  → 用 json.JSONDecoder.raw_decode() 兼容
2. response_format={"json_object"} 不支持
3. tool_choice 可能不支持
```

防御性代码模板：
```python
def _parse_args(s: str) -> dict:
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(s)
        return obj
```

---

# 🩺 案例分析：Reflection 未 PASS 的真实样貌（最值钱的部分）

实战中 max_iters=2 后**仍未 PASS**——这是 Reflection 的**典型表现**，不是 bug。

## 3 种失效模式同时出现

### A. Critic 鸡蛋里挑骨头
Round 1 的 issue 里夹杂"OK"、"这是正确的"等自相矛盾的话——LLM 当 Critic 时**偏向找问题**（被训练成"乐于助人"），找不到真问题就找细节。

### B. 修订引入新问题
Round 1 修订加的代码（如 TypeVar、Hashable 检查），Round 2 又被批评"冗余"。**修一个问题引一个新问题**。

### C. 任务超出 2 轮能搞定
Round 2 的 issues 1-3 是真问题（"不修改原字典"未实现）——任务复杂度本身超出 2 轮。

## 根本原因

```
LLM 当 Critic 时 ≠ 严格遵守"通过线"
LLM 当 Critic 时 = 倾向输出"看起来像深度审查的内容"

→ self-critic 天然偏向 false（不 PASS）
→ 必须设计明确的"硬性通过标准"
```

## 3 种修复处方

| 处方 | 强度 | 说明 |
|------|------|------|
| 1. 改 Critic prompt，明确 PASS 硬标准 | 简单 | 只列"必须满足的功能点"，不审风格 |
| 2. 加外部 verifier（跑测试）| 可靠 ★ | LLM 当法官不如真跑代码 |
| 3. 分级反思（每轮只看一个维度）| 进阶 | 避免 Critic"想啥批啥" |

## 核心教训

> **生产环境的 Reflection 必须配「外部验证」**——LLM 当 Critic 当法官不可靠。
> 跑测试通过 = PASS，这才是真信号。

---

# ✅ 自检清单

- [ ] ReAct 和 Plan-and-Execute 各自适合什么任务？
- [ ] 为什么 Plan-and-Execute 反而更省钱？
- [ ] Self-Critique 和 Critic-Generator 的本质差别？
- [ ] Critic 设计的两个反模式，怎么修？
- [ ] Reflection 的 ROI 曲线是什么形状？为什么 max_iters 推荐 2-3？
- [ ] OpenAI 兼容渠道的 3 个常见坑各是什么？
- [ ] 看到 Reflection 未 PASS，应该首先检查什么？

---

# 🎓 本章产出

- `chapter_04_planning_reflection/tools.py` —— 文件工具集
- `chapter_04_planning_reflection/agent.py` —— Plan + Execute + Reflect 完整 agent
- `chapter_04_planning_reflection/output/merge_dicts.py` —— agent 自动生成的产出
- 防御性 helper `_parse_args` —— 处理中转渠道多 JSON 拼接问题

**典型运行轨迹**：
```
Plan:    5 步计划
Execute: 按 5 步顺序执行，每步 mini ReAct
Reflect: Round 1 发现问题 → 修订 → Round 2 仍有问题 → 达上限
```

未 PASS ≠ 失败——亲眼看到 Reflection 的边界，比成功 PASS 更有教学价值。


---

◀ 上一章：[第 3 章 · 工具与记忆](../chapter_03_tools_memory/NOTES.md)
▶ 下一章：[第 5 章 · RAG 与知识增强](../chapter_05_rag/NOTES.md)

🏠 [回到课程首页](../README.md)
